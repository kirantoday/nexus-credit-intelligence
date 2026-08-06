"""SEC EDGAR DTO -> canonical domain object mapping.

The only place SEC-specific shapes (CIKs, XBRL concept tags, SIC codes,
accession numbers) get translated into PLAN.md's provider-neutral canonical
schema (`app/domain/issuer.py`, `app/domain/financial_fact.py`). A future
provider (Bloomberg, S&P Global, ...) would have its own normalizer module
producing the exact same canonical types from its own DTO shapes.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from app.core.types import DataClassification, FormType, ProviderName, TransformationType
from app.domain.financial_fact import FinancialFactCreate
from app.domain.issuer import IssuerCreate
from app.domain.provenance import ProvenanceCreate
from app.providers.sec_edgar.client import format_cik10
from app.providers.sec_edgar.dto import SecSubmissionsDTO, SecXbrlUnitDatapoint

_FORM_TYPE_MAP: dict[str, FormType] = {
    "10-K": FormType.FORM_10K,
    "10-Q": FormType.FORM_10Q,
    "8-K": FormType.FORM_8K,
    "6-K": FormType.FORM_6K,
    "20-F": FormType.FORM_20F,
}


def normalize_issuer_provenance(
    dto: SecSubmissionsDTO,
    *,
    source_url: str,
    retrieved_at: datetime,
    raw_payload_id: UUID,
) -> ProvenanceCreate:
    return ProvenanceCreate(
        provider=ProviderName.SEC_EDGAR,
        source_record_id=format_cik10(dto.cik),
        source_url=source_url,
        as_of_date=retrieved_at.date(),
        retrieved_at=retrieved_at,
        transformation=TransformationType.REPORTED,
        classification=DataClassification.PUBLIC,
        raw_payload_id=raw_payload_id,
    )


def normalize_issuer(dto: SecSubmissionsDTO, *, provenance_id: UUID) -> IssuerCreate:
    """`sic_description` is deliberately left unmapped to `sector`.

    SEC's SIC taxonomy and a GICS-style "sector" (which a future provider like
    Bloomberg might populate) are different classification schemes — mapping
    SIC text into `sector` now would make that column's meaning
    provider-dependent, which is exactly what canonical fields must not be.
    `sic` (the actual code) is populated; `sector` stays unset until a
    provider that reports true sector data exists.
    """
    return IssuerCreate(
        legal_name=dto.name,
        cik=format_cik10(dto.cik),
        lei=dto.lei,
        ticker=dto.tickers[0] if dto.tickers else None,
        sic=dto.sic,
        sector=None,
        provenance_id=provenance_id,
    )


def normalize_financial_fact_provenance(
    datapoint: SecXbrlUnitDatapoint,
    *,
    source_url: str,
    retrieved_at: datetime,
    raw_payload_id: UUID,
) -> ProvenanceCreate:
    return ProvenanceCreate(
        provider=ProviderName.SEC_EDGAR,
        source_record_id=datapoint.accn,
        source_url=source_url,
        as_of_date=date.fromisoformat(datapoint.end),
        retrieved_at=retrieved_at,
        transformation=TransformationType.REPORTED,
        classification=DataClassification.PUBLIC,
        raw_payload_id=raw_payload_id,
    )


def normalize_financial_fact(
    datapoint: SecXbrlUnitDatapoint,
    *,
    issuer_id: UUID,
    concept: str,
    unit: str,
    provenance_id: UUID,
) -> FinancialFactCreate:
    form_type = _FORM_TYPE_MAP.get(datapoint.form)
    if form_type is None:
        raise ValueError(f"unsupported SEC form type: {datapoint.form!r}")
    if datapoint.fy is None or datapoint.fp is None:
        # Real, if uncommon, SEC data (pre-2011-ish datapoints omit these) —
        # see SecXbrlUnitDatapoint's docstring. financial_fact requires both.
        raise ValueError(
            f"datapoint for accession {datapoint.accn!r} is missing fiscal_year/fiscal_period"
        )
    return FinancialFactCreate(
        issuer_id=issuer_id,
        concept=concept,
        value=datapoint.val,
        unit=unit,
        fiscal_period=datapoint.fp,
        fiscal_year=datapoint.fy,
        form_type=form_type,
        filing_date=date.fromisoformat(datapoint.filed),
        accession_no=datapoint.accn,
        provenance_id=provenance_id,
    )
