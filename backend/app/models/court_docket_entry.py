"""ORM model for `court_docket_entry` (PLAN.md section 4.5, Milestone 7)."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CourtDocketEntry(Base):
    __tablename__ = "court_docket_entry"
    __table_args__ = (
        Index(
            "ix_court_docket_entry_courtlistener_entry_id",
            "courtlistener_entry_id",
            unique=True,
        ),
        Index("ix_court_docket_entry_docket_id", "docket_id"),
        Index("ix_court_docket_entry_provenance_id", "provenance_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    docket_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("court_docket.id"), nullable=False
    )
    courtlistener_entry_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    entry_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    entry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    document_available: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    provenance_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("provenance.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
