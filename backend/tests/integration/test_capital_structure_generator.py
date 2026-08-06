"""Integration tests for the synthetic capital structure generator against
the live nexus schema.

Mirrors `test_leveraged_loan_generator.py`'s idempotency-testing style:
these deliberately don't assert `issuer_created` to a fixed True/False,
since whether *this* call creates Cobalt Ridge Energy Corp or finds it
already seeded depends on prior runs (including the real, permanently
committed seed run — see BUILD_LOG.md), not on anything this test controls.
What's actually being proven is data correctness and idempotency.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.types import CapitalStructureInstrumentType, DataClassification, ProviderName
from app.repositories import (
    capital_structure_repository,
    issuer_repository,
    provenance_repository,
    security_repository,
)
from app.synthetic.capital_structure_generator import (
    COBALT_RIDGE_LEGAL_NAME,
    SYNTHETIC_REASON,
    seed_capital_structure_demo,
)


def test_seed_cobalt_ridge_creates_eight_layers_in_rank_order(db_session: Session) -> None:
    result = seed_capital_structure_demo(db_session)

    assert result.issuer.legal_name == COBALT_RIDGE_LEGAL_NAME
    assert result.issuer.is_synthetic is True
    assert result.issuer.synthetic_reason == SYNTHETIC_REASON
    assert result.issuer.cik is None, "a fictional demo issuer must never claim a real CIK"

    positions = capital_structure_repository.list_positions_by_issuer(db_session, result.issuer.id)
    assert [p.rank_order for p in positions] == list(range(1, 9))
    assert [p.instrument_type for p in positions] == [
        CapitalStructureInstrumentType.REVOLVER,
        CapitalStructureInstrumentType.FIRST_LIEN_LOAN,
        CapitalStructureInstrumentType.FIRST_LIEN_NOTES,
        CapitalStructureInstrumentType.SECOND_LIEN,
        CapitalStructureInstrumentType.UNSECURED,
        CapitalStructureInstrumentType.SUBORDINATED,
        CapitalStructureInstrumentType.PREFERRED_EQUITY,
        CapitalStructureInstrumentType.COMMON_EQUITY,
    ]


def test_seed_cobalt_ridge_recovery_figures_match_the_stated_waterfall(
    db_session: Session,
) -> None:
    result = seed_capital_structure_demo(db_session)
    positions = capital_structure_repository.list_positions_by_issuer(db_session, result.issuer.id)
    by_rank = {p.rank_order: p for p in positions}

    # Same figures proven in tests/unit/test_capital_structure_generator.py —
    # this asserts the persisted rows agree with the pure waterfall math.
    assert by_rank[1].illustrative_recovery == Decimal("100.00")  # revolver
    assert by_rank[3].illustrative_recovery == Decimal("100.00")  # 1L notes
    assert by_rank[4].illustrative_recovery == Decimal("77.14")  # 2L notes
    assert by_rank[5].illustrative_recovery == Decimal("0.00")  # senior unsecured
    assert by_rank[8].illustrative_recovery == Decimal("0.00")  # common equity

    for position in positions:
        assert position.recovery_scenario is not None

    # Coverage is only meaningful for debt-like layers, not equity residual claims.
    assert by_rank[2].enterprise_value_coverage is not None  # 1L TLB
    assert by_rank[7].enterprise_value_coverage is None  # preferred equity
    assert by_rank[8].enterprise_value_coverage is None  # common equity


def test_seed_cobalt_ridge_positions_carry_calculated_provenance_with_lineage(
    db_session: Session,
) -> None:
    result = seed_capital_structure_demo(db_session)
    positions = capital_structure_repository.list_positions_by_issuer(db_session, result.issuer.id)
    second_lien = next(
        p for p in positions if p.instrument_type is CapitalStructureInstrumentType.SECOND_LIEN
    )

    provenance = provenance_repository.get_provenance(db_session, second_lien.provenance_id)
    assert provenance is not None
    assert provenance.provider is ProviderName.SYNTHETIC
    assert provenance.classification is DataClassification.SYNTHETIC
    assert provenance.calculation_id is not None

    calculation_inputs = provenance_repository.list_calculation_inputs(
        db_session, provenance.calculation_id
    )
    input_roles = {i.input_role for i in calculation_inputs}
    # Second lien (rank 4) depends on the EV assumption, its own principal,
    # and every strictly-senior layer's principal (revolver, 1L TLB, 1L notes).
    assert input_roles == {"enterprise_value_assumption", "tranche_principal", "senior_principal"}
    senior_inputs = [i for i in calculation_inputs if i.input_role == "senior_principal"]
    assert len(senior_inputs) == 3


def test_seed_cobalt_ridge_first_lien_tlb_has_a_security_row(db_session: Session) -> None:
    result = seed_capital_structure_demo(db_session)
    positions = capital_structure_repository.list_positions_by_issuer(db_session, result.issuer.id)
    tlb = next(
        p for p in positions if p.instrument_type is CapitalStructureInstrumentType.FIRST_LIEN_LOAN
    )
    assert tlb.security_id is not None

    security = security_repository.get_security(db_session, tlb.security_id)
    assert security is not None
    assert security.amount_outstanding == Decimal("320000000")
    assert security.is_synthetic is True


def test_seed_cobalt_ridge_revolver_has_no_security_row(db_session: Session) -> None:
    result = seed_capital_structure_demo(db_session)
    positions = capital_structure_repository.list_positions_by_issuer(db_session, result.issuer.id)
    revolver = next(
        p for p in positions if p.instrument_type is CapitalStructureInstrumentType.REVOLVER
    )
    assert revolver.security_id is None


def test_seed_capital_structure_demo_is_idempotent_within_a_run(db_session: Session) -> None:
    first_run = seed_capital_structure_demo(db_session)
    second_run = seed_capital_structure_demo(db_session)

    assert second_run.issuer_created is False
    assert first_run.issuer.id == second_run.issuer.id
    assert len(first_run.positions) == len(second_run.positions) == 8


def test_seed_reported_layers_for_existing_loan_issuers(db_session: Session) -> None:
    """Milestone 4's leveraged-loan issuers (already permanently committed —
    see BUILD_LOG.md) each get a reported capital_structure_position per
    loan tranche, with no recovery scenario asserted."""
    seed_capital_structure_demo(db_session)

    ridgeline = issuer_repository.get_issuer_by_legal_name(
        db_session, "Ridgeline Industrial Holdings LLC"
    )
    assert ridgeline is not None, "Milestone 4's seed data must already be committed"

    positions = capital_structure_repository.list_positions_by_issuer(db_session, ridgeline.id)
    assert len(positions) >= 1
    for position in positions:
        assert position.is_synthetic is True
        assert position.enterprise_value_coverage is None
        assert position.illustrative_recovery is None
        assert position.recovery_scenario is None
