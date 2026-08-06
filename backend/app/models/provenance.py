"""ORM models for the provenance spine: Provenance, Calculation, CalculationInput.

Enum-shaped columns (`provider`, `original_source`, `transformation`,
`classification`) are `Text` with a `CheckConstraint`, not native Postgres ENUM
types — see `app/core/types.py`'s module docstring for why. Validity is also
enforced one layer up, in the Pydantic domain objects (`app/domain/provenance.py`);
the CHECK constraints here are defense-in-depth against any write path that
bypasses the domain layer, not the primary line of defense.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.types import DataClassification, OriginalSource, ProviderName, TransformationType
from app.db.base import Base

_PROVIDER_SQL_LIST = ", ".join(f"'{value}'" for value in ProviderName)
_ORIGINAL_SOURCE_SQL_LIST = ", ".join(f"'{value}'" for value in OriginalSource)
_TRANSFORMATION_SQL_LIST = ", ".join(f"'{value}'" for value in TransformationType)
_CLASSIFICATION_SQL_LIST = ", ".join(f"'{value}'" for value in DataClassification)


class Provenance(Base):
    __tablename__ = "provenance"
    __table_args__ = (
        CheckConstraint(f"provider IN ({_PROVIDER_SQL_LIST})", name="ck_provenance_provider"),
        CheckConstraint(
            f"original_source IS NULL OR original_source IN ({_ORIGINAL_SOURCE_SQL_LIST})",
            name="ck_provenance_original_source",
        ),
        CheckConstraint(
            f"transformation IN ({_TRANSFORMATION_SQL_LIST})",
            name="ck_provenance_transformation",
        ),
        CheckConstraint(
            f"classification IN ({_CLASSIFICATION_SQL_LIST})",
            name="ck_provenance_classification",
        ),
        CheckConstraint(
            "(transformation = 'calculated') = (calculation_id IS NOT NULL)",
            name="ck_provenance_calculation_linkage",
        ),
        CheckConstraint(
            "provider = 'admin_upload' OR original_source IS NULL",
            name="ck_provenance_original_source_requires_admin_upload",
        ),
        Index("ix_provenance_calculation_id", "calculation_id"),
        Index("ix_provenance_raw_payload_id", "raw_payload_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    original_source: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_attested_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_attested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    source_record_id: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    transformation: Mapped[str] = mapped_column(Text, nullable=False)
    classification: Mapped[str] = mapped_column(Text, nullable=False)
    calculation_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("calculation.id"), nullable=True
    )
    raw_payload_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("raw_provider_payload.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class Calculation(Base):
    __tablename__ = "calculation"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    method: Mapped[str] = mapped_column(Text, nullable=False)
    formula_note: Mapped[str] = mapped_column(Text, nullable=False)


class CalculationInput(Base):
    __tablename__ = "calculation_input"
    __table_args__ = (Index("ix_calculation_input_provenance_id", "provenance_id"),)

    calculation_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("calculation.id"), primary_key=True
    )
    provenance_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("provenance.id"), primary_key=True
    )
    input_role: Mapped[str | None] = mapped_column(Text, nullable=True)
    sequence_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
