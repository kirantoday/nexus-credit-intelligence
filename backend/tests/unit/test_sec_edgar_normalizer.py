"""Unit tests for the SEC EDGAR DTO parsing and normalizer.

Uses real, trimmed JSON captured from live data.sec.gov responses
(tests/fixtures/sec_edgar/) rather than fabricated data — no network, no
database, but the shapes are genuine, including the real edge case of
datapoints with null fiscal_year/fiscal_period (pre-2011-ish SEC data).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

from app.core.types import DataClassification, FormType, ProviderName, TransformationType
from app.providers.sec_edgar import normalizer
from app.providers.sec_edgar.client import format_cik10
from app.providers.sec_edgar.dto import SecCompanyFactsDTO, SecSubmissionsDTO, SecXbrlUnitDatapoint
from app.providers.sec_edgar.provider import _select_most_recent_datapoint

_FIXTURES = Path(__file__).parent.parent / "fixtures" / "sec_edgar"


@pytest.fixture
def submissions_dto() -> SecSubmissionsDTO:
    raw = json.loads((_FIXTURES / "submissions_aapl_trimmed.json").read_text(encoding="utf-8"))
    return SecSubmissionsDTO.model_validate(raw)


@pytest.fixture
def company_facts_dto() -> SecCompanyFactsDTO:
    raw_text = (_FIXTURES / "companyfacts_aapl_trimmed.json").read_text(encoding="utf-8")
    raw = json.loads(raw_text, parse_float=Decimal)
    return SecCompanyFactsDTO.model_validate(raw)


def test_format_cik10_pads_int() -> None:
    assert format_cik10(320193) == "0000320193"


def test_format_cik10_pads_unpadded_string() -> None:
    assert format_cik10("320193") == "0000320193"


def test_format_cik10_is_idempotent_on_padded_string() -> None:
    assert format_cik10("0000320193") == "0000320193"


def test_submissions_dto_parses_real_shape(submissions_dto: SecSubmissionsDTO) -> None:
    assert submissions_dto.cik == "0000320193"
    assert submissions_dto.name == "Apple Inc."
    assert submissions_dto.sic == "3571"
    assert submissions_dto.tickers == ["AAPL"]
    assert submissions_dto.lei is None


def test_company_facts_dto_parses_real_shape(company_facts_dto: SecCompanyFactsDTO) -> None:
    assert company_facts_dto.entityName == "Apple Inc."
    assert company_facts_dto.cik == 320193
    assert "RevenueFromContractWithCustomerExcludingAssessedTax" in company_facts_dto.facts.us_gaap


def test_company_facts_values_are_decimal_not_float(company_facts_dto: SecCompanyFactsDTO) -> None:
    """The whole point of parse_float=Decimal in client.py: no binary-float
    precision loss on financial values."""
    concept = company_facts_dto.facts.us_gaap["RevenueFromContractWithCustomerExcludingAssessedTax"]
    datapoint = concept.units["USD"][0]
    assert isinstance(datapoint.val, Decimal)


def test_select_most_recent_datapoint_picks_max_end_date(
    company_facts_dto: SecCompanyFactsDTO,
) -> None:
    datapoints = company_facts_dto.facts.us_gaap[
        "RevenueFromContractWithCustomerExcludingAssessedTax"
    ].units["USD"]
    expected = max(datapoints, key=lambda d: d.end)

    selected = _select_most_recent_datapoint(datapoints)

    assert selected == expected


def test_select_most_recent_datapoint_excludes_null_fiscal_metadata(
    company_facts_dto: SecCompanyFactsDTO,
) -> None:
    """Real SEC data: AccountsPayableCurrent has some pre-2011-ish datapoints
    with fy=None/fp=None. The fixture is genuine, not synthesized to include
    this case."""
    datapoints = company_facts_dto.facts.us_gaap["AccountsPayableCurrent"].units["USD"]
    assert any(d.fy is None for d in datapoints), "fixture should contain a real null-fy datapoint"

    selected = _select_most_recent_datapoint(datapoints)

    assert selected.fy is not None
    assert selected.fp is not None


def test_select_most_recent_datapoint_empty_list_raises() -> None:
    with pytest.raises(ValueError, match="no datapoints with complete fiscal"):
        _select_most_recent_datapoint([])


def test_select_most_recent_datapoint_all_null_fiscal_metadata_raises() -> None:
    datapoint = SecXbrlUnitDatapoint(
        end="2010-09-25",
        val=Decimal("100"),
        accn="0000320193-10-000001",
        form="10-K",
        filed="2010-10-27",
    )
    with pytest.raises(ValueError, match="no datapoints with complete fiscal"):
        _select_most_recent_datapoint([datapoint])


def test_normalize_issuer_maps_real_fields(submissions_dto: SecSubmissionsDTO) -> None:
    provenance_id = uuid4()

    issuer = normalizer.normalize_issuer(submissions_dto, provenance_id=provenance_id)

    assert issuer.legal_name == "Apple Inc."
    assert issuer.cik == "0000320193"
    assert issuer.ticker == "AAPL"
    assert issuer.sic == "3571"
    assert issuer.sector is None, "sic_description must not leak into sector (different taxonomy)"
    assert issuer.provenance_id == provenance_id


def test_normalize_issuer_provenance_is_public_reported(submissions_dto: SecSubmissionsDTO) -> None:
    retrieved_at = datetime.now(UTC)

    provenance = normalizer.normalize_issuer_provenance(
        submissions_dto,
        source_url="https://data.sec.gov/submissions/CIK0000320193.json",
        retrieved_at=retrieved_at,
        raw_payload_id=uuid4(),
    )

    assert provenance.provider is ProviderName.SEC_EDGAR
    assert provenance.classification is DataClassification.PUBLIC
    assert provenance.transformation is TransformationType.REPORTED
    assert provenance.source_record_id == "0000320193"


def test_normalize_financial_fact_maps_real_datapoint(
    company_facts_dto: SecCompanyFactsDTO,
) -> None:
    datapoints = company_facts_dto.facts.us_gaap[
        "RevenueFromContractWithCustomerExcludingAssessedTax"
    ].units["USD"]
    datapoint = _select_most_recent_datapoint(datapoints)
    issuer_id = uuid4()
    provenance_id = uuid4()

    fact = normalizer.normalize_financial_fact(
        datapoint,
        issuer_id=issuer_id,
        concept="RevenueFromContractWithCustomerExcludingAssessedTax",
        unit="USD",
        provenance_id=provenance_id,
    )

    assert fact.issuer_id == issuer_id
    assert fact.value == datapoint.val
    assert isinstance(fact.value, Decimal)
    assert fact.fiscal_year == datapoint.fy
    assert fact.fiscal_period == datapoint.fp
    assert fact.accession_no == datapoint.accn
    assert fact.form_type is FormType(datapoint.form)


def test_normalize_financial_fact_rejects_unsupported_form_type() -> None:
    datapoint = SecXbrlUnitDatapoint(
        end="2026-06-17",
        val=Decimal("1"),
        accn="0001140361-26-025622",
        fy=2026,
        fp="Q3",
        form="4",  # a Form 4 insider-trading filing, not a financial-statement form
        filed="2026-06-17",
    )
    with pytest.raises(ValueError, match="unsupported SEC form type"):
        normalizer.normalize_financial_fact(
            datapoint, issuer_id=uuid4(), concept="x", unit="USD", provenance_id=uuid4()
        )


def test_normalize_financial_fact_rejects_missing_fiscal_metadata() -> None:
    datapoint = SecXbrlUnitDatapoint(
        end="2010-09-25",
        val=Decimal("100"),
        accn="0000320193-10-000001",
        form="10-K",
        filed="2010-10-27",
    )
    with pytest.raises(ValueError, match="missing fiscal_year/fiscal_period"):
        normalizer.normalize_financial_fact(
            datapoint, issuer_id=uuid4(), concept="x", unit="USD", provenance_id=uuid4()
        )
