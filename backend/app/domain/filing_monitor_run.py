"""Canonical domain object for `filing_monitor_run` (PLAN.md section 24.5).

One row per overnight-monitor invocation. `FilingMonitorRunCreate` starts a
run (`status = running`); the repository's `complete_run` takes the closing
counts/status directly rather than a second domain object, since "complete a
run" is a narrow, single-purpose update, not a general-purpose write.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.core.types import FilingMonitorRunMode, FilingMonitorRunStatus


class FilingMonitorRunCreate(BaseModel):
    """Everything needed to start a `filing_monitor_run` row."""

    model_config = ConfigDict(frozen=True)

    mode: FilingMonitorRunMode
    previous_watermark: datetime | None = None
    backfill_lookback_days: int | None = None
    is_backfill: bool = False


class FilingMonitorRun(BaseModel):
    """A persisted `filing_monitor_run` row."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    started_at: datetime
    completed_at: datetime | None
    status: FilingMonitorRunStatus
    mode: FilingMonitorRunMode
    previous_watermark: datetime | None
    resulting_watermark: datetime | None
    issuers_checked: int
    filings_discovered: int
    filings_processed: int
    alerts_created: int
    errors_count: int
    error_summary: str | None
    backfill_lookback_days: int | None
    is_backfill: bool
    created_at: datetime
