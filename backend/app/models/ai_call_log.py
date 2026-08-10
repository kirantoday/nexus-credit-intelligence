"""ORM model for `ai_call_log` (PLAN.md Milestone 7.5.3).

One row per real Anthropic API request. `discovery_run_id`/`filing_monitor_run_id`
are both nullable FKs to the two existing run tables (never both set) —
mirrors the existing nullable-per-provider-FK convention (ADR-018) rather
than inventing a generic polymorphic run reference. A call made outside
either run context (e.g. `app.scripts.reclassify_system_universes`, a
one-off maintenance script) leaves both null.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.types import AiOperation, AiRoute
from app.db.base import Base

_OPERATION_SQL_LIST = ", ".join(f"'{value}'" for value in AiOperation)
_ROUTE_SQL_LIST = ", ".join(f"'{value}'" for value in AiRoute)


class AiCallLog(Base):
    __tablename__ = "ai_call_log"
    __table_args__ = (
        CheckConstraint(f"operation IN ({_OPERATION_SQL_LIST})", name="ck_ai_call_log_operation"),
        CheckConstraint(f"route IN ({_ROUTE_SQL_LIST})", name="ck_ai_call_log_route"),
        Index("ix_ai_call_log_discovery_run_id", "discovery_run_id"),
        Index("ix_ai_call_log_filing_monitor_run_id", "filing_monitor_run_id"),
        Index("ix_ai_call_log_issuer_id", "issuer_id"),
        Index("ix_ai_call_log_bundle_key", "bundle_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    discovery_run_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("market_discovery_run.id"), nullable=True
    )
    filing_monitor_run_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("filing_monitor_run.id"), nullable=True
    )
    issuer_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("issuer.id"), nullable=True
    )
    bundle_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    operation: Mapped[str] = mapped_column(Text, nullable=False)
    route: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    routing_reason: Mapped[str] = mapped_column(Text, nullable=False)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost_usd: Mapped[float | None] = mapped_column(Numeric(12, 6), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    error_classification: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
