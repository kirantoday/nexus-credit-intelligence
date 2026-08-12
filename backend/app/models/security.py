"""ORM model for `security` (PLAN.md section 4.5).

Single `provenance_id` per row, not per-field — see `app/domain/security.py`'s
module docstring and PLAN.md Technical Debt TD-007 for why (still open, but
not because Milestone 5 needed it: OpenFIGI-sourced bonds are new rows, not
enrichments of the existing SEC-sourced aggregate row).
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Computed,
    Date,
    ForeignKey,
    Index,
    Numeric,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.types import InstrumentType, Seniority
from app.db.base import Base

_INSTRUMENT_TYPE_SQL_LIST = ", ".join(f"'{value}'" for value in InstrumentType)
_SENIORITY_SQL_LIST = ", ".join(f"'{value}'" for value in Seniority)
# search_vector (Milestone 12A): description only — cusip/isin/figi are
# identifiers, not natural-language text, and are matched exactly (Tier 0)
# against their own existing unique indexes, never tokenized into this
# tsvector. See app.repositories.search_repository's module docstring.
_SEARCH_VECTOR_SQL = "setweight(to_tsvector('english', coalesce(description, '')), 'A')"


class Security(Base):
    __tablename__ = "security"
    __table_args__ = (
        CheckConstraint(
            f"instrument_type IN ({_INSTRUMENT_TYPE_SQL_LIST})",
            name="ck_security_instrument_type",
        ),
        CheckConstraint(
            f"seniority IS NULL OR seniority IN ({_SENIORITY_SQL_LIST})",
            name="ck_security_seniority",
        ),
        CheckConstraint(
            "is_synthetic OR synthetic_reason IS NULL",
            name="ck_security_synthetic_reason_requires_is_synthetic",
        ),
        Index("ix_security_issuer_id", "issuer_id"),
        Index("ix_security_provenance_id", "provenance_id"),
        Index("ix_security_instrument_type", "instrument_type"),
        Index(
            "ix_security_cusip", "cusip", unique=True, postgresql_where=text("cusip IS NOT NULL")
        ),
        Index("ix_security_isin", "isin", unique=True, postgresql_where=text("isin IS NOT NULL")),
        Index("ix_security_figi", "figi", unique=True, postgresql_where=text("figi IS NOT NULL")),
        Index("ix_security_search_vector", "search_vector", postgresql_using="gin"),
        Index(
            "ix_security_description_trgm",
            "description",
            postgresql_using="gin",
            postgresql_ops={"description": "gin_trgm_ops"},
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    issuer_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("issuer.id"), nullable=False
    )
    instrument_type: Mapped[str] = mapped_column(Text, nullable=False)
    seniority: Mapped[str | None] = mapped_column(Text, nullable=True)
    lien_position: Mapped[str | None] = mapped_column(Text, nullable=True)
    secured: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    cusip: Mapped[str | None] = mapped_column(Text, nullable=True)
    isin: Mapped[str | None] = mapped_column(Text, nullable=True)
    figi: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    maturity_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    coupon: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    amount_outstanding: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    benchmark: Mapped[str | None] = mapped_column(Text, nullable=True)
    spread: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
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
