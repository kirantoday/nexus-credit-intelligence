"""ORM model for `court_docket` (PLAN.md section 4.5, Milestone 7)."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CourtDocket(Base):
    __tablename__ = "court_docket"
    __table_args__ = (
        Index("ix_court_docket_courtlistener_docket_id", "courtlistener_docket_id", unique=True),
        Index("ix_court_docket_issuer_id", "issuer_id"),
        Index("ix_court_docket_provenance_id", "provenance_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    issuer_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("issuer.id"), nullable=True
    )
    courtlistener_docket_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    court: Mapped[str] = mapped_column(Text, nullable=False)
    docket_number: Mapped[str] = mapped_column(Text, nullable=False)
    case_name: Mapped[str] = mapped_column(Text, nullable=False)
    nature_of_suit: Mapped[str | None] = mapped_column(Text, nullable=True)
    chapter: Mapped[str | None] = mapped_column(Text, nullable=True)
    date_filed: Mapped[date | None] = mapped_column(Date, nullable=True)
    provenance_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("provenance.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
