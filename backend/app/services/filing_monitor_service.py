"""The SEC-specific overnight filing monitor orchestrator (PLAN.md 24.5).

Baseline / delta / backfill modes, watermark rules, idempotent
accession-number-keyed filing ingestion, per-issuer error isolation so one
issuer's failure never loses the run. Produces `research_evidence` rows
(`evidence_provider=sec_edgar`, `source_type=sec_filing`) via Layer 1
deterministic rule matching, then hands them to the provider-agnostic
`app.services.alert_synthesis_service` — this module contains no
alert-synthesis logic of its own.

Takes injectable `fetch_filings_fn`/`fetch_filing_text_fn` dependencies so
watermark/idempotency/retry logic is unit-testable without hitting live SEC
on every test run; the real wiring (the script + the manual-trigger API)
passes the actual `app.providers.sec_edgar.provider` functions.

**Known limitation** (documented, not a design shortcut): SEC's `filing_date`
has day granularity while the watermark is a precise timestamp. Comparing
`filing_date > previous_watermark.date()` means a legitimately new filing
posted later the same calendar day as a previous run's watermark could be
missed by the next delta run (which starts strictly after that day). This is
a real, narrow gap tracked as a Technical Debt entry (PLAN.md), not silently
accepted — accession-number-keyed idempotency means the risk is *missing* a
same-day filing, never duplicating one.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from app.ai.model_router import ModelRouter
from app.core.distress_rules import match_rules
from app.core.types import (
    MONITORED_FORM_TYPES,
    CollectionType,
    DetectionMethod,
    FilingMonitorRunMode,
    FilingMonitorRunStatus,
    ProviderName,
)
from app.domain.alert import AlertEvent
from app.domain.filing_monitor_run import FilingMonitorRun, FilingMonitorRunCreate
from app.domain.research_evidence import ResearchEvidence, ResearchEvidenceCreate
from app.domain.sec_filing import SecFiling
from app.providers.base.http_client import ThrottledHttpClient
from app.providers.sec_edgar import normalizer as sec_normalizer
from app.providers.sec_edgar.provider import FilingIngestResult, FilingTextResult
from app.providers.sec_edgar.provider import fetch_filing_text as sec_fetch_filing_text
from app.providers.sec_edgar.provider import ingest_recent_filings as sec_ingest_recent_filings
from app.repositories import (
    collection_repository,
    filing_monitor_run_repository,
    issuer_repository,
    provenance_repository,
    raw_provider_payload_repository,
    research_evidence_repository,
    sec_filing_repository,
)
from app.services import alert_synthesis_service
from app.services.alert_synthesis_service import SourceDescription


class FetchFilingsFn(Protocol):
    def __call__(
        self,
        db: Session,
        http_client: ThrottledHttpClient,
        *,
        cik: int | str,
        forms: frozenset[str],
        since: date | None,
    ) -> list[FilingIngestResult]: ...


class FetchFilingTextFn(Protocol):
    def __call__(
        self, db: Session, http_client: ThrottledHttpClient, *, cik: int | str, filing: SecFiling
    ) -> FilingTextResult: ...


def describe_sec_source(db: Session, evidence: ResearchEvidence) -> SourceDescription:
    """The one place SEC-specific source formatting happens — injected into
    the provider-agnostic `alert_synthesis_service`, never hardcoded there.
    """
    if evidence.filing_id is None:
        return SourceDescription(
            phrase="a recent SEC filing",
            label="SEC EDGAR (source filing unavailable)",
            url=None,
            as_of_date=date.today(),
        )
    filing = sec_filing_repository.get_filing(db, evidence.filing_id)
    if filing is None:
        return SourceDescription(
            phrase="a recent SEC filing",
            label="SEC EDGAR (source filing unavailable)",
            url=None,
            as_of_date=date.today(),
        )
    return SourceDescription(
        phrase=f"a new {filing.form_type}",
        label=f"{filing.form_type} filed {filing.filing_date.isoformat()}, "
        f"Accession {filing.accession_no}",
        url=filing.primary_document_url,
        as_of_date=filing.filing_date,
    )


def _process_one_filing(
    db: Session,
    http_client: ThrottledHttpClient,
    *,
    cik: str,
    issuer_id: UUID,
    ingest_result: FilingIngestResult,
    fetch_filing_text_fn: FetchFilingTextFn,
) -> list[ResearchEvidence]:
    """Idempotent per filing: if evidence already exists for this filing
    (from an earlier attempt, successful or not), reuse it rather than
    re-fetching the document and re-matching rules — this is the actual
    duplicate-evidence guard, deliberately *not* keyed off
    `FilingIngestResult.filing_created` (which is `False` on every retry
    regardless of whether evidence was ever created, and would wrongly skip
    a filing that failed *before* evidence creation on a prior attempt).
    """
    filing = ingest_result.filing
    existing_evidence = research_evidence_repository.list_evidence_by_filing(db, filing.id)
    if existing_evidence:
        return existing_evidence

    text_result = fetch_filing_text_fn(db, http_client, cik=cik, filing=filing)
    matches = match_rules(
        form_type=filing.form_type, item_codes=ingest_result.item_codes, text=text_result.text
    )

    created: list[ResearchEvidence] = []
    payload_linked = False
    for match in matches:
        # One provenance row per matched rule — not one shared across every
        # match on this filing (see FilingTextResult's docstring for the
        # real `calculation_input` collision this avoids: a bundle with two
        # evidence items sharing one provenance_id violates
        # calculation_input's composite primary key the first time an alert
        # cites both). `raw_provider_payload.provenance_id` is a single
        # convenience back-pointer (PLAN.md 4.4), not one-per-provenance, so
        # it's only set once per filing (to the first match's provenance) —
        # every provenance row still carries the authoritative
        # `raw_payload_id` link in the other direction regardless.
        evidence_provenance = provenance_repository.create_provenance(
            db,
            sec_normalizer.normalize_filing_document_provenance(
                accession_no=filing.accession_no,
                filing_date=filing.filing_date,
                source_url=text_result.source_url,
                retrieved_at=text_result.retrieved_at,
                raw_payload_id=text_result.raw_payload_id,
            ),
        )
        if not payload_linked:
            raw_provider_payload_repository.link_provenance(
                db, text_result.raw_payload_id, evidence_provenance.id
            )
            payload_linked = True
        evidence = research_evidence_repository.create_evidence(
            db,
            ResearchEvidenceCreate(
                issuer_id=issuer_id,
                evidence_provider=ProviderName.SEC_EDGAR.value,
                source_type="sec_filing",
                filing_id=filing.id,
                evidence_type=match.evidence_type,
                severity=match.severity,
                source_section=None,
                source_item=match.source_item,
                matched_rule=match.rule_id,
                evidence_excerpt=match.excerpt,
                evidence_start_offset=match.start_offset or None,
                evidence_end_offset=match.end_offset or None,
                confidence=match.confidence,
                detection_method=DetectionMethod.DETERMINISTIC,
                provenance_id=evidence_provenance.id,
            ),
        )
        created.append(evidence)
    return created


@dataclass(frozen=True, slots=True)
class IssuerFilingProcessingResult:
    """Return shape of `process_issuer_filings` — filings found/processed
    for one issuer plus every `ResearchEvidence` row produced, so the
    caller (either `run_monitor`'s known-issuer loop or
    `app.services.market_discovery_service`'s newly-resolved-issuer path)
    can synthesize alerts and accumulate its own run-level counters.
    """

    filings_discovered: int
    filings_processed: int
    evidence: list[ResearchEvidence]


def process_issuer_filings(
    db: Session,
    http_client: ThrottledHttpClient,
    *,
    cik: str,
    issuer_id: UUID,
    since_date: date | None,
    fetch_filings_fn: FetchFilingsFn = sec_ingest_recent_filings,
    fetch_filing_text_fn: FetchFilingTextFn = sec_fetch_filing_text,
) -> IssuerFilingProcessingResult:
    """Fetch one issuer's recent SEC filings since `since_date` and run
    Layer 1 rule matching on each (extracted from `run_monitor`'s per-issuer
    loop body so `market_discovery_service` can reuse the exact same
    ingestion/evidence pipeline for a newly-resolved issuer — PLAN.md
    Milestone 7.5's "do not build separate business logic for historical
    and nightly/discovery processing"). Alert synthesis and commit/rollback
    boundaries stay with each caller, since watermark/run-counter semantics
    differ between the known-issuer monitor and market discovery.
    """
    ingest_results = fetch_filings_fn(
        db, http_client, cik=cik, forms=MONITORED_FORM_TYPES, since=since_date
    )
    evidence: list[ResearchEvidence] = []
    for ingest_result in ingest_results:
        evidence.extend(
            _process_one_filing(
                db,
                http_client,
                cik=cik,
                issuer_id=issuer_id,
                ingest_result=ingest_result,
                fetch_filing_text_fn=fetch_filing_text_fn,
            )
        )
    return IssuerFilingProcessingResult(
        filings_discovered=len(ingest_results),
        filings_processed=len(ingest_results),
        evidence=evidence,
    )


def run_monitor(
    db: Session,
    http_client: ThrottledHttpClient,
    router: ModelRouter | None,
    *,
    mode: FilingMonitorRunMode,
    backfill_days: int | None = None,
    environment: str,
    fetch_filings_fn: FetchFilingsFn = sec_ingest_recent_filings,
    fetch_filing_text_fn: FetchFilingTextFn = sec_fetch_filing_text,
) -> FilingMonitorRun:
    if mode is FilingMonitorRunMode.BACKFILL and not backfill_days:
        raise ValueError("backfill mode requires backfill_days")

    latest_successful = filing_monitor_run_repository.get_latest_successful_run(db)
    previous_watermark = latest_successful.resulting_watermark if latest_successful else None

    # This service manages its own commit/rollback boundaries — unlike the
    # rest of this codebase's repositories/services (which only flush and
    # let a FastAPI request's `get_db` dependency commit once at the end),
    # this is a long-running background job over many issuers. A later
    # issuer's failure must never roll back an earlier issuer's already-
    # successful filings/evidence/alerts, so each issuer's work is committed
    # durably before moving to the next, and a failure rolls back only that
    # issuer's partial writes (and restores the session to a usable state
    # for the next iteration — a failed flush leaves a SQLAlchemy session
    # unusable until rolled back).
    run = filing_monitor_run_repository.create_run(
        db,
        FilingMonitorRunCreate(
            mode=mode,
            previous_watermark=previous_watermark,
            backfill_lookback_days=backfill_days,
            is_backfill=(mode is FilingMonitorRunMode.BACKFILL),
        ),
    )
    db.commit()

    target_issuer_ids = collection_repository.list_issuer_ids_for_collection_types(
        db, [CollectionType.RESEARCH_UNIVERSE, CollectionType.BENCHMARK]
    )

    if mode is FilingMonitorRunMode.BASELINE:
        # No filings ingested at all — establishes a watermark without
        # flooding the UI with an issuer's entire filing history.
        completed_baseline = filing_monitor_run_repository.complete_run(
            db,
            run.id,
            status=FilingMonitorRunStatus.BASELINE_ESTABLISHED,
            resulting_watermark=datetime.now(UTC),
            issuers_checked=len(target_issuer_ids),
            filings_discovered=0,
            filings_processed=0,
            alerts_created=0,
            errors_count=0,
            error_summary=None,
        )
        db.commit()
        return completed_baseline

    since_date: date | None
    if mode is FilingMonitorRunMode.DELTA:
        since_date = previous_watermark.date() if previous_watermark else None
    else:
        assert backfill_days is not None
        since_date = date.today() - timedelta(days=backfill_days)

    filings_discovered = 0
    filings_processed = 0
    alerts_created = 0
    errors_count = 0
    error_messages: list[str] = []

    for issuer_id in target_issuer_ids:
        issuer = issuer_repository.get_issuer(db, issuer_id)
        if issuer is None or issuer.cik is None:
            # Synthetic/non-SEC-filer issuers have nothing to monitor — not
            # an error, just out of scope for this provider.
            continue

        try:
            processing_result = process_issuer_filings(
                db,
                http_client,
                cik=issuer.cik,
                issuer_id=issuer_id,
                since_date=since_date,
                fetch_filings_fn=fetch_filings_fn,
                fetch_filing_text_fn=fetch_filing_text_fn,
            )
            filings_discovered += processing_result.filings_discovered
            filings_processed += processing_result.filings_processed
            issuer_evidence = processing_result.evidence

            if issuer_evidence:
                new_alerts: list[AlertEvent] = (
                    alert_synthesis_service.synthesize_alerts_from_evidence(
                        db,
                        evidence=issuer_evidence,
                        describe_source=lambda e: describe_sec_source(db, e),
                        router=router,
                        environment=environment,
                        is_backfill=(mode is FilingMonitorRunMode.BACKFILL),
                        filing_monitor_run_id=run.id,
                    )
                )
                alerts_created += len(new_alerts)
            db.commit()
        except Exception as exc:  # noqa: BLE001 - deliberate per-issuer isolation boundary
            db.rollback()
            errors_count += 1
            error_messages.append(f"issuer {issuer_id} (CIK {issuer.cik}): {exc}")
            continue

    status = (
        FilingMonitorRunStatus.SUCCESS
        if errors_count == 0
        else FilingMonitorRunStatus.COMPLETED_WITH_ERRORS
    )
    # Watermark only advances on a fully successful run (PLAN.md 24.5) — a
    # run with errors leaves it untouched so the next run safely re-checks
    # the same window; already-ingested filings/evidence/alerts are never
    # lost, just not re-created (idempotent by accession_no/bundle_key).
    resulting_watermark = datetime.now(UTC) if errors_count == 0 else previous_watermark

    completed = filing_monitor_run_repository.complete_run(
        db,
        run.id,
        status=status,
        resulting_watermark=resulting_watermark,
        issuers_checked=len(target_issuer_ids),
        filings_discovered=filings_discovered,
        filings_processed=filings_processed,
        alerts_created=alerts_created,
        errors_count=errors_count,
        error_summary="; ".join(error_messages) if error_messages else None,
    )
    db.commit()
    return completed
