"""ORM models for `research_note` and `research_note_version` (PLAN.md 4.10;
Milestone 10A — see PLAN.md 24.12).

Refines the original §4.10 sketch: no generic `body_markdown` field. The user
explicitly asked for a note that "feels like an investment-research artifact,
not a generic text box" — the structured sections (bull/base/bear case,
catalysts, risks, invalidation conditions) *are* the note's content, so a
parallel free-text body would just be a redundant place to put the same
information. `evidence_refs` lets a note point at existing
`research_evidence`/`sec_filing`/`alert_event`/`docket_document` rows by
table+id without copying their content, mirroring the already-established
`alert_event.evidence_ids` JSONB-list-of-ids pattern.

`research_note_version` is a full snapshot per material edit (never a diff),
written by `research_note_service` before an update is applied — this model
only defines the shape; the write-before-update ordering lives in the service.

`author_user_id`/`edited_by` are plain nullable `Text`, not a FK to a `user`
table — Milestone 10A ships with `AUTH_ENABLED=false` and no `user` table
(mirrors `collection.owner_user_id`'s already-established nullable-identity
convention from Milestone 8/ADR-016). No fabricated per-user ownership.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.types import AccessClassification, Conviction, ThesisStatus
from app.db.base import Base

_THESIS_STATUS_SQL_LIST = ", ".join(f"'{value}'" for value in ThesisStatus)
_CONVICTION_SQL_LIST = ", ".join(f"'{value}'" for value in Conviction)
_ACCESS_CLASSIFICATION_SQL_LIST = ", ".join(f"'{value}'" for value in AccessClassification)


class ResearchNote(Base):
    __tablename__ = "research_note"
    __table_args__ = (
        CheckConstraint(
            f"thesis_status IN ({_THESIS_STATUS_SQL_LIST})", name="ck_research_note_thesis_status"
        ),
        CheckConstraint(
            f"conviction IS NULL OR conviction IN ({_CONVICTION_SQL_LIST})",
            name="ck_research_note_conviction",
        ),
        CheckConstraint(
            f"access_classification IN ({_ACCESS_CLASSIFICATION_SQL_LIST})",
            name="ck_research_note_access_classification",
        ),
        CheckConstraint(
            "(is_archived AND archived_at IS NOT NULL) "
            "OR (NOT is_archived AND archived_at IS NULL)",
            name="ck_research_note_archived_requires_timestamp",
        ),
        Index("ix_research_note_issuer_id", "issuer_id"),
        Index("ix_research_note_security_id", "security_id"),
        Index("ix_research_note_is_archived", "is_archived"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    issuer_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("issuer.id"), nullable=False
    )
    security_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("security.id"), nullable=True
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    thesis_status: Mapped[str] = mapped_column(Text, nullable=False)
    conviction: Mapped[str | None] = mapped_column(Text, nullable=True)
    bull_case: Mapped[str | None] = mapped_column(Text, nullable=True)
    base_case: Mapped[str | None] = mapped_column(Text, nullable=True)
    bear_case: Mapped[str | None] = mapped_column(Text, nullable=True)
    catalysts: Mapped[str | None] = mapped_column(Text, nullable=True)
    risks: Mapped[str | None] = mapped_column(Text, nullable=True)
    invalidation_conditions: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_refs: Mapped[list[dict[str, str]] | None] = mapped_column(JSONB, nullable=True)
    access_classification: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'standard'")
    )
    author_user_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    current_version_number: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1")
    )
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class ResearchNoteVersion(Base):
    __tablename__ = "research_note_version"
    __table_args__ = (
        CheckConstraint(
            f"thesis_status IN ({_THESIS_STATUS_SQL_LIST})",
            name="ck_research_note_version_thesis_status",
        ),
        CheckConstraint(
            f"conviction IS NULL OR conviction IN ({_CONVICTION_SQL_LIST})",
            name="ck_research_note_version_conviction",
        ),
        CheckConstraint(
            f"access_classification IN ({_ACCESS_CLASSIFICATION_SQL_LIST})",
            name="ck_research_note_version_access_classification",
        ),
        Index("ix_research_note_version_research_note_id", "research_note_id"),
        Index(
            "ix_research_note_version_note_version",
            "research_note_id",
            "version_number",
            unique=True,
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    research_note_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("research_note.id"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    thesis_status: Mapped[str] = mapped_column(Text, nullable=False)
    conviction: Mapped[str | None] = mapped_column(Text, nullable=True)
    bull_case: Mapped[str | None] = mapped_column(Text, nullable=True)
    base_case: Mapped[str | None] = mapped_column(Text, nullable=True)
    bear_case: Mapped[str | None] = mapped_column(Text, nullable=True)
    catalysts: Mapped[str | None] = mapped_column(Text, nullable=True)
    risks: Mapped[str | None] = mapped_column(Text, nullable=True)
    invalidation_conditions: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_refs: Mapped[list[dict[str, str]] | None] = mapped_column(JSONB, nullable=True)
    access_classification: Mapped[str] = mapped_column(Text, nullable=False)
    edited_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    # clock_timestamp(), not now() — see app/models/audit.py's occurred_at
    # comment: version snapshots need the same genuinely-distinct-per-
    # statement ordering guarantee audit events do.
    edited_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("clock_timestamp()")
    )
