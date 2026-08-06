"""Assembles the Capital Structure API response for one issuer (PLAN.md section 7).

Cross-repository orchestration lives here, not in the route (kept thin per
PLAN.md section 3) or the repository (single-table concern) — PLAN.md section
17's `services/` layer, same pattern as `credit_universe_service.py`.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.entitlement import PolicyContext, policy_check
from app.core.freshness import compute_freshness
from app.core.types import DataClassification, EntitlementAction, ProviderName
from app.repositories import capital_structure_repository, issuer_repository, provenance_repository
from app.schemas.capital_structure import CapitalStructurePositionRow, CapitalStructureResponse


def get_capital_structure(db: Session, issuer_id: UUID) -> CapitalStructureResponse | None:
    """`None` when the issuer itself doesn't exist — the route maps that to a 404."""
    issuer = issuer_repository.get_issuer(db, issuer_id)
    if issuer is None:
        return None

    context = PolicyContext(environment=get_settings().environment)
    positions = capital_structure_repository.list_positions_by_issuer(db, issuer_id)

    rows: list[CapitalStructurePositionRow] = []
    for position in positions:
        provenance = provenance_repository.get_provenance(db, position.provenance_id)
        if provenance is None:
            continue
        classification = DataClassification(provenance.classification)
        decision = policy_check(EntitlementAction.DISPLAY, classification, None, context)
        if not decision.allowed:
            continue
        rows.append(
            CapitalStructurePositionRow(
                position_id=position.id,
                security_id=position.security_id,
                layer_name=position.layer_name,
                rank_order=position.rank_order,
                instrument_type=position.instrument_type,
                seniority=position.seniority,
                lien_position=position.lien_position,
                secured=position.secured,
                guarantor_scope=position.guarantor_scope,
                amount_outstanding=position.amount_outstanding,
                currency=position.currency,
                maturity_date=position.maturity_date,
                price=position.price,
                enterprise_value_coverage=position.enterprise_value_coverage,
                illustrative_recovery=position.illustrative_recovery,
                recovery_scenario=position.recovery_scenario,
                is_synthetic=position.is_synthetic,
                synthetic_reason=position.synthetic_reason,
                provider=ProviderName(provenance.provider),
                classification=classification,
                transformation=provenance.transformation,
                as_of_date=provenance.as_of_date,
                retrieved_at=provenance.retrieved_at,
                freshness=compute_freshness(
                    provenance.retrieved_at, ProviderName(provenance.provider)
                ),
            )
        )

    return CapitalStructureResponse(
        issuer_id=issuer.id, issuer_legal_name=issuer.legal_name, positions=rows
    )
