"""Assembles Overnight Distress Filing Monitor API responses (PLAN.md 24.5, 24.8).

Read-only assembly for the API surface — distinct from
`app.services.filing_monitor_service`, which is the write-side ingestion
orchestrator (`run_monitor`). This module never ingests anything; it only
joins already-persisted runs/filings/evidence/alerts with issuer/universe
names for display, and handles the acknowledge/dismiss/manual-trigger
actions.
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy.orm import Session

from app.ai.providers.base import LLMProvider
from app.core.types import (
    AlertStatus,
    CollectionType,
    DetectionMethod,
    EvidenceSeverity,
    EvidenceType,
    FilingMonitorRunMode,
    ReviewStatus,
)
from app.domain.alert import AlertEvent
from app.domain.filing_monitor_run import FilingMonitorRun
from app.domain.research_evidence import ResearchEvidence
from app.providers.base.http_client import ThrottledHttpClient
from app.repositories import (
    alert_repository,
    collection_repository,
    filing_monitor_run_repository,
    issuer_repository,
    research_evidence_repository,
    sec_filing_repository,
)
from app.schemas.filing_monitor import (
    AlertEvidenceDetail,
    AlertRow,
    AlertsPage,
    FilingMonitorRunRow,
    MorningBriefSummary,
    ResearchEvidenceRow,
    SecFilingRow,
    SecFilingsResponse,
    SeverityCounts,
)
from app.services import filing_monitor_service


def _run_to_row(run: FilingMonitorRun) -> FilingMonitorRunRow:
    return FilingMonitorRunRow(
        id=run.id,
        started_at=run.started_at,
        completed_at=run.completed_at,
        status=run.status,
        mode=run.mode,
        previous_watermark=run.previous_watermark,
        resulting_watermark=run.resulting_watermark,
        issuers_checked=run.issuers_checked,
        filings_discovered=run.filings_discovered,
        filings_processed=run.filings_processed,
        alerts_created=run.alerts_created,
        errors_count=run.errors_count,
        error_summary=run.error_summary,
        backfill_lookback_days=run.backfill_lookback_days,
        is_backfill=run.is_backfill,
    )


def list_runs(db: Session, *, page: int = 1, page_size: int = 20) -> list[FilingMonitorRunRow]:
    runs = filing_monitor_run_repository.list_runs(db, page=page, page_size=page_size)
    return [_run_to_row(r) for r in runs]


def get_latest_successful_run(db: Session) -> FilingMonitorRunRow | None:
    run = filing_monitor_run_repository.get_latest_successful_run(db)
    return _run_to_row(run) if run is not None else None


def list_new_filings(db: Session, *, since_run_id: UUID | None = None) -> SecFilingsResponse:
    """Filings discovered since a given run's watermark — defaults to the
    latest successful run when `since_run_id` isn't given."""
    if since_run_id is not None:
        target_run = filing_monitor_run_repository.get_run(db, since_run_id)
        resolved_run_id: UUID | None = since_run_id
    else:
        target_run = filing_monitor_run_repository.get_latest_successful_run(db)
        resolved_run_id = target_run.id if target_run else None

    since_date = (
        target_run.previous_watermark.date()
        if target_run is not None and target_run.previous_watermark is not None
        else None
    )

    filings = sec_filing_repository.list_filings_since(db, since=since_date)
    rows: list[SecFilingRow] = []
    for filing in filings:
        issuer = issuer_repository.get_issuer(db, filing.issuer_id)
        rows.append(
            SecFilingRow(
                id=filing.id,
                issuer_id=filing.issuer_id,
                issuer_legal_name=issuer.legal_name if issuer else "Unknown issuer",
                accession_no=filing.accession_no,
                form_type=filing.form_type,
                filing_date=filing.filing_date,
                period_of_report=filing.period_of_report,
                is_amendment=filing.is_amendment,
                primary_document_url=filing.primary_document_url,
            )
        )
    return SecFilingsResponse(filings=rows, since_run_id=resolved_run_id)


