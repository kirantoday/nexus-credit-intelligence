"""SEC EDGAR DTO -> canonical domain object mapping.

The only place SEC-specific shapes (CIKs, XBRL concept tags, SIC codes,
accession numbers) get translated into PLAN.md's provider-neutral canonical
schema (`app/domain/issuer.py`, `app/domain/financial_fact.py`). A future
provider (Bloomberg, S&P Global, ...) would have its own normalizer module
producing the exact same canonical types from its own DTO shapes.
"""

from __future__ import annotations

from datetime import date, datetime
from html.parser import HTMLParser
from uuid import UUID

from app.core.types import (
    DataClassification,
    FormType,
    InstrumentType,
    ProviderName,
    TransformationType,
)
from app.domain.financial_fact import FinancialFactCreate
from app.domain.issuer import IssuerCreate
from app.domain.provenance import ProvenanceCreate
from app.domain.sec_filing import SecFilingCreate
from app.domain.security import SecurityCreate
from app.providers.sec_edgar.client import format_cik10
from app.providers.sec_edgar.dto import SecFilingEntryDTO, SecSubmissionsDTO, SecXbrlUnitDatapoint

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


def normalize_bond_provenance(
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


def normalize_bond_security(
    datapoint: SecXbrlUnitDatapoint,
    *,
    issuer_id: UUID,
    issuer_legal_name: str,
    provenance_id: UUID,
) -> SecurityCreate:
    """A real, SEC-reported aggregate debt figure represented as one
    `security` row — deliberately *not* presented as a specific,
    CUSIP-identified bond issue.

    SEC's company-facts API reports debt at the balance-sheet aggregate level
    (e.g. `LongTermDebtNoncurrent`), not per-instrument/tranche — genuine
    per-issue detail (a specific note's own CUSIP, coupon, maturity) would
    require parsing full XBRL dimensional data, which this project's simple
    company-facts client doesn't do. `seniority`, `lien_position`, `secured`,
    `cusip`/`isin`/`figi`, `maturity_date`, and `coupon` are left genuinely
    unknown (`None`) rather than guessed at — the `description` says exactly
    what this figure is so it's never mistaken for a specific issue.
    """
    return SecurityCreate(
        issuer_id=issuer_id,
        instrument_type=InstrumentType.BOND,
        seniority=None,
        lien_position=None,
        secured=None,
        cusip=None,
        isin=None,
        figi=None,
        description=(
            f"{issuer_legal_name} — Long-Term Debt "
            "(SEC XBRL aggregate; not a specific instrument)"
        ),
        maturity_date=None,
        coupon=None,
        amount_outstanding=datapoint.val,
        benchmark=None,
        spread=None,
        is_synthetic=False,
        synthetic_reason=None,
        provenance_id=provenance_id,
    )


def normalize_sec_filing_provenance(
    entry: SecFilingEntryDTO,
    *,
    source_url: str,
    retrieved_at: datetime,
    raw_payload_id: UUID,
) -> ProvenanceCreate:
    return ProvenanceCreate(
        provider=ProviderName.SEC_EDGAR,
        source_record_id=entry.accession_no,
        source_url=source_url,
        as_of_date=date.fromisoformat(entry.filing_date),
        retrieved_at=retrieved_at,
        transformation=TransformationType.REPORTED,
        classification=DataClassification.PUBLIC,
        raw_payload_id=raw_payload_id,
    )


def normalize_sec_filing(
    entry: SecFilingEntryDTO,
    *,
    issuer_id: UUID,
    primary_document_url: str | None,
    provenance_id: UUID,
) -> SecFilingCreate:
    return SecFilingCreate(
        issuer_id=issuer_id,
        accession_no=entry.accession_no,
        form_type=entry.form,
        filing_date=date.fromisoformat(entry.filing_date),
        period_of_report=date.fromisoformat(entry.report_date) if entry.report_date else None,
        is_amendment=entry.form.endswith("/A"),
        primary_document=entry.primary_document,
        primary_document_url=primary_document_url,
        provenance_id=provenance_id,
    )


def normalize_filing_document_provenance(
    *,
    accession_no: str,
    filing_date: date,
    source_url: str,
    retrieved_at: datetime,
    raw_payload_id: UUID,
) -> ProvenanceCreate:
    """Provenance for a fetched filing *document* (the body, for text/evidence
    extraction) — a distinct retrieval event from the filing-metadata
    provenance `sec_filing.provenance_id` already carries.
    """
    return ProvenanceCreate(
        provider=ProviderName.SEC_EDGAR,
        source_record_id=accession_no,
        source_url=source_url,
        as_of_date=filing_date,
        retrieved_at=retrieved_at,
        transformation=TransformationType.REPORTED,
        classification=DataClassification.PUBLIC,
        raw_payload_id=raw_payload_id,
    )


class _TextExtractingHTMLParser(HTMLParser):
    """Minimal stdlib HTML-to-text extractor — no new dependency for what is,
    for rule-matching purposes, just "the visible words in the document."
    Skips `<script>`/`<style>` contents; does not attempt layout fidelity.
    """

    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style"):
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style") and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0 and data.strip():
            self._chunks.append(data.strip())

    def get_text(self) -> str:
        return " ".join(self._chunks)


def extract_filing_text(html: str) -> str:
    """Plain visible text from a filing's HTML body, for deterministic rule
    matching (PLAN.md 24.4) — not a layout-preserving conversion.
    """
    parser = _TextExtractingHTMLParser()
    parser.feed(html)
    return parser.get_text()
