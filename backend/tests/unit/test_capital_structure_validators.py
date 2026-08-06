"""Unit tests for `CapitalStructurePositionCreate` validators (PLAN.md 4.6, section 7).

Mirrors the DB CHECK constraints in app/models/capital_structure.py — the
domain layer is the primary line of defense, see ARCHITECTURE_DECISIONS.md
ADR-014.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.types import CapitalStructureInstrumentType, Seniority
from app.domain.capital_structure import CapitalStructurePositionCreate


def _base_kwargs(**overrides: object) -> dict[str, object]:
    defaults: dict[str, object] = dict(
        issuer_id=uuid4(),
        layer_name="First Lien Term Loan B",
        rank_order=1,
        instrument_type=CapitalStructureInstrumentType.FIRST_LIEN_LOAN,
        seniority=Seniority.FIRST_LIEN,
        secured=True,
        amount_outstanding=Decimal("320000000"),
        provenance_id=uuid4(),
    )
    defaults.update(overrides)
    return defaults


def test_position_synthetic_reason_requires_is_synthetic() -> None:
    with pytest.raises(ValidationError, match="synthetic_reason may only be set"):
        CapitalStructurePositionCreate(
            **_base_kwargs(is_synthetic=False, synthetic_reason="SYNTHETIC_DEMO_DATA")  # type: ignore[arg-type]
        )


def test_position_synthetic_with_reason_is_valid() -> None:
    CapitalStructurePositionCreate(
        **_base_kwargs(is_synthetic=True, synthetic_reason="SYNTHETIC_DEMO_DATA")  # type: ignore[arg-type]
    )


def test_position_without_recovery_figures_needs_no_scenario() -> None:
    position = CapitalStructurePositionCreate(**_base_kwargs())  # type: ignore[arg-type]
    assert position.enterprise_value_coverage is None
    assert position.illustrative_recovery is None
    assert position.recovery_scenario is None


def test_position_with_coverage_requires_recovery_scenario() -> None:
    with pytest.raises(ValidationError, match="recovery_scenario is required"):
        CapitalStructurePositionCreate(
            **_base_kwargs(enterprise_value_coverage=Decimal("1.78"))  # type: ignore[arg-type]
        )


def test_position_with_illustrative_recovery_requires_recovery_scenario() -> None:
    with pytest.raises(ValidationError, match="recovery_scenario is required"):
        CapitalStructurePositionCreate(
            **_base_kwargs(illustrative_recovery=Decimal("100.00"))  # type: ignore[arg-type]
        )


def test_position_with_recovery_figures_and_scenario_is_valid() -> None:
    position = CapitalStructurePositionCreate(
        **_base_kwargs(  # type: ignore[arg-type]
            enterprise_value_coverage=Decimal("1.78"),
            illustrative_recovery=Decimal("100.00"),
            recovery_scenario="Illustrative base-case Enterprise Value of $650,000,000.",
        )
    )
    assert position.enterprise_value_coverage == Decimal("1.78")
    assert position.recovery_scenario is not None


def test_position_security_id_defaults_to_none() -> None:
    """A revolver or equity layer may have no CUSIP-bearing `security` row (PLAN.md 4.6)."""
    position = CapitalStructurePositionCreate(**_base_kwargs())  # type: ignore[arg-type]
    assert position.security_id is None


def test_position_currency_defaults_to_usd() -> None:
    position = CapitalStructurePositionCreate(**_base_kwargs())  # type: ignore[arg-type]
    assert position.currency == "USD"
