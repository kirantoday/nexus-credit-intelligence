"""ORM model for `alert_event` (PLAN.md section 4.11, 24.3).

First real implementation of the already-approved §4.11 shape, redesigned
around Evidence rather than SEC filings (ADR-018): no `filing_id` column at
all — `evidence_ids` is the source of truth for what caused the alert, and
the UI resolves "which filing(s)" by joining through
`research_evidence.filing_id`. `alert_rule` (§4.11) is deliberately not
created this milestone — no real caller yet (Milestone 10).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.types import AlertStatus, DetectionMethod, EvidenceSeverity
from app.db.base import Base

_SEVERITY_SQL_LIST = ", ".join(f"'{value}'" for value in EvidenceSeverity)
_DETECTION_METHOD_SQL_LIST = ", ".join(f"'{value}'" for value in DetectionMethod)
_STATUS_SQL_LIST = ", ".join(f"'{value}'" for value in AlertStatus)


class AlertEvent(Base):
    __tablename__ = "alert_event"
    __table_args__ = (
        CheckConstraint(f"severity IN ({_SEVERITY_SQL_LIST})", name="ck_alert_event_severity"),
        CheckConstraint(
            f"detection_method IN ({_DETECTION_METHOD_SQL_LIST})",
            name="ck_alert_event_detection_method",
        ),
        CheckConstraint(f"status IN ({_STATUS_SQL_LIST})", name="ck_alert_event_status"),
        CheckConstraint(
            "(dismissed_at IS NULL AND dismissed_by IS NULL) OR status = 'dismissed'",
            name="ck_alert_event_dismissed_requires_status",
        ),
        Index("ix_alert_event_issuer_id", "issuer_id"),
        Index("ix_alert_event_bundle_key", "bundle_key"),
        Index("ix_alert_event_provenance_id", "provenance_id"),
        Index("ix_alert_event_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    issuer_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("issuer.id"), nullable=False
    )
    category: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    headline: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    bundle_key: Mapped[str] = mapped_column(Text, nullable=False)
    primary_evidence_provider: Mapped[str] = mapped_column(Text, nullable=False)
    primary_source_label: Mapped[str] = mapped_column(Text, nullable=False)
    primary_source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    detection_method: Mapped[str] = mapped_column(Text, nullable=False)
    ai_assisted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    confidence: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    provenance_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("provenance.id"), nullable=False
    )
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'new'"))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledged_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dismissed_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    dismissal_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_backfill: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    issuer_is_subject: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
