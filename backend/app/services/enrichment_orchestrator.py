"""Automatic, reusable per-issuer/provider enrichment orchestrator (PLAN.md
Milestone 7.5 sections 7-13).

Runs for **every** issuer this pipeline touches — newly discovered
(`verified_new`) and already-known (`matched_existing`) alike. There is no
"only run for new issuers" gate: `issuer_enrichment_status` (never
checked / stale / retry-due / forced) is what decides whether a provider
actually runs, so a nightly delta pass over already-enriched issuers stays
cheap while a genuinely stale or never-attempted issuer/provider pair still
gets picked up. The same `enrich_issuer` function backs the automatic call
at the end of `market_discovery_service`'s per-candidate loop, a standalone
retry/backfill sweep (`app.scripts.run_enrichment_orchestrator`), and any
future nightly cron — one code path, not separate historical/nightly logic
(PLAN.md Milestone 7.5 section 1/19).

Each provider call is independently try/except-isolated: one provider's
failure is recorded as `failed_retryable` and never blocks or rolls back
another provider's success for the same issuer (PLAN.md Milestone 7.5
section 19/20).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from app.ai.model_router import ModelRouter
from app.core.types import (
    ISSUER_LEVEL_ENRICHMENT_PROVIDERS,
    EnrichmentStatus,
    ProviderName,
)
from app.domain.enrichment_status import IssuerEnrichmentStatus, IssuerEnrichmentStatusUpdate
from app.providers.base.http_client import ThrottledHttpClient
from app.providers.openfigi.provider import search_and_ingest_issuer_bonds
from app.repositories import (
    issuer_enrichment_status_repository,
    issuer_repository,
    research_evidence_repository,
)
from app.services import (
    alert_synthesis_service,
    court_docket_service,
    universe_classification_service,
)
from app.services.court_docket_service import DOCKET_RELEVANT_EVIDENCE_TYPES
from app.services.filing_monitor_service import (
    IssuerFilingProcessingResult,
    describe_sec_source,
    process_issuer_filings,
)

# Per-provider staleness policy: how long a `complete`/`no_data` status stays
# fresh before the orchestrator re-runs that provider for an issuer it
# already knows about. SEC is cheap to re-check often; CourtListener is
# rate-limited and expensive (PLAN.md TD-012 context); OpenFIGI identity
# rarely changes once resolved. `None` reserved for "always safe to
# re-check" is intentionally unused today — every provider here has a real
# cost, so every provider gets a real TTL.
PROVIDER_STALENESS_TTL: dict[ProviderName, timedelta] = {
    ProviderName.SEC_EDGAR: timedelta(hours=12),
    ProviderName.COURTLISTENER: timedelta(days=7),
    ProviderName.OPENFIGI: timedelta(days=30),
}

# How long a status may sit in a "needs a human"/"couldn't check" state
# before the orchestrator tries again on its own — config may have changed
# (a token got added), or a first attempt may have hit a transient issue.
RECHECK_TTL_FOR_UNRESOLVED_STATES = timedelta(days=3)

# A `running` status older than this is treated as stuck (e.g. the process
# that set it crashed) and is safe to retry rather than wait on forever.
STUCK_RUNNING_TTL = timedelta(hours=1)

# First-ever SEC check for a `matched_existing` issuer with no prior
# enrichment status bounds how far back to look, rather than an unbounded
# full-history ingest the orchestrator wasn't asked to perform.
SEC_FIRST_CHECK_LOOKBACK_DAYS = 90


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


def _should_run(
    status: IssuerEnrichmentStatus | None, *, ttl: timedelta, force: bool, now: datetime
) -> bool:
    if force or status is None:
        return True
    if status.status is EnrichmentStatus.FAILED_RETRYABLE:
        return status.next_retry_at is None or status.next_retry_at <= now
    if status.status is EnrichmentStatus.RUNNING:
        return status.last_attempt_at is None or (now - status.last_attempt_at) > STUCK_RUNNING_TTL
    if status.status in (EnrichmentStatus.COMPLETE, EnrichmentStatus.NO_DATA):
        return status.last_success_at is None or (now - status.last_success_at) > ttl
    if status.status in (
        EnrichmentStatus.AMBIGUOUS,
        EnrichmentStatus.MANUAL_REVIEW_REQUIRED,
        EnrichmentStatus.UNAVAILABLE,
    ):
        return (
            status.last_attempt_at is None
            or (now - status.last_attempt_at) > RECHECK_TTL_FOR_UNRESOLVED_STATES
        )
    # FAILED_PERMANENT, BLOCKED_ENTITLEMENT, UNSUPPORTED never auto-retry.
    return False


@dataclass(frozen=True, slots=True)
class EnrichmentClients:
    """Per-provider HTTP clients — each optional, since a provider without
    its required configuration (e.g. no `COURTLISTENER_API_TOKEN`) stays
    fully operational at the app level, just marked `unavailable` for that
    one provider (PLAN.md's established "app stays operational without an
    optional credential" pattern)."""

    sec: ThrottledHttpClient | None
    courtlistener: ThrottledHttpClient | None
    openfigi: ThrottledHttpClient | None


def enrich_issuer(
    db: Session,
    issuer_id: UUID,
    clients: EnrichmentClients,
    router: ModelRouter | None,
    *,
    environment: str,
    force: bool = False,
    discovery_run_id: UUID | None = None,
    process_issuer_filings_fn: ProcessIssuerFilingsFn = process_issuer_filings,
) -> dict[ProviderName, IssuerEnrichmentStatus]:
    issuer = issuer_repository.get_issuer(db, issuer_id)
    if issuer is None:
        raise ValueError(f"issuer {issuer_id} not found")

    now = datetime.now(UTC)
    results: dict[ProviderName, IssuerEnrichmentStatus] = {}

    for provider in ISSUER_LEVEL_ENRICHMENT_PROVIDERS:
        current = issuer_enrichment_status_repository.get_status(
            db, issuer_id=issuer_id, provider=provider
        )
        if not _should_run(current, ttl=PROVIDER_STALENESS_TTL[provider], force=force, now=now):
            if current is not None:
                results[provider] = current
            continue

        try:
            if provider is ProviderName.SEC_EDGAR:
                update = _enrich_sec(
                    db,
                    issuer_id,
                    issuer.cik,
                    clients.sec,
                    current,
                    router,
                    environment,
                    now=now,
                    discovery_run_id=discovery_run_id,
                    process_issuer_filings_fn=process_issuer_filings_fn,
                )
            elif provider is ProviderName.OPENFIGI:
                update = _enrich_openfigi(
                    db, issuer_id, issuer.legal_name, clients.openfigi, now=now
                )
            else:
                update = _enrich_courtlistener(
                    db,
                    issuer_id,
                    issuer.legal_name,
                    clients.courtlistener,
                    router,
                    environment,
                    now=now,
                    discovery_run_id=discovery_run_id,
                )
        except Exception as exc:  # noqa: BLE001 - per-provider isolation boundary
            db.rollback()
            update = IssuerEnrichmentStatusUpdate(
                status=EnrichmentStatus.FAILED_RETRYABLE,
                last_attempt_at=now,
                next_retry_at=now + timedelta(hours=6),
                error_classification=type(exc).__name__,
            )

        results[provider] = issuer_enrichment_status_repository.record_attempt_outcome(
            db, issuer_id=issuer_id, provider=provider, update=update
        )
        db.commit()

    return results


def _enrich_sec(
    db: Session,
    issuer_id: UUID,
    cik: str | None,
    http_client: ThrottledHttpClient | None,
    current: IssuerEnrichmentStatus | None,
    router: ModelRouter | None,
    environment: str,
    *,
    now: datetime,
    discovery_run_id: UUID | None = None,
    process_issuer_filings_fn: ProcessIssuerFilingsFn = process_issuer_filings,
) -> IssuerEnrichmentStatusUpdate:
    """Re-checks an issuer's SEC filings (bounded to
    `SEC_FIRST_CHECK_LOOKBACK_DAYS` on a first-ever check, or since its own
    last success otherwise) independent of whatever window triggered this
    issuer's discovery. Any evidence found here flows through the exact
    same `alert_synthesis_service`/`universe_classification_service` calls
    `market_discovery_service` uses for discovery-triggered evidence — a
    real gap found and fixed during Milestone 7.5 live validation (a
    `matched_existing` issuer's enrichment-triggered historical SEC
    re-check was creating real `research_evidence` rows that never became
    alerts, since this function originally only called
    `process_issuer_filings` and stopped there)."""
    if http_client is None:
        return IssuerEnrichmentStatusUpdate(
            status=EnrichmentStatus.UNAVAILABLE,
            last_attempt_at=now,
            error_classification="sec_http_client_not_configured",
        )
    if cik is None:
        return IssuerEnrichmentStatusUpdate(
            status=EnrichmentStatus.UNSUPPORTED,
            last_attempt_at=now,
            error_classification="issuer_has_no_cik",
        )

    since_date: date | None = (
        current.last_success_at.date()
        if current is not None and current.last_success_at is not None
        else now.date() - timedelta(days=SEC_FIRST_CHECK_LOOKBACK_DAYS)
    )
    result = process_issuer_filings_fn(
        db, http_client, cik=cik, issuer_id=issuer_id, since_date=since_date
    )
    if result.evidence:
        alert_synthesis_service.synthesize_alerts_from_evidence(
            db,
            evidence=result.evidence,
            describe_source=lambda e: describe_sec_source(db, e),
            router=router,
            environment=environment,
            is_backfill=True,
            discovery_run_id=discovery_run_id,
        )
        universe_classification_service.classify_issuer(db, issuer_id, result.evidence)
    status = (
        EnrichmentStatus.COMPLETE if result.filings_discovered > 0 else EnrichmentStatus.NO_DATA
    )
    return IssuerEnrichmentStatusUpdate(
        status=status,
        last_attempt_at=now,
        last_success_at=now,
        records_found=result.filings_discovered,
    )


def _enrich_openfigi(
    db: Session,
    issuer_id: UUID,
    issuer_legal_name: str,
    http_client: ThrottledHttpClient | None,
    *,
    now: datetime,
) -> IssuerEnrichmentStatusUpdate:
    if http_client is None:
        return IssuerEnrichmentStatusUpdate(
            status=EnrichmentStatus.UNAVAILABLE,
            last_attempt_at=now,
            error_classification="openfigi_http_client_not_configured",
        )

    result = search_and_ingest_issuer_bonds(
        db, http_client, issuer_id=issuer_id, query=issuer_legal_name
    )
    status = EnrichmentStatus.COMPLETE if result.bonds else EnrichmentStatus.NO_DATA
    return IssuerEnrichmentStatusUpdate(
        status=status,
        last_attempt_at=now,
        last_success_at=now,
        records_found=len(result.bonds),
    )


def _enrich_courtlistener(
    db: Session,
    issuer_id: UUID,
    issuer_legal_name: str,
    http_client: ThrottledHttpClient | None,
    router: ModelRouter | None,
    environment: str,
    *,
    now: datetime,
    discovery_run_id: UUID | None = None,
) -> IssuerEnrichmentStatusUpdate:
    if http_client is None:
        return IssuerEnrichmentStatusUpdate(
            status=EnrichmentStatus.UNAVAILABLE,
            last_attempt_at=now,
            error_classification="courtlistener_http_client_not_configured",
        )

    has_relevant_evidence = any(
        e.evidence_type in DOCKET_RELEVANT_EVIDENCE_TYPES
        for e in research_evidence_repository.list_evidence(db, issuer_id=issuer_id, page_size=50)
    )
    if not has_relevant_evidence:
        return IssuerEnrichmentStatusUpdate(
            status=EnrichmentStatus.UNSUPPORTED,
            last_attempt_at=now,
            error_classification="no_docket_relevant_evidence_on_file",
        )

    result = court_docket_service.attempt_auto_link(
        db,
        http_client,
        router,
        issuer_id=issuer_id,
        issuer_legal_name=issuer_legal_name,
        environment=environment,
        discovery_run_id=discovery_run_id,
    )
    outcome_to_status = {
        "verified_docket_match": EnrichmentStatus.COMPLETE,
        "checked_no_relevant_docket": EnrichmentStatus.NO_DATA,
        "ambiguous_manual_review": EnrichmentStatus.MANUAL_REVIEW_REQUIRED,
        "unavailable": EnrichmentStatus.UNAVAILABLE,
        "retryable_failure": EnrichmentStatus.FAILED_RETRYABLE,
    }
    status = outcome_to_status[result.outcome.value]
    is_success = status in (EnrichmentStatus.COMPLETE, EnrichmentStatus.NO_DATA)
    records_found = result.sync_result.entries_discovered if result.sync_result else 0
    return IssuerEnrichmentStatusUpdate(
        status=status,
        last_attempt_at=now,
        last_success_at=now if is_success else None,
        records_found=records_found,
    )
