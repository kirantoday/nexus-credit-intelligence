"""Repository for `market_discovery_run` / `market_discovery_candidate`
(PLAN.md Milestone 7.5).

See `provenance_repository.py`'s module docstring for this project's
repository conventions (function-style, domain objects only, flush-not-commit).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.types import (
    FilingMonitorRunMode,
    FilingMonitorRunStatus,
    MarketDiscoveryResolutionOutcome,
)
from app.domain.market_discovery import (
    MarketDiscoveryCandidate,
    MarketDiscoveryCandidateCreate,
    MarketDiscoveryRun,
    MarketDiscoveryRunCreate,
)
from app.models.market_discovery_candidate import MarketDiscoveryCandidate as CandidateModel
from app.models.market_discovery_run import MarketDiscoveryRun as RunModel


def _run_to_domain(row: RunModel) -> MarketDiscoveryRun:
    return MarketDiscoveryRun(
        id=row.id,
        started_at=row.started_at,
        completed_at=row.completed_at,
        status=FilingMonitorRunStatus(row.status),
        mode=FilingMonitorRunMode(row.mode),
        window_start_date=row.window_start_date,
        window_end_date=row.window_end_date,
        previous_watermark=row.previous_watermark,
        resulting_watermark=row.resulting_watermark,
        queries_executed=row.queries_executed,
        filings_examined=row.filings_examined,
        candidate_filings=row.candidate_filings,
        issuers_resolved_existing=row.issuers_resolved_existing,
        issuers_resolved_new=row.issuers_resolved_new,
        issuers_ambiguous=row.issuers_ambiguous,
        issuers_rejected=row.issuers_rejected,
        evidence_created=row.evidence_created,
        alerts_created=row.alerts_created,
        errors_count=row.errors_count,
        error_summary=row.error_summary,
        created_at=row.created_at,
    )


def create_run(db: Session, data: MarketDiscoveryRunCreate) -> MarketDiscoveryRun:
    row = RunModel(
        status=FilingMonitorRunStatus.RUNNING.value,
        mode=data.mode.value,
        window_start_date=data.window_start_date,
        window_end_date=data.window_end_date,
        previous_watermark=data.previous_watermark,
    )
    db.add(row)
    db.flush()
    db.refresh(row)
    return _run_to_domain(row)


def complete_run(
    db: Session,
    run_id: UUID,
    *,
    status: FilingMonitorRunStatus,
    resulting_watermark: datetime | None,
    queries_executed: int,
    filings_examined: int,
    candidate_filings: int,
    issuers_resolved_existing: int,
    issuers_resolved_new: int,
    issuers_ambiguous: int,
    issuers_rejected: int,
    evidence_created: int,
    alerts_created: int,
    errors_count: int,
    error_summary: str | None,
) -> MarketDiscoveryRun:
    row = db.get(RunModel, run_id)
    if row is None:
        raise ValueError(f"market_discovery_run {run_id} not found")
    row.status = status.value
    row.resulting_watermark = resulting_watermark
    row.queries_executed = queries_executed
    row.filings_examined = filings_examined
    row.candidate_filings = candidate_filings
    row.issuers_resolved_existing = issuers_resolved_existing
    row.issuers_resolved_new = issuers_resolved_new
    row.issuers_ambiguous = issuers_ambiguous
    row.issuers_rejected = issuers_rejected
    row.evidence_created = evidence_created
    row.alerts_created = alerts_created
    row.errors_count = errors_count
    row.error_summary = error_summary
    row.completed_at = datetime.now(tz=row.started_at.tzinfo)
    db.flush()
    db.refresh(row)
    return _run_to_domain(row)


def get_latest_successful_run(db: Session) -> MarketDiscoveryRun | None:
    """Mirrors `filing_monitor_run_repository.get_latest_successful_run`: only
    `success`/`baseline_established` runs advance the watermark; an errored
    run must never be treated as "latest successful" regardless of recency.
    """
    success_statuses = (
        FilingMonitorRunStatus.SUCCESS.value,
        FilingMonitorRunStatus.BASELINE_ESTABLISHED.value,
    )
    stmt = (
        select(RunModel)
        .where(RunModel.status.in_(success_statuses))
        .order_by(RunModel.completed_at.desc())
        .limit(1)
    )
    row = db.execute(stmt).scalars().first()
    return _run_to_domain(row) if row is not None else None


def list_runs(db: Session, *, page: int = 1, page_size: int = 20) -> list[MarketDiscoveryRun]:
    stmt = (
        select(RunModel)
        .order_by(RunModel.started_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = db.execute(stmt).scalars().all()
    return [_run_to_domain(row) for row in rows]


def _candidate_to_domain(row: CandidateModel) -> MarketDiscoveryCandidate:
    return MarketDiscoveryCandidate(
        id=row.id,
        discovery_run_id=row.discovery_run_id,
        cik=row.cik,
        accession_no=row.accession_no,
        form_type=row.form_type,
        file_date=row.file_date,
        matched_query=row.matched_query,
        sec_items=row.sec_items,
        resolution_outcome=MarketDiscoveryResolutionOutcome(row.resolution_outcome),
        resolution_reason=row.resolution_reason,
        issuer_id=row.issuer_id,
        layer1_matched=row.layer1_matched,
        evidence_created=row.evidence_created,
        provenance_id=row.provenance_id,
        rule_version=row.rule_version,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def get_candidate_by_filing(
    db: Session, *, cik: str, accession_no: str
) -> MarketDiscoveryCandidate | None:
    """The idempotency lookup: has this exact `(cik, accession_no)` filing
    ever been examined? Source identity/dedup only — callers decide whether
    an existing row's `rule_version` warrants reprocessing (see
    `upsert_candidate`), never a "skip unconditionally" gate on its own.
    """
    stmt = select(CandidateModel).where(
        CandidateModel.cik == cik, CandidateModel.accession_no == accession_no
    )
    row = db.execute(stmt).scalars().first()
    return _candidate_to_domain(row) if row is not None else None


def upsert_candidate(db: Session, data: MarketDiscoveryCandidateCreate) -> MarketDiscoveryCandidate:
    """Insert a new candidate, or update an existing `(cik, accession_no)`
    row in place when reprocessing is requested — never a second row for
    the same filing (unique constraint on `(cik, accession_no)`).
    """
    existing = (
        db.execute(
            select(CandidateModel).where(
                CandidateModel.cik == data.cik, CandidateModel.accession_no == data.accession_no
            )
        )
        .scalars()
        .first()
    )
    if existing is not None:
        existing.discovery_run_id = data.discovery_run_id
        existing.form_type = data.form_type
        existing.file_date = data.file_date
        existing.matched_query = data.matched_query
        existing.sec_items = data.sec_items
        existing.resolution_outcome = data.resolution_outcome.value
        existing.resolution_reason = data.resolution_reason
        existing.issuer_id = data.issuer_id
        existing.layer1_matched = data.layer1_matched
        existing.evidence_created = data.evidence_created
        existing.provenance_id = data.provenance_id
        existing.rule_version = data.rule_version
        existing.updated_at = datetime.now(tz=existing.created_at.tzinfo)
        db.flush()
        db.refresh(existing)
        return _candidate_to_domain(existing)

    row = CandidateModel(
        discovery_run_id=data.discovery_run_id,
        cik=data.cik,
        accession_no=data.accession_no,
        form_type=data.form_type,
        file_date=data.file_date,
        matched_query=data.matched_query,
        sec_items=data.sec_items,
        resolution_outcome=data.resolution_outcome.value,
        resolution_reason=data.resolution_reason,
        issuer_id=data.issuer_id,
        layer1_matched=data.layer1_matched,
        evidence_created=data.evidence_created,
        provenance_id=data.provenance_id,
        rule_version=data.rule_version,
    )
    db.add(row)
    db.flush()
    db.refresh(row)
    return _candidate_to_domain(row)
