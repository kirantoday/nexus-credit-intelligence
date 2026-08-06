"""Repository for the provenance spine: `provenance`, `calculation`, `calculation_input`.

Per PLAN.md section 3, this is the only module allowed to open a SQLAlchemy
session for these tables. Functions take an explicit `Session` as their first
argument (module-level functions, not a stateful repository class) — this
project's established repository convention (see ARCHITECTURE_DECISIONS.md
ADR-014): callers pass/receive canonical domain objects only, never a
SQLAlchemy model instance.

Every function `flush()`s but never `commit()`s — the caller (a FastAPI
request's `get_db` dependency, or a test's transaction fixture) owns the
transaction boundary. `flush()` is enough to populate server-generated columns
(`id`, `created_at`) via Postgres's `RETURNING`.

Provenance and calculation rows are treated as immutable/append-only once
created, matching the domain's audit-trail semantics — there are intentionally
no update functions here.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.types import DataClassification, OriginalSource, ProviderName, TransformationType
from app.domain.provenance import (
    Calculation,
    CalculationCreate,
    CalculationInput,
    CalculationInputCreate,
    Provenance,
    ProvenanceCreate,
)
from app.models.provenance import Calculation as CalculationModel
from app.models.provenance import CalculationInput as CalculationInputModel
from app.models.provenance import Provenance as ProvenanceModel


def _provenance_to_domain(row: ProvenanceModel) -> Provenance:
    return Provenance(
        id=row.id,
        provider=ProviderName(row.provider),
        original_source=OriginalSource(row.original_source) if row.original_source else None,
        source_attested_by=row.source_attested_by,
        source_attested_at=row.source_attested_at,
        source_record_id=row.source_record_id,
        source_url=row.source_url,
        as_of_date=row.as_of_date,
        retrieved_at=row.retrieved_at,
        transformation=TransformationType(row.transformation),
        classification=DataClassification(row.classification),
        calculation_id=row.calculation_id,
        raw_payload_id=row.raw_payload_id,
        created_at=row.created_at,
    )


def _calculation_to_domain(row: CalculationModel) -> Calculation:
    return Calculation(id=row.id, method=row.method, formula_note=row.formula_note)


def _calculation_input_to_domain(row: CalculationInputModel) -> CalculationInput:
    return CalculationInput(
        calculation_id=row.calculation_id,
        provenance_id=row.provenance_id,
        input_role=row.input_role,
        sequence_number=row.sequence_number,
    )


def create_provenance(db: Session, data: ProvenanceCreate) -> Provenance:
    row = ProvenanceModel(
        provider=data.provider.value,
        original_source=data.original_source.value if data.original_source else None,
        source_attested_by=data.source_attested_by,
        source_attested_at=data.source_attested_at,
        source_record_id=data.source_record_id,
        source_url=data.source_url,
        as_of_date=data.as_of_date,
        retrieved_at=data.retrieved_at,
        transformation=data.transformation.value,
        classification=data.classification.value,
        calculation_id=data.calculation_id,
        raw_payload_id=data.raw_payload_id,
    )
    db.add(row)
    db.flush()
    db.refresh(row)
    return _provenance_to_domain(row)


def get_provenance(db: Session, provenance_id: UUID) -> Provenance | None:
    row = db.get(ProvenanceModel, provenance_id)
    return _provenance_to_domain(row) if row is not None else None


def create_calculation(
    db: Session,
    data: CalculationCreate,
    inputs: Sequence[CalculationInputCreate] = (),
) -> Calculation:
    """Create a `calculation` row and its `calculation_input` rows atomically."""
    calc_row = CalculationModel(method=data.method, formula_note=data.formula_note)
    db.add(calc_row)
    db.flush()

    for input_data in inputs:
        db.add(
            CalculationInputModel(
                calculation_id=calc_row.id,
                provenance_id=input_data.provenance_id,
                input_role=input_data.input_role,
                sequence_number=input_data.sequence_number,
            )
        )
    if inputs:
        db.flush()

    db.refresh(calc_row)
    return _calculation_to_domain(calc_row)


def get_calculation(db: Session, calculation_id: UUID) -> Calculation | None:
    row = db.get(CalculationModel, calculation_id)
    return _calculation_to_domain(row) if row is not None else None


def list_calculation_inputs(db: Session, calculation_id: UUID) -> list[CalculationInput]:
    stmt = select(CalculationInputModel).where(
        CalculationInputModel.calculation_id == calculation_id
    )
    rows = db.execute(stmt).scalars().all()
    return [_calculation_input_to_domain(row) for row in rows]
