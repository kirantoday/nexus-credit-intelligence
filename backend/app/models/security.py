"""ORM model for `security` (PLAN.md section 4.5).

Single `provenance_id` per row, not per-field — see `app/domain/security.py`'s
module docstring and PLAN.md Technical Debt TD-007 for why.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Numeric,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.types import InstrumentType, Seniority
from app.db.base import Base

_INSTRUMENT_TYPE_SQL_LIST = ", ".join(f"'{value}'" for value in InstrumentType)
_SENIORITY_SQL_LIST = ", ".join(f"'{value}'" for value in Seniority)


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
