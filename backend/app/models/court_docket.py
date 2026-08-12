"""ORM model for `court_docket` (PLAN.md section 4.5, Milestone 7).

`search_vector`/`docket_number` index (Milestone 12A) — see
`app.repositories.search_repository`'s module docstring.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, Computed, Date, DateTime, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

_SEARCH_VECTOR_SQL = (
    "setweight(to_tsvector('english', coalesce(case_name, '')), 'A') || "
    "setweight(to_tsvector('english', coalesce(nature_of_suit, '')), 'C')"
)


class CourtDocket(Base):
    __tablename__ = "court_docket"
    __table_args__ = (
        Index("ix_court_docket_courtlistener_docket_id", "courtlistener_docket_id", unique=True),
        Index("ix_court_docket_issuer_id", "issuer_id"),
        Index("ix_court_docket_provenance_id", "provenance_id"),
        # docket_number (e.g. "23-10920") is a human-readable exact-match
        # identifier (PLAN.md 4.13/8) — not unique on its own (case numbers
        # can repeat across different courts), so a plain non-unique index,
        # not the unique index courtlistener_docket_id already has.
        Index("ix_court_docket_docket_number", "docket_number"),
        Index("ix_court_docket_search_vector", "search_vector", postgresql_using="gin"),
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
    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR, Computed(_SEARCH_VECTOR_SQL, persisted=True), nullable=True
    )
