"""Repository for `filing_monitor_run` (PLAN.md section 24.5).

See `provenance_repository.py`'s module docstring for this project's
repository conventions (function-style, domain objects only, flush-not-commit).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.types import FilingMonitorRunMode, FilingMonitorRunStatus
from app.domain.filing_monitor_run import FilingMonitorRun, FilingMonitorRunCreate
from app.models.filing_monitor_run import FilingMonitorRun as FilingMonitorRunModel


def _to_domain(row: FilingMonitorRunModel) -> FilingMonitorRun:
    return FilingMonitorRun(
        id=row.id,
        started_at=row.started_at,
        completed_at=row.completed_at,
        status=FilingMonitorRunStatus(row.status),
        mode=FilingMonitorRunMode(row.mode),
        previous_watermark=row.previous_watermark,
        resulting_watermark=row.resulting_watermark,
        issuers_checked=row.issuers_checked,
        filings_discovered=row.filings_discovered,
        filings_processed=row.filings_processed,
        alerts_created=row.alerts_created,
        errors_count=row.errors_count,
        error_summary=row.error_summary,
        backfill_lookback_days=row.backfill_lookback_days,
        is_backfill=row.is_backfill,
        created_at=row.created_at,
    )


def create_run(db: Session, data: FilingMonitorRunCreate) -> FilingMonitorRun:
    row = FilingMonitorRunModel(
        status=FilingMonitorRunStatus.RUNNING.value,
        mode=data.mode.value,
        previous_watermark=data.previous_watermark,
        backfill_lookback_days=data.backfill_lookback_days,
        is_backfill=data.is_backfill,
    )
    db.add(row)
    db.flush()
    db.refresh(row)
    return _to_domain(row)


def complete_run(
    db: Session,
    run_id: UUID,
    *,
    status: FilingMonitorRunStatus,
    resulting_watermark: datetime | None,
    issuers_checked: int,
    filings_discovered: int,
    filings_processed: int,
    alerts_created: int,
    errors_count: int,
    error_summary: str | None,
) -> FilingMonitorRun:
    row = db.get(FilingMonitorRunModel, run_id)
    if row is None:
        raise ValueError(f"filing_monitor_run {run_id} not found")
    row.status = status.value
    row.resulting_watermark = resulting_watermark
    row.issuers_checked = issuers_checked
    row.filings_discovered = filings_discovered
    row.filings_processed = filings_processed
    row.alerts_created = alerts_created
    row.errors_count = errors_count
    row.error_summary = error_summary
    row.completed_at = datetime.now(tz=row.started_at.tzinfo)
    db.flush()
    db.refresh(row)
    return _to_domain(row)


def get_run(db: Session, run_id: UUID) -> FilingMonitorRun | None:
    row = db.get(FilingMonitorRunModel, run_id)
    return _to_domain(row) if row is not None else None


def get_latest_successful_run(db: Session) -> FilingMonitorRun | None:
    """The run whose `resulting_watermark` is the current watermark — success
    or baseline_established only; a run with errors never advances the
    watermark (PLAN.md 24.5), so it must never be treated as "latest
    successful" here regardless of recency.
    """
    success_statuses = (
        FilingMonitorRunStatus.SUCCESS.value,
        FilingMonitorRunStatus.BASELINE_ESTABLISHED.value,
    )
    stmt = (
        select(FilingMonitorRunModel)
        .where(FilingMonitorRunModel.status.in_(success_statuses))
        .order_by(FilingMonitorRunModel.completed_at.desc())
        .limit(1)
    )
    row = db.execute(stmt).scalars().first()
    return _to_domain(row) if row is not None else None


def list_runs(db: Session, *, page: int = 1, page_size: int = 20) -> list[FilingMonitorRun]:
    stmt = (
        select(FilingMonitorRunModel)
        .order_by(FilingMonitorRunModel.started_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = db.execute(stmt).scalars().all()
    return [_to_domain(row) for row in rows]
