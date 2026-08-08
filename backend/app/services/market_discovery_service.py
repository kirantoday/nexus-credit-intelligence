"""Market-wide SEC discovery orchestrator (PLAN.md Milestone 7.5).

The reverse of `app.services.filing_monitor_service`: that module answers
"what changed for issuers Nexus already knows about?"; this module answers
"which issuers does Nexus not yet know about, that real SEC filing activity
says are distress-relevant right now?"

Layer 0 (this module, new): SEC's own full-text-search index
(`efts.sec.gov`), queried with a curated set of high-precision distress
phrases (`app.core.distress_rules.MARKET_DISCOVERY_FULL_TEXT_QUERIES`)
restricted to `MONITORED_FORM_TYPES`, market-wide, within a date window —
cheap SEC-side pre-filtering, never a scan of every filing by every filer.
Layer 1 (unchanged, `app.core.distress_rules.match_rules`) and Layer 2
(unchanged, `app.ai.evidence_review`) still gate what actually becomes
`research_evidence`/alerts — a Layer 0 hit is a *candidate issuer to look
at*, never evidence by itself.

Once a hit resolves to a canonical issuer (`app.core.issuer_resolver`,
CIK-first — the full-text-search hit already carries SEC's own authoritative
CIK, so no name/ticker guessing happens here at all), this module hands off
to the exact same `app.services.filing_monitor_service.process_issuer_filings`
pipeline `filing_monitor_service` already uses for known issuers — this
module contains no separate evidence/alert-synthesis logic of its own
(PLAN.md Milestone 7.5: "do not build separate business logic for
historical and nightly/discovery processing").

Same watermark discipline as `filing_monitor_service`:
`resulting_watermark` only advances on a zero-error run. Idempotency is
two-layered: `market_discovery_candidate`, keyed by `(cik, accession_no)`,
is Layer 0's own dedup/audit record (skipped on a re-run unless
`force_reprocess` or the active `RULE_VERSION` has changed since the row
was last written — see that table's docstring for why source identity and
processing state are deliberately kept separate); the actual
`sec_filing`/`research_evidence`/`alert_event` rows it may lead to have
their own independent idempotent get-or-create keys further downstream, so
Layer 0 re-examining a filing never duplicates them.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from app.ai.providers.base import LLMProvider
from app.core.distress_rules import MARKET_DISCOVERY_FULL_TEXT_QUERIES
from app.core.issuer_resolver import IssuerResolutionResult, resolve_issuer_identity_by_cik
from app.core.types import (
    MONITORED_FORM_TYPES,
    FilingMonitorRunMode,
    FilingMonitorRunStatus,
    MarketDiscoveryResolutionOutcome,
)
from app.domain.market_discovery import (
    MarketDiscoveryCandidateCreate,
    MarketDiscoveryRun,
    MarketDiscoveryRunCreate,
)
from app.providers.base.http_client import ThrottledHttpClient
from app.providers.sec_edgar.client import (
    FULL_TEXT_SEARCH_MAX_PAGE_SIZE,
    FetchResult,
    SecEdgarClient,
)
from app.providers.sec_edgar.dto import SecFullTextSearchResponseDTO
from app.repositories import market_discovery_repository, sec_filing_repository
from app.services import alert_synthesis_service, universe_classification_service
from app.services.enrichment_orchestrator import EnrichmentClients
from app.services.enrichment_orchestrator import enrich_issuer as default_enrich_issuer
from app.services.filing_monitor_service import (
    IssuerFilingProcessingResult,
    describe_sec_source,
    process_issuer_filings,
)

# Bumped whenever `distress_rules`/the AI evidence-review prompt changes
# materially enough that an already-examined filing deserves a fresh look —
# `market_discovery_candidate.rule_version` is compared against this to
# decide whether a previously-seen `(cik, accession_no)` should be silently
# skipped or deliberately reprocessed (see that table's docstring; also
# forced unconditionally via `force_reprocess=True`).
RULE_VERSION = "2026-08.1"

# Safety cap (PLAN.md Milestone 7.5 section 29 — "do not accept obviously
# pathological behavior"): a broad bare-word query (e.g. "going concern")
# could in principle return thousands of hits across a wide date range.
# Capped, not silently truncated — a capped query is recorded in the run's
# `error_summary` as a note, not swallowed.
DEFAULT_MAX_HITS_PER_QUERY = 500


def _split_forms_for_full_text_search(forms: tuple[str, ...]) -> list[tuple[str, ...]]:
    """Milestone 7.5.1 root-cause fix: SEC's full-text-search `forms`
    parameter silently breaks when amendment-suffix form types (e.g.
    `"8-K/A"`) are mixed into the same comma-separated list as base form
    types — live-verified directly against `efts.sec.gov`: `forms=8-K`
    alone returned 577 real hits for a "chapter 11" query over a fixed
    window, `forms=8-K,10-K` returned 1002, but `forms=8-K,10-K/A` (mixing
    one amendment suffix into the list) returned 0, and the actual
    10-form list this milestone's `MONITORED_FORM_TYPES` used returned
    just 50 instead of the ~1460 confirmed to genuinely exist in that
    window — a >96% real coverage loss, not a hypothetical one. Splitting
    into a same-list-quirk-free base-forms request and a separate
    amendment-forms request (both individually confirmed correct) recovers
    full intended coverage without changing which form types are in scope
    — not a query/scope expansion, a fix to how the existing approved list
    is actually transmitted to SEC's API."""
    base = tuple(sorted(f for f in forms if "/" not in f))
    amendments = tuple(sorted(f for f in forms if "/" in f))
    return [group for group in (base, amendments) if group]