def _evidence_to_row(db: Session, evidence: ResearchEvidence) -> ResearchEvidenceRow:
    issuer = issuer_repository.get_issuer(db, evidence.issuer_id)
    return ResearchEvidenceRow(
        id=evidence.id,
        issuer_id=evidence.issuer_id,
        issuer_legal_name=issuer.legal_name if issuer else "Unknown issuer",
        evidence_provider=evidence.evidence_provider,
        source_type=evidence.source_type,
        filing_id=evidence.filing_id,
        docket_entry_id=evidence.docket_entry_id,
        evidence_type=evidence.evidence_type,
        severity=evidence.severity,
        source_section=evidence.source_section,
        source_item=evidence.source_item,
        matched_rule=evidence.matched_rule,
        evidence_excerpt=evidence.evidence_excerpt,
        confidence=evidence.confidence,
        detection_method=evidence.detection_method,
        review_status=evidence.review_status,
        created_at=evidence.created_at,
    )


def list_evidence(
    db: Session,
    *,
    issuer_id: UUID | None = None,
    evidence_provider: str | None = None,
    evidence_type: EvidenceType | None = None,
    severity: EvidenceSeverity | None = None,
    review_status: ReviewStatus | None = None,
    page: int = 1,
    page_size: int = 50,
) -> list[ResearchEvidenceRow]:
    evidence = research_evidence_repository.list_evidence(
        db,
        issuer_id=issuer_id,
        evidence_provider=evidence_provider,
        evidence_type=evidence_type,
        severity=severity,
        review_status=review_status,
        page=page,
        page_size=page_size,
    )
    return [_evidence_to_row(db, e) for e in evidence]


def _alert_to_row(db: Session, alert: AlertEvent) -> AlertRow:
    issuer = issuer_repository.get_issuer(db, alert.issuer_id)
    universes = collection_repository.list_collections_for_issuer(db, alert.issuer_id)
    return AlertRow(
        id=alert.id,
        issuer_id=alert.issuer_id,
        issuer_legal_name=issuer.legal_name if issuer else "Unknown issuer",
        issuer_ticker=issuer.ticker if issuer else None,
        universe_names=[c.name for c in universes],
        category=alert.category,
        severity=alert.severity,
        headline=alert.headline,
        explanation=alert.explanation,
        evidence_ids=alert.evidence_ids,
        detection_method=alert.detection_method,
        ai_assisted=alert.ai_assisted,
        confidence=alert.confidence,
        primary_evidence_provider=alert.primary_evidence_provider,
        primary_source_label=alert.primary_source_label,
        primary_source_url=alert.primary_source_url,
        as_of_date=alert.as_of_date,
        triggered_at=alert.triggered_at,
        status=alert.status,
        acknowledged_at=alert.acknowledged_at,
        acknowledged_by=alert.acknowledged_by,
        dismissed_at=alert.dismissed_at,
        dismissed_by=alert.dismissed_by,
        dismissal_reason=alert.dismissal_reason,
        is_backfill=alert.is_backfill,
    )


def list_alerts(
    db: Session,
    *,
    issuer_id: UUID | None = None,
    universe_id: UUID | None = None,
    severity: EvidenceSeverity | None = None,
    category: str | None = None,
    evidence_provider: str | None = None,
    status: AlertStatus | None = None,
    detection_method: DetectionMethod | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = 1,
    page_size: int = 50,
) -> AlertsPage:
    scoped_issuer_id = issuer_id
    if universe_id is not None:
        # Filtering by universe means "issuer must be a member of this
        # collection" — resolved to a concrete issuer_id set (this
        # milestone's Research Universes are small, tens of issuers at
        # most, so materializing the set is cheap). If both `issuer_id` and
        # `universe_id` are given and disagree, `issuer_id` wins (the more
        # specific filter) — matched to `alert_repository.list_alerts`'s
        # single `issuer_id` parameter shape.
        member_ids = {
            issuer.id
            for issuer, _m in collection_repository.list_issuers_for_collection(db, universe_id)
        }
        if issuer_id is not None and issuer_id not in member_ids:
            return AlertsPage(alerts=[], total=0, page=page, page_size=page_size)
        if issuer_id is None and len(member_ids) == 1:
            scoped_issuer_id = next(iter(member_ids))
        elif issuer_id is None and not member_ids:
            return AlertsPage(alerts=[], total=0, page=page, page_size=page_size)
        elif issuer_id is None:
            # Multiple issuers in the universe: filter client-request-shape
            # not supported by the single-issuer repository filter — fetch
            # unfiltered-by-issuer and post-filter by membership instead.
            scoped_issuer_id = None

    alerts, total = alert_repository.list_alerts(
        db,
        issuer_id=scoped_issuer_id,
        severity=severity,
        category=category,
        evidence_provider=evidence_provider,
        status=status,
        detection_method=detection_method,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )

    if universe_id is not None and issuer_id is None and scoped_issuer_id is None:
        member_ids = {
            issuer.id
            for issuer, _m in collection_repository.list_issuers_for_collection(db, universe_id)
        }
        alerts = [a for a in alerts if a.issuer_id in member_ids]
        total = len(alerts)

    rows = [_alert_to_row(db, a) for a in alerts]
    return AlertsPage(alerts=rows, total=total, page=page, page_size=page_size)


