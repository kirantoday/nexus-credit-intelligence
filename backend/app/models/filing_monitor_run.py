"""ORM model for `filing_monitor_run` (PLAN.md section 24.5).

One row per overnight-monitor invocation. Watermark rules (enforced in
`app/services/filing_monitor_service.py`, not here): `resulting_watermark`
only advances when a run completes with zero errors; a partial/failed run
leaves `previous_watermark` unchanged so the next run safely re-checks the
same window without losing or duplicating filings.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.types import FilingMonitorRunMode, FilingMonitorRunStatus
from app.db.base import Base

_STATUS_SQL_LIST = ", ".join(f"'{value}'" for value in FilingMonitorRunStatus)
_MODE_SQL_LIST = ", ".join(f"'{value}'" for value in FilingMonitorRunMode)


class FilingMonitorRun(Base):
    __tablename__ = "filing_monitor_run"
    __table_args__ = (
        CheckConstraint(f"status IN ({_STATUS_SQL_LIST})", name="ck_filing_monitor_run_status"),
        CheckConstraint(f"mode IN ({_MODE_SQL_LIST})", name="ck_filing_monitor_run_mode"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[str] = mapped_column(Text, nullable=False)
    previous_watermark: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resulting_watermark: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    issuers_checked: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    filings_discovered: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    filings_processed: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    alerts_created: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    errors_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    backfill_lookback_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_backfill: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