class SearchFullTextFn(Protocol):
    def __call__(
        self,
        http_client: ThrottledHttpClient,
        *,
        query: str,
        forms: tuple[str, ...],
        start_date: date,
        end_date: date,
        from_offset: int,
        size: int,
    ) -> FetchResult[SecFullTextSearchResponseDTO]: ...


def _default_search_full_text(
    http_client: ThrottledHttpClient,
    *,
    query: str,
    forms: tuple[str, ...],
    start_date: date,
    end_date: date,
    from_offset: int,
    size: int,
) -> FetchResult[SecFullTextSearchResponseDTO]:
    client = SecEdgarClient(http_client)
    return client.search_full_text(
        f'"{query}"',
        forms=forms,
        start_date=start_date,
        end_date=end_date,
        from_offset=from_offset,
        size=size,
    )


class ResolveIssuerFn(Protocol):
    def __call__(
        self, db: Session, http_client: ThrottledHttpClient, *, cik: str
    ) -> IssuerResolutionResult: ...


class ProcessIssuerFilingsFn(Protocol):
    def __call__(
        self,
        db: Session,
        http_client: ThrottledHttpClient,
        *,
        cik: str,
        issuer_id: UUID,
        since_date: date | None,
    ) -> IssuerFilingProcessingResult: ...


class EnrichIssuerFn(Protocol):
    def __call__(
        self,
        db: Session,
        issuer_id: UUID,
        clients: EnrichmentClients,
        llm: LLMProvider | None,
        *,
        environment: str,
        force: bool,
    ) -> object: ...


