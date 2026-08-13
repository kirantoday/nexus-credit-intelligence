"""ORM model for `document_extraction` (Milestone 10C).

One immutable row per extraction/chunking *attempt* over a source
document. Reprocessing a `research_document` never mutates an existing
row — it creates a new one (see `app.services.document_extraction_service`).
`is_current` marks the single active attempt whose chunks represent the
document's corpus today; promotion (flipping `is_current`) happens inside
one transaction alongside marking the new attempt `completed`, and the
partial unique index below makes "two current extractions for the same
source" a constraint violation, not just an application-level bug — the
same mechanism this project already trusts for CHECK-constrained enums
(ADR-014) applied to a cross-row invariant instead of a single-row one.

`source_type` + a nullable per-source FK (`research_document_id` today)
mirrors `research_evidence.evidence_provider`/`filing_id`/`docket_entry_id`
(ADR-018) rather than a polymorphic `source_id` association — a future
SEC/court source adds its own nullable FK column and its own `source_type`
member, never a schema redesign of this table.
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
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.types import (
    DocumentExtractionErrorClass,
    DocumentExtractionSourceType,
    DocumentExtractionStatus,
)
from app.db.base import Base

_SOURCE_TYPE_SQL_LIST = ", ".join(f"'{value}'" for value in DocumentExtractionSourceType)
_STATUS_SQL_LIST = ", ".join(f"'{value}'" for value in DocumentExtractionStatus)
_ERROR_CLASS_SQL_LIST = ", ".join(f"'{value}'" for value in DocumentExtractionErrorClass)


class DocumentExtraction(Base):
    __tablename__ = "document_extraction"
    __table_args__ = (
        CheckConstraint(
            f"source_type IN ({_SOURCE_TYPE_SQL_LIST})", name="ck_document_extraction_source_type"
        ),
        CheckConstraint(f"status IN ({_STATUS_SQL_LIST})", name="ck_document_extraction_status"),
        CheckConstraint(
            f"error_classification IS NULL OR error_classification IN "
            f"({_ERROR_CLASS_SQL_LIST})",
            name="ck_document_extraction_error_classification",
        ),
        CheckConstraint(
            "source_type != 'research_document' OR research_document_id IS NOT NULL",
            name="ck_document_extraction_research_document_source_requires_fk",
        ),
        # Only a genuinely completed attempt may ever be promoted current —
        # a stuck `processing`/`failed`/`needs_ocr` row can never satisfy
        # this, so "current" always means "safe to read chunks from."
        CheckConstraint(
            "(NOT is_current) OR (status = 'completed')",
            name="ck_document_extraction_current_requires_completed",
        ),
        Index("ix_document_extraction_research_document_id", "research_document_id"),
        # Backs the worker's atomic claim query (`WHERE status = 'pending'
        # ORDER BY created_at FOR UPDATE SKIP LOCKED`).
        Index("ix_document_extraction_status", "status"),
        # Partial unique index: at most one current extraction per source
        # document, enforced by Postgres itself, not just by application
        # code remembering to demote the old one before promoting the new
        # one in the same transaction.
        Index(
            "ux_document_extraction_one_current_per_document",
            "research_document_id",
            unique=True,
            postgresql_where=text("is_current"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    source_type: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'research_document'")
    )
    research_document_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("research_document.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"))

    extractor_provider: Mapped[str | None] = mapped_column(Text, nullable=True)
    extractor_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunking_strategy_version: Mapped[str | None] = mapped_column(Text, nullable=True)

    structured_artifact_storage_key: Mapped[str | None] = mapped_column(Text, nullable=True)

    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    table_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    error_classification: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # `clock_timestamp()`, not `now()` — see `app/models/audit.py`'s
    # identical `occurred_at` comment: `now()` is frozen at transaction
    # start, so several extractions created in one transaction (e.g. the
    # worker's own reclaim-then-claim sequence, or a test fixture) would
    # tie and make `list_for_document`'s "newest first" ordering unstable.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("clock_timestamp()")
    )

    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
