"""Unit tests for app/providers/openfigi/normalizer.py.

Ticker examples are taken verbatim from a real, live OpenFIGI search for
"APPLE INC" (`marketSecDes="Corp"`) during Milestone 5 development, not
invented.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

from app.core.types import DataClassification, InstrumentType, ProviderName, TransformationType
from app.providers.openfigi.dto import OpenFigiSearchResult
from app.providers.openfigi.normalizer import (
    normalize_bond_provenance,
    normalize_bond_security,
    parse_coupon_and_maturity,
)


def test_parse_coupon_and_maturity_from_fixed_rate_ticker() -> None:
    assert parse_coupon_and_maturity("AAPL 3.85 05/04/43") == (
        Decimal("3.85"),
        date(2043, 5, 4),
    )


def test_parse_coupon_and_maturity_from_whole_number_coupon() -> None:
    assert parse_coupon_and_maturity("AAPL 4 05/12/28") == (Decimal("4"), date(2028, 5, 12))


def test_parse_coupon_and_maturity_ignores_trailing_suffix() -> None:
    assert parse_coupon_and_maturity("AAPL 1 11/10/22 EMTN") == (
        Decimal("1"),
        date(2022, 11, 10),
    )


def test_parse_maturity_only_for_floating_rate_ticker() -> None:
    """ "F" is OpenFIGI's floating-rate marker, not a numeric coupon — the
    coupon must stay honestly None rather than parsed as garbage."""
    coupon, maturity = parse_coupon_and_maturity("AAPL F 08/28/19 MTn")
    assert coupon is None
    assert maturity == date(2019, 8, 28)


def test_parse_coupon_and_maturity_returns_none_for_unrecognized_shape() -> None:
    assert parse_coupon_and_maturity("APPLE INC") == (None, None)


def _sample_result(**overrides: object) -> OpenFigiSearchResult:
    defaults: dict[str, object] = dict(
        figi="BBG004HST0K7",
        name="APPLE INC",
        ticker="AAPL 3.85 05/04/43",
        exchCode="TRACE",
        marketSector="Corp",
        securityType2="Corp",
    )
    defaults.update(overrides)
    return OpenFigiSearchResult(**defaults)  # type: ignore[arg-type]


def test_normalize_bond_security_never_fabricates_cusip_or_isin() -> None:
    security = normalize_bond_security(
        _sample_result(),
        issuer_id=uuid4(),
        issuer_legal_name="Apple Inc.",
        provenance_id=uuid4(),
    )
    assert security.cusip is None
    assert security.isin is None
    assert security.figi == "BBG004HST0K7"
    assert security.instrument_type is InstrumentType.BOND
    assert security.coupon == Decimal("3.85")
    assert security.maturity_date == date(2043, 5, 4)
    assert security.is_synthetic is False
    assert "Apple Inc." in security.description
    assert "AAPL 3.85 05/04/43" in security.description


def test_normalize_bond_security_leaves_unreported_terms_none() -> None:
    """OpenFIGI is an identification service, not a terms/pricing one."""
    security = normalize_bond_security(
        _sample_result(), issuer_id=uuid4(), issuer_legal_name="Apple Inc.", provenance_id=uuid4()
    )
    assert security.seniority is None
    assert security.lien_position is None
    assert security.secured is None
    assert security.amount_outstanding is None
    assert security.benchmark is None
    assert security.spread is None


def test_normalize_bond_provenance_is_public_reported_openfigi() -> None:
    retrieved_at = datetime(2026, 8, 6, 12, 0, 0)
    provenance = normalize_bond_provenance(
        _sample_result(),
        source_url="https://api.openfigi.com/v3/search",
        retrieved_at=retrieved_at,
        raw_payload_id=uuid4(),
    )
    assert provenance.provider is ProviderName.OPENFIGI
    assert provenance.source_record_id == "BBG004HST0K7"
    assert provenance.classification is DataClassification.PUBLIC
    assert provenance.transformation is TransformationType.REPORTED
    assert provenance.as_of_date == retrieved_at.date()
