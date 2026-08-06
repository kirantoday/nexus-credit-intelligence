"""Repository for `capital_structure_position`.

See `provenance_repository.py`'s module docstring for this project's
repository conventions (function-style, domain objects only, flush-not-commit).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.types import CapitalStructureInstrumentType, Seniority
from app.domain.capital_structure import CapitalStructurePosition, CapitalStructurePositionCreate
from app.models.capital_structure import (
    CapitalStructurePosition as CapitalStructurePositionModel,
)


def _to_domain(row: CapitalStructurePositionModel) -> CapitalStructurePosition:
    return CapitalStructurePosition(
        id=row.id,
        issuer_id=row.issuer_id,
        security_id=row.security_id,
        layer_name=row.layer_name,
        rank_order=row.rank_order,
        instrument_type=CapitalStructureInstrumentType(row.instrument_type),
        seniority=Seniority(row.seniority) if row.seniority else None,
        lien_position=row.lien_position,
        secured=row.secured,
        guarantor_scope=row.guarantor_scope,
        amount_outstanding=row.amount_outstanding,
        currency=row.currency,
        maturity_date=row.maturity_date,
        price=row.price,
        enterprise_value_coverage=row.enterprise_value_coverage,
        illustrative_recovery=row.illustrative_recovery,
        recovery_scenario=row.recovery_scenario,
        is_synthetic=row.is_synthetic,
        synthetic_reason=row.synthetic_reason,
        provenance_id=row.provenance_id,
    )


def create_position(db: Session, data: CapitalStructurePositionCreate) -> CapitalStructurePosition:
    row = CapitalStructurePositionModel(
        issuer_id=data.issuer_id,
        security_id=data.security_id,
        layer_name=data.layer_name,
        rank_order=data.rank_order,
        instrument_type=data.instrument_type.value,
        seniority=data.seniority.value if data.seniority else None,
        lien_position=data.lien_position,
        secured=data.secured,
        guarantor_scope=data.guarantor_scope,
        amount_outstanding=data.amount_outstanding,
        currency=data.currency,
        maturity_date=data.maturity_date,
        price=data.price,
        enterprise_value_coverage=data.enterprise_value_coverage,
        illustrative_recovery=data.illustrative_recovery,
        recovery_scenario=data.recovery_scenario,
        is_synthetic=data.is_synthetic,
        synthetic_reason=data.synthetic_reason,
        provenance_id=data.provenance_id,
    )
    db.add(row)
    db.flush()
    db.refresh(row)
    return _to_domain(row)


def get_position(db: Session, position_id: UUID) -> CapitalStructurePosition | None:
    row = db.get(CapitalStructurePositionModel, position_id)
    return _to_domain(row) if row is not None else None


def list_positions_by_issuer(db: Session, issuer_id: UUID) -> list[CapitalStructurePosition]:
    """The full stack for one issuer, top (most senior) to bottom (PLAN.md section 7)."""
    stmt = (
        select(CapitalStructurePositionModel)
        .where(CapitalStructurePositionModel.issuer_id == issuer_id)
        .order_by(CapitalStructurePositionModel.rank_order.asc())
    )
    rows = db.execute(stmt).scalars().all()
    return [_to_domain(row) for row in rows]