def run_discovery(
    db: Session,
    http_client: ThrottledHttpClient,
    llm: LLMProvider | None,
    *,
    mode: FilingMonitorRunMode,
    window_start: date | None = None,
    window_end: date | None = None,
    environment: str,
    force_reprocess: bool = False,
    queries: tuple[str, ...] = MARKET_DISCOVERY_FULL_TEXT_QUERIES,
    forms: tuple[str, ...] = tuple(sorted(MONITORED_FORM_TYPES)),
    max_hits_per_query: int = DEFAULT_MAX_HITS_PER_QUERY,
    search_full_text_fn: SearchFullTextFn = _default_search_full_text,
    resolve_issuer_fn: ResolveIssuerFn = resolve_issuer_identity_by_cik,
    process_issuer_filings_fn: ProcessIssuerFilingsFn = process_issuer_filings,
    enrichment_clients: EnrichmentClients | None = None,
    enrich_issuer_fn: EnrichIssuerFn = default_enrich_issuer,
) -> MarketDiscoveryRun:
    """Run one market-discovery pass. `mode` mirrors `filing_monitor_service`:
    `BASELINE` establishes a watermark with zero processing (never floods a
    first run with the market's entire distress history); `BACKFILL`
    requires an explicit `window_start`/`window_end`; `DELTA` derives
    `window_start` from the previous successful run's watermark.

    `enrichment_clients`, when provided, makes every resolved issuer
    (`matched_existing` and `verified_new` alike — no "only newly
    discovered" gate) automatically flow into
    `app.services.enrichment_orchestrator.enrich_issuer` right after its
    SEC filings are processed, exactly matching PLAN.md Milestone 7.5's
    "one reusable enrichment pipeline" requirement. `None` (the default)
    skips automatic enrichment entirely for this run — useful for a
    discovery-only pass or a test that doesn't need three provider
    clients configured.
    """
    if mode is FilingMonitorRunMode.BACKFILL and (window_start is None or window_end is None):
        raise ValueError("backfill mode requires window_start and window_end")

    latest_successful = market_discovery_repository.get_latest_successful_run(db)
    previous_watermark = latest_successful.resulting_watermark if latest_successful else None

    if mode is FilingMonitorRunMode.DELTA:
        resolved_start = previous_watermark.date() if previous_watermark else date.today()
        resolved_end = date.today()
    elif mode is FilingMonitorRunMode.BACKFILL:
        assert window_start is not None and window_end is not None
        resolved_start, resolved_end = window_start, window_end
    else:  # BASELINE
        resolved_start = resolved_end = date.today()

    run = market_discovery_repository.create_run(
        db,
        MarketDiscoveryRunCreate(
            mode=mode,
            window_start_date=resolved_start,
            window_end_date=resolved_end,
            previous_watermark=previous_watermark,
        ),
    )
    db.commit()

    if mode is FilingMonitorRunMode.BASELINE:
        completed_baseline = market_discovery_repository.complete_run(
            db,
            run.id,
            status=FilingMonitorRunStatus.BASELINE_ESTABLISHED,
            resulting_watermark=datetime.now(UTC),
            queries_executed=0,
            filings_examined=0,
            candidate_filings=0,
            issuers_resolved_existing=0,
            issuers_resolved_new=0,
            issuers_ambiguous=0,
            issuers_rejected=0,
            evidence_created=0,
            alerts_created=0,
            errors_count=0,
            error_summary=None,
        )
        db.commit()
        return completed_baseline

    error_messages: list[str] = []
    seen_filing_keys: set[tuple[str, str]] = set()
    processed_issuer_ids: set[UUID] = set()
    queries_executed = 0
    filings_examined = 0
    candidate_filings = 0
    issuers_resolved_existing = 0
    issuers_resolved_new = 0
    issuers_ambiguous = 0
    issuers_rejected = 0
    evidence_created = 0
    alerts_created = 0
    errors_count = 0

    for query in queries:
        for forms_group in _split_forms_for_full_text_search(forms):
            from_offset = 0
            while True:
                result = search_full_text_fn(
                    http_client,
                    query=query,
                    forms=forms_group,
                    start_date=resolved_start,
                    end_date=resolved_end,
                    from_offset=from_offset,
                    size=FULL_TEXT_SEARCH_MAX_PAGE_SIZE,
                )
                queries_executed += 1
                hits = result.dto.hits.hits
                filings_examined += len(hits)

                for hit in hits:
                    accession_no = hit.source.adsh
                    file_date_value = date.fromisoformat(hit.source.file_date)
                    for cik in hit.source.ciks or ():
                        if not cik:
                            continue
                        key = (cik, accession_no)
                        if key in seen_filing_keys:
                            continue
                        seen_filing_keys.add(key)
                        candidate_filings += 1

                        existing = market_discovery_repository.get_candidate_by_filing(
                            db, cik=cik, accession_no=accession_no
                        )
                        if (
                            existing is not None
                            and not force_reprocess
                            and existing.rule_version == RULE_VERSION
                        ):
                            continue

                        try:
                            resolution = resolve_issuer_fn(db, http_client, cik=cik)
                        except Exception as exc:  # noqa: BLE001 - per-candidate isolation
                            db.rollback()
                            errors_count += 1
                            error_messages.append(
                                f"resolve cik {cik} accession {accession_no}: {exc}"
                            )
                            continue

                        market_discovery_repository.upsert_candidate(
                            db,
                            MarketDiscoveryCandidateCreate(
                                discovery_run_id=run.id,
                                cik=cik,
                                accession_no=accession_no,
                                form_type=hit.source.form,
                                file_date=file_date_value,
                                matched_query=query,
                                sec_items=hit.source.items or None,
                                resolution_outcome=resolution.outcome,
                                resolution_reason=resolution.reason,
                                issuer_id=(
                                    UUID(resolution.issuer_id) if resolution.issuer_id else None
                                ),
                                layer1_matched=False,
                                evidence_created=False,
                                provenance_id=None,
                                rule_version=RULE_VERSION,
                            ),
                        )
                        db.commit()

                        if resolution.outcome == MarketDiscoveryResolutionOutcome.MATCHED_EXISTING:
                            issuers_resolved_existing += 1
                        elif resolution.outcome == MarketDiscoveryResolutionOutcome.VERIFIED_NEW:
                            issuers_resolved_new += 1
                        elif resolution.outcome == MarketDiscoveryResolutionOutcome.AMBIGUOUS:
                            issuers_ambiguous += 1
                        else:
                            issuers_rejected += 1

                        if resolution.outcome not in (
                            MarketDiscoveryResolutionOutcome.MATCHED_EXISTING,
                            MarketDiscoveryResolutionOutcome.VERIFIED_NEW,
                        ):
                            continue

                        assert resolution.issuer_id is not None
                        issuer_id = UUID(resolution.issuer_id)
                        if issuer_id in processed_issuer_ids:
                            continue
                        processed_issuer_ids.add(issuer_id)

                        try:
                            processing_result = process_issuer_filings_fn(
                                db,
                                http_client,
                                cik=cik,
                                issuer_id=issuer_id,
                                since_date=resolved_start,
                            )
                            if processing_result.evidence:
                                new_alerts = (
                                    alert_synthesis_service.synthesize_alerts_from_evidence(
                                        db,
                                        evidence=processing_result.evidence,
                                        describe_source=lambda e: describe_sec_source(db, e),
                                        llm=llm,
                                        environment=environment,
                                        is_backfill=(mode is FilingMonitorRunMode.BACKFILL),
                                    )
                                )
                                alerts_created += len(new_alerts)
                                universe_classification_service.classify_issuer(
                                    db,
                                    issuer_id,
                                    processing_result.evidence,
                                    as_of_date=file_date_value,
                                )
                            evidence_created += len(processing_result.evidence)

                            triggering_filing = sec_filing_repository.get_filing_by_accession(
                                db, accession_no
                            )
                            if triggering_filing is not None:
                                filing_evidence = [
                                    e
                                    for e in processing_result.evidence
                                    if e.filing_id == triggering_filing.id
                                ]
                                if filing_evidence:
                                    market_discovery_repository.upsert_candidate(
                                        db,
                                        MarketDiscoveryCandidateCreate(
                                            discovery_run_id=run.id,
                                            cik=cik,
                                            accession_no=accession_no,
                                            form_type=hit.source.form,
                                            file_date=file_date_value,
                                            matched_query=query,
                                            sec_items=hit.source.items or None,
                                            resolution_outcome=resolution.outcome,
                                            resolution_reason=resolution.reason,
                                            issuer_id=issuer_id,
                                            layer1_matched=True,
                                            evidence_created=True,
                                            provenance_id=filing_evidence[0].provenance_id,
                                            rule_version=RULE_VERSION,
                                        ),
                                    )
                            db.commit()

                            if enrichment_clients is not None:
                                # Every resolved issuer, `matched_existing` and
                                # `verified_new` alike — the orchestrator's own
                                # staleness policy is what keeps this cheap for
                                # issuers already enriched recently, not a gate
                                # here on "is this newly discovered."
                                enrich_issuer_fn(
                                    db,
                                    issuer_id,
                                    enrichment_clients,
                                    llm,
                                    environment=environment,
                                    force=False,
                                )
                        except Exception as exc:  # noqa: BLE001 - per-issuer isolation
                            db.rollback()
                            errors_count += 1
                            error_messages.append(
                                f"process issuer {issuer_id} (CIK {cik}) filings: {exc}"
                            )
                            continue

                total_hits = result.dto.hits.total.value
                next_offset = from_offset + len(hits)
                if len(hits) == 0 or next_offset >= total_hits:
                    break
                if next_offset >= max_hits_per_query:
                    error_messages.append(
                        f"query {query!r}: capped at {max_hits_per_query} hits "
                        f"(SEC reported {total_hits} total) — see PLAN.md Milestone 7.5 section 29"
                    )
                    break
                from_offset = next_offset

    status = (
        FilingMonitorRunStatus.SUCCESS
        if errors_count == 0
        else FilingMonitorRunStatus.COMPLETED_WITH_ERRORS
    )
    resulting_watermark = datetime.now(UTC) if errors_count == 0 else previous_watermark

    completed = market_discovery_repository.complete_run(
        db,
        run.id,
        status=status,
        resulting_watermark=resulting_watermark,
        queries_executed=queries_executed,
        filings_examined=filings_examined,
        candidate_filings=candidate_filings,
        issuers_resolved_existing=issuers_resolved_existing,
        issuers_resolved_new=issuers_resolved_new,
        issuers_ambiguous=issuers_ambiguous,
        issuers_rejected=issuers_rejected,
        evidence_created=evidence_created,
        alerts_created=alerts_created,
        errors_count=errors_count,
        error_summary="; ".join(error_messages) if error_messages else None,
    )
    db.commit()
    return completed
