"""ORM model for `financial_fact` (PLAN.md section 4.5)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Integer, Numeric, Text, text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.types import FormType
from app.db.base import Base

_FORM_TYPE_SQL_LIST = ", ".join(f"'{value}'" for value in FormType)


class FinancialFact(Base):
    __tablename__ = "financial_fact"
    __table_args__ = (
        CheckConstraint(
            f"form_type IN ({_FORM_TYPE_SQL_LIST})", name="ck_financial_fact_form_type"
        ),
        Index("ix_financial_fact_issuer_id", "issuer_id"),
        Index("ix_financial_fact_provenance_id", "provenance_id"),
        # Idempotency: re-ingesting the same filing's same datapoint should
        # not create a duplicate row.
        Index(
            "ix_financial_fact_dedup",
            "issuer_id",
            "concept",
            "accession_no",
            "fiscal_year",
            "fiscal_period",
            unique=True,
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    issuer_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("issuer.id"), nullable=False
    )
    concept: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    unit: Mapped[str] = mapped_column(Text, nullable=False)
    fiscal_period: Mapped[str] = mapped_column(Text, nullable=False)
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    form_type: Mapped[str] = mapped_column(Text, nullable=False)
    filing_date: Mapped[date] = mapped_column(Date, nullable=False)
    accession_no: Mapped[str] = mapped_column(Text, nullable=False)
    provenance_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("provenance.id"), nullable=False
    )
