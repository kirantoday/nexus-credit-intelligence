"""Unit tests for `compute_recovery_waterfall` (PLAN.md section 7's
illustrative recovery math) — a pure function, no database needed.

The Cobalt Ridge Energy Corp numbers exercised here are the same figures
`app/synthetic/capital_structure_generator.py` seeds for real: $45M revolver,
$320M 1L TLB, $150M 1L notes, $175M 2L notes, $225M senior unsecured, $100M
subordinated, against a stated $650M base-case Enterprise Value — chosen so
the first three layers are fully covered, the second lien is partially
covered, and everything junior to it recovers nothing, a realistic distressed
shape worth testing precisely.
"""

from __future__ import annotations

from decimal import Decimal

from app.synthetic.capital_structure_generator import compute_recovery_waterfall

_COBALT_RIDGE_AMOUNTS = [
    Decimal("45000000"),  # revolver
    Decimal("320000000"),  # 1L TLB
    Decimal("150000000"),  # 1L notes
    Decimal("175000000"),  # 2L notes
    Decimal("225000000"),  # senior unsecured
    Decimal("100000000"),  # subordinated
]
_COBALT_RIDGE_EV = Decimal("650000000")


def test_waterfall_fully_covers_senior_layers() -> None:
    results = compute_recovery_waterfall(_COBALT_RIDGE_AMOUNTS, _COBALT_RIDGE_EV)

    assert results[0].recovery_pct == Decimal("100.00")  # revolver: cum 45M <= 650M
    assert results[1].recovery_pct == Decimal("100.00")  # 1L TLB: cum 365M <= 650M
    assert results[2].recovery_pct == Decimal("100.00")  # 1L notes: cum 515M <= 650M


def test_waterfall_partially_covers_the_layer_ev_runs_out_on() -> None:
    results = compute_recovery_waterfall(_COBALT_RIDGE_AMOUNTS, _COBALT_RIDGE_EV)

    # 2L notes: 650M - 515M = 135M of its 175M principal is reachable.
    assert results[3].recovery_pct == Decimal("77.14")


def test_waterfall_wipes_out_layers_junior_to_the_shortfall() -> None:
    results = compute_recovery_waterfall(_COBALT_RIDGE_AMOUNTS, _COBALT_RIDGE_EV)

    assert results[4].recovery_pct == Decimal("0.00")  # senior unsecured
    assert results[5].recovery_pct == Decimal("0.00")  # subordinated


def test_waterfall_coverage_is_ev_over_cumulative_principal() -> None:
    results = compute_recovery_waterfall(_COBALT_RIDGE_AMOUNTS, _COBALT_RIDGE_EV)

    assert results[0].coverage == Decimal("14.44")  # 650M / 45M
    assert results[1].coverage == Decimal("1.78")  # 650M / 365M
    assert results[5].coverage == Decimal("0.64")  # 650M / 1,015M


def test_waterfall_single_layer_fully_covered() -> None:
    results = compute_recovery_waterfall([Decimal("100")], Decimal("500"))
    assert results[0].recovery_pct == Decimal("100.00")
    assert results[0].coverage == Decimal("5.00")


def test_waterfall_single_layer_zero_enterprise_value() -> None:
    results = compute_recovery_waterfall([Decimal("100")], Decimal("0"))
    assert results[0].recovery_pct == Decimal("0.00")
    assert results[0].coverage == Decimal("0.00")


def test_waterfall_empty_amounts_returns_empty() -> None:
    assert compute_recovery_waterfall([], Decimal("500")) == []
