"""ORM model for `market_discovery_run` (PLAN.md Milestone 7.5).

Distinct from `filing_monitor_run`: that table watermarks a refresh of
issuers Nexus already knows about; this one watermarks a market-wide SEC
full-text-search scan for issuers Nexus does not yet know about. Same
watermark discipline: `resulting_watermark` only advances when a run
completes with zero errors, mirroring `filing_monitor_run`'s rule
(`app/services/filing_monitor_service.py`).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.types import FilingMonitorRunMode, FilingMonitorRunStatus
from app.db.base import Base

_STATUS_SQL_LIST = ", ".join(f"'{value}'" for value in FilingMonitorRunStatus)
_MODE_SQL_LIST = ", ".join(f"'{value}'" for value in FilingMonitorRunMode)


class MarketDiscoveryRun(Base):
    __tablename__ = "market_discovery_run"
    __table_args__ = (
        CheckConstraint(f"status IN ({_STATUS_SQL_LIST})", name="ck_market_discovery_run_status"),
        CheckConstraint(f"mode IN ({_MODE_SQL_LIST})", name="ck_market_discovery_run_mode"),
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
    window_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    window_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    previous_watermark: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resulting_watermark: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    queries_executed: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    filings_examined: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    candidate_filings: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    issuers_resolved_existing: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    issuers_resolved_new: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    issuers_ambiguous: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    issuers_rejected: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    evidence_created: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    alerts_created: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    errors_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