def get_alert_evidence_detail(db: Session, alert_id: UUID) -> AlertEvidenceDetail | None:
    alert = alert_repository.get_alert(db, alert_id)
    if alert is None:
        return None
    evidence = research_evidence_repository.list_evidence_by_ids(db, alert.evidence_ids)
    return AlertEvidenceDetail(
        alert=_alert_to_row(db, alert),
        evidence=[_evidence_to_row(db, e) for e in evidence],
    )


def acknowledge_alert(db: Session, alert_id: UUID, *, acknowledged_by: str | None) -> AlertRow:
    alert = alert_repository.acknowledge_alert(db, alert_id, acknowledged_by=acknowledged_by)
    return _alert_to_row(db, alert)


def dismiss_alert(
    db: Session, alert_id: UUID, *, dismissed_by: str | None, dismissal_reason: str | None
) -> AlertRow:
    alert = alert_repository.dismiss_alert(
        db, alert_id, dismissed_by=dismissed_by, dismissal_reason=dismissal_reason
    )
    return _alert_to_row(db, alert)


def get_morning_brief(db: Session) -> MorningBriefSummary:
    latest_successful = filing_monitor_run_repository.get_latest_successful_run(db)
    all_runs = filing_monitor_run_repository.list_runs(db, page_size=1)
    latest_run = all_runs[0] if all_runs else None

    universes_monitored = len(
        collection_repository.list_collections(db, collection_type=CollectionType.RESEARCH_UNIVERSE)
    ) + len(collection_repository.list_collections(db, collection_type=CollectionType.BENCHMARK))
    issuers_monitored = len(
        collection_repository.list_issuer_ids_for_collection_types(
            db, [CollectionType.RESEARCH_UNIVERSE, CollectionType.BENCHMARK]
        )
    )

    alerts, total = alert_repository.list_alerts(db, page=1, page_size=500)
    high = sum(1 for a in alerts if a.severity is EvidenceSeverity.HIGH)
    medium = sum(1 for a in alerts if a.severity is EvidenceSeverity.MEDIUM)
    low = sum(1 for a in alerts if a.severity is EvidenceSeverity.LOW)
    ai_assisted = sum(1 for a in alerts if a.ai_assisted)

    return MorningBriefSummary(
        last_successful_run=_run_to_row(latest_successful) if latest_successful else None,
        latest_run=_run_to_row(latest_run) if latest_run else None,
        universes_monitored=universes_monitored,
        issuers_monitored=issuers_monitored,
        new_evidence_discovered=(latest_run.filings_discovered if latest_run else 0),
        alerts_total=total,
        alerts_by_severity=SeverityCounts(high=high, medium=medium, low=low),
        deterministic_alert_count=total - ai_assisted,
        ai_assisted_alert_count=ai_assisted,
        failures_count=(latest_run.errors_count if latest_run else 0),
        no_new_alerts=(total == 0),
    )


def trigger_manual_run(
    db: Session,
    *,
    mode: FilingMonitorRunMode,
    backfill_days: int | None,
    environment: str,
    sec_user_agent: str,
    llm: LLMProvider | None,
) -> FilingMonitorRunRow:
    """Admin/demo-only manual run trigger — the route layer is responsible
    for the non-production access gate (PLAN.md 24.8); this function just
    runs the same pipeline the script uses."""
    http_client = ThrottledHttpClient(user_agent=sec_user_agent)
    try:
        run = filing_monitor_service.run_monitor(
            db,
            http_client,
            llm,
            mode=mode,
            backfill_days=backfill_days,
            environment=environment,
        )
    finally:
        http_client.close()
    return _run_to_row(run)
