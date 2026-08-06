"""ORM model for `capital_structure_position` (PLAN.md section 4.6)."""

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
    Integer,
    Numeric,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.types import CapitalStructureInstrumentType, Seniority
from app.db.base import Base

_INSTRUMENT_TYPE_SQL_LIST = ", ".join(f"'{value}'" for value in CapitalStructureInstrumentType)
_SENIORITY_SQL_LIST = ", ".join(f"'{value}'" for value in Seniority)


class CapitalStructurePosition(Base):
    __tablename__ = "capital_structure_position"
    __table_args__ = (
        # Constraint names are kept under Postgres's 63-character identifier
        # limit by abbreviating "capital_structure_position" to "capstruct_position"
        # here only — the table/column names themselves stay unabbreviated.
        CheckConstraint(
            f"instrument_type IN ({_INSTRUMENT_TYPE_SQL_LIST})",
            name="ck_capstruct_position_instrument_type",
        ),
        CheckConstraint(
            f"seniority IS NULL OR seniority IN ({_SENIORITY_SQL_LIST})",
            name="ck_capstruct_position_seniority",
        ),
        CheckConstraint(
            "is_synthetic OR synthetic_reason IS NULL",
            name="ck_capstruct_position_synth_reason_requires_synth",
        ),
        CheckConstraint(
            "(enterprise_value_coverage IS NULL AND illustrative_recovery IS NULL) "
            "OR recovery_scenario IS NOT NULL",
            name="ck_capstruct_position_recovery_requires_scenario",
        ),
        Index("ix_capital_structure_position_issuer_id", "issuer_id"),
        Index("ix_capital_structure_position_security_id", "security_id"),
        Index("ix_capital_structure_position_provenance_id", "provenance_id"),
        # Rendering order within one issuer's stack is a hard requirement
        # (PLAN.md section 7) — never two layers claiming the same rank.
        Index(
            "ix_capital_structure_position_issuer_rank",
            "issuer_id",
            "rank_order",
            unique=True,
        ),
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
    layer_name: Mapped[str] = mapped_column(Text, nullable=False)
    rank_order: Mapped[int] = mapped_column(Integer, nullable=False)
    instrument_type: Mapped[str] = mapped_column(Text, nullable=False)
    seniority: Mapped[str | None] = mapped_column(Text, nullable=True)
    lien_position: Mapped[str | None] = mapped_column(Text, nullable=True)
    secured: Mapped[bool] = mapped_column(Boolean, nullable=False)
    guarantor_scope: Mapped[str | None] = mapped_column(Text, nullable=True)
    amount_outstanding: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    currency: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'USD'"))
    maturity_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    price: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    enterprise_value_coverage: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    illustrative_recovery: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    recovery_scenario: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_synthetic: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    synthetic_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    provenance_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("provenance.id"), nullable=False
    )
