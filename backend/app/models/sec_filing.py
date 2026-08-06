"""ORM model for `sec_filing` (PLAN.md section 24.5).

Distinct from `financial_fact` (XBRL-datapoint-level): this represents the
filing itself — accession number, form type, filing date — the unit the
overnight monitor's watermark/delta logic keys off of.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SecFiling(Base):
    __tablename__ = "sec_filing"
    __table_args__ = (
        Index("ix_sec_filing_accession_no", "accession_no", unique=True),
        Index("ix_sec_filing_issuer_id", "issuer_id"),
        Index("ix_sec_filing_provenance_id", "provenance_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    issuer_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("issuer.id"), nullable=False
    )
    accession_no: Mapped[str] = mapped_column(Text, nullable=False)
    form_type: Mapped[str] = mapped_column(Text, nullable=False)
    filing_date: Mapped[date] = mapped_column(Date, nullable=False)
    period_of_report: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_amendment: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    primary_document: Mapped[str | None] = mapped_column(Text, nullable=True)
    primary_document_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    provenance_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("provenance.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
