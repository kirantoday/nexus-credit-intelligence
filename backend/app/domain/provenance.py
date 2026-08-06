"""Canonical domain objects for the provenance spine (PLAN.md section 4.1-4.3).

These are the objects normalizers build and repositories persist — never a raw
provider DTO, and never a SQLAlchemy model. Frozen (immutable) Pydantic models:
a provenance/calculation record is a fact about what happened at ingestion time
and is never mutated in place, matching the append-only nature of the spine
(see ARCHITECTURE_DECISIONS.md ADR-014 for why Pydantic over a plain dataclass).
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator

from app.core.types import DataClassification, OriginalSource, ProviderName, TransformationType


class ProvenanceCreate(BaseModel):
    """Everything needed to create a `provenance` row; id/created_at are server-generated."""

    model_config = ConfigDict(frozen=True)

    provider: ProviderName
    original_source: OriginalSource | None = None
    source_attested_by: str | None = None
    source_attested_at: datetime | None = None
    source_record_id: str
    source_url: str | None = None
    as_of_date: date
    retrieved_at: datetime
    transformation: TransformationType
    classification: DataClassification
    calculation_id: UUID | None = None
    raw_payload_id: UUID | None = None

    @model_validator(mode="after")
    def _calculation_linkage_matches_transformation(self) -> ProvenanceCreate:
        is_calculated = self.transformation is TransformationType.CALCULATED
        has_calculation = self.calculation_id is not None
        if is_calculated != has_calculation:
            raise ValueError(
                "calculation_id must be set if and only if transformation is 'calculated'"
            )
        return self

    @model_validator(mode="after")
    def _original_source_requires_admin_upload(self) -> ProvenanceCreate:
        if self.original_source is not None and self.provider is not ProviderName.ADMIN_UPLOAD:
            raise ValueError("original_source may only be set when provider is 'admin_upload'")
        return self


class Provenance(ProvenanceCreate):
    """A persisted `provenance` row."""

    id: UUID
    created_at: datetime


class CalculationCreate(BaseModel):
    """Everything needed to create a `calculation` row; id is server-generated."""

    model_config = ConfigDict(frozen=True)

    method: str
    formula_note: str


class Calculation(CalculationCreate):
    """A persisted `calculation` row."""

    id: UUID


class CalculationInputCreate(BaseModel):
    """One provenance record feeding a not-yet-created calculation.

    Deliberately has no `calculation_id`: when creating a calculation and its
    inputs together (`provenance_repository.create_calculation`), the
    calculation's id doesn't exist until the calculation row itself is
    inserted, so it can't be part of what the caller supplies.
    """

    model_config = ConfigDict(frozen=True)

    provenance_id: UUID
    input_role: str | None = None
    sequence_number: int | None = None


class CalculationInput(CalculationInputCreate):
    """A persisted `calculation_input` row (composite PK, no surrogate id)."""

    calculation_id: UUID
