"""ORM model for `docket_document` (PLAN.md sections 4.5, 15).

`is_sealed` is enforced at the domain layer (never `recap_available` when
sealed, see `app/domain/docket_document.py`) — kept as a real, queryable
column here rather than only an application-level inference, so the "never
fetch sealed material" invariant (PLAN.md section 22) is auditable directly
against the database, not just trusted from ingestion code.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
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

from app.core.types import DocketDocumentAvailability
from app.db.base import Base

_AVAILABILITY_SQL_LIST = ", ".join(f"'{value}'" for value in DocketDocumentAvailability)


class DocketDocument(Base):
    __tablename__ = "docket_document"
    __table_args__ = (
        CheckConstraint(
            f"availability IN ({_AVAILABILITY_SQL_LIST})", name="ck_docket_document_availability"
        ),
        CheckConstraint(
            "NOT (is_sealed AND availability = 'recap_available')",
            name="ck_docket_document_sealed_never_recap_available",
        ),
        Index(
            "ix_docket_document_courtlistener_document_id",
            "courtlistener_document_id",
            unique=True,
        ),
        Index("ix_docket_document_docket_entry_id", "docket_entry_id"),
        Index("ix_docket_document_provenance_id", "provenance_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    docket_entry_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("court_docket_entry.id"), nullable=False
    )
    courtlistener_document_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    availability: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_sealed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    recap_document_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_payload_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("raw_provider_payload.id"), nullable=True
    )
    uploaded_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    provenance_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("provenance.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
