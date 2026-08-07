"""ORM model for `issuer_enrichment_status` (PLAN.md Milestone 7.5 section 8).

The canonical model distinguishing "no data exists" (`NO_DATA`) from
"Nexus never checked" (no row, or `PENDING`) per issuer/provider. This is
the input to `app/services/enrichment_orchestrator.py`'s "should I run this
provider right now" decision for every issuer the pipeline touches —
newly-discovered and already-known alike — driven by staleness/never-
checked/retry-due policy, never a one-time "new issuer" trigger.

`checkpoint` carries a provider-specific watermark (e.g. CourtListener's
per-docket `last_synced_date_created`, the TD-012 incremental-sync fix) —
never secrets or full request/response bodies.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.types import EnrichmentStatus
from app.db.base import Base

_STATUS_SQL_LIST = ", ".join(f"'{value}'" for value in EnrichmentStatus)


class IssuerEnrichmentStatus(Base):
    __tablename__ = "issuer_enrichment_status"
    __table_args__ = (
        UniqueConstraint(
            "issuer_id", "provider", name="uq_issuer_enrichment_status_issuer_provider"
        ),
        CheckConstraint(
            f"status IN ({_STATUS_SQL_LIST})", name="ck_issuer_enrichment_status_status"
        ),
        Index("ix_issuer_enrichment_status_issuer_id", "issuer_id"),
        Index("ix_issuer_enrichment_status_provider", "provider"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    issuer_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("issuer.id"), nullable=False
    )
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    records_found: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    error_classification: Mapped[str | None] = mapped_column(Text, nullable=True)
    checkpoint: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
