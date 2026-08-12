"""ORM model for `issuer` (PLAN.md section 4.5).

`search_vector` (Milestone 12A) is a database-generated, always-in-sync
`tsvector` column — see `app.repositories.search_repository`'s module
docstring for why generated columns were chosen over a synced
`search_document` table.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, CheckConstraint, Computed, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

_SEARCH_VECTOR_SQL = (
    "setweight(to_tsvector('english', coalesce(legal_name, '')), 'A') || "
    "setweight(to_tsvector('english', coalesce(ticker, '')), 'A')"
)


class Issuer(Base):
    __tablename__ = "issuer"
    __table_args__ = (
        # unique=True on a nullable column allows any number of NULL ciks
        # (synthetic/no-SEC-filer issuers) while still preventing two rows
        # from claiming the same real CIK.
        Index("ix_issuer_cik", "cik", unique=True),
        CheckConstraint(
            "is_synthetic OR synthetic_reason IS NULL",
            name="ck_issuer_synthetic_reason_requires_is_synthetic",
        ),
        Index("ix_issuer_search_vector", "search_vector", postgresql_using="gin"),
        Index(
            "ix_issuer_legal_name_trgm",
            "legal_name",
            postgresql_using="gin",
            postgresql_ops={"legal_name": "gin_trgm_ops"},
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    legal_name: Mapped[str] = mapped_column(Text, nullable=False)
    cik: Mapped[str | None] = mapped_column(Text, nullable=True)
    lei: Mapped[str | None] = mapped_column(Text, nullable=True)
    ticker: Mapped[str | None] = mapped_column(Text, nullable=True)
    sic: Mapped[str | None] = mapped_column(Text, nullable=True)
    sector: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_synthetic: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    synthetic_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    provenance_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("provenance.id"), nullable=False
    )
    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR, Computed(_SEARCH_VECTOR_SQL, persisted=True), nullable=True
    )
