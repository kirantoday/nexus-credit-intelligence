"""Provider DTOs for SEC EDGAR — mirror data.sec.gov's real JSON response
shapes closely enough to parse them, not exhaustively (unused fields are
ignored via `extra="ignore"`, not modeled). Verified against live requests
during Milestone 3 development (CIK 0000320193 / Apple Inc.).

DTOs are allowed to be provider-specific, unlike canonical domain objects
(`app/domain/**`) — these field names match SEC's API verbatim; the
normalizer (`normalizer.py`) is the only place that translation happens.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class SecFilingsRecent(BaseModel):
    """`filings.recent` — SEC's real shape: parallel arrays, one index per
    filing, not a list of filing objects. `items` is a comma-separated string
    of 8-K item numbers (e.g. `"1.03,2.03"`) when `form` is `8-K`, empty
    otherwise — a real, free signal for bankruptcy/Item-1.03 detection
    (PLAN.md 24.4) without parsing the filing document body.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    accessionNumber: list[str] = Field(default_factory=list)
    filingDate: list[str] = Field(default_factory=list)
    reportDate: list[str] = Field(default_factory=list)
    form: list[str] = Field(default_factory=list)
    items: list[str] = Field(default_factory=list)
    primaryDocument: list[str] = Field(default_factory=list)


class SecFilings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    recent: SecFilingsRecent = Field(default_factory=SecFilingsRecent)


class SecFilingEntryDTO(BaseModel):
    """One filing, zipped out of `SecFilingsRecent`'s parallel arrays by
    `recent_filing_entries` below — provider-shaped (SEC field names/format),
    translated into canonical `SecFilingCreate` only in `normalizer.py`.
    """

    model_config = ConfigDict(frozen=True)

    accession_no: str
    filing_date: str
    report_date: str | None
    form: str
    items: str | None
    primary_document: str | None


class SecSubmissionsDTO(BaseModel):
    """`GET https://data.sec.gov/submissions/CIK{cik10}.json`.

    `filings` (added in Milestone 6.5) was deliberately omitted in Milestone
    3 — see the historical note in `normalize_issuer`'s docstring context —
    because financial facts identify their own filing via the XBRL datapoint
    itself. The overnight filing monitor (PLAN.md 24.5) needs the actual
    filing list, so it's modeled now.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    cik: str
    name: str
    sic: str | None = None
    sicDescription: str | None = None
    tickers: list[str] = Field(default_factory=list)
    exchanges: list[str] = Field(default_factory=list)
    lei: str | None = None
    filings: SecFilings = Field(default_factory=SecFilings)


def recent_filing_entries(dto: SecSubmissionsDTO) -> list[SecFilingEntryDTO]:
    """Zip `filings.recent`'s parallel arrays into one entry per filing.

    Uses `zip()` (stops at the shortest array) rather than asserting equal
    lengths — a defensively-parsed real-world response is preferable to a
    hard crash on an SEC response shape this project hasn't seen before.
    """
    recent = dto.filings.recent
    entries: list[SecFilingEntryDTO] = []
    for accession_no, filing_date, report_date, form, items, primary_document in zip(
        recent.accessionNumber,
        recent.filingDate,
        recent.reportDate,
        recent.form,
        recent.items,
        recent.primaryDocument,
        strict=False,
    ):
        entries.append(
            SecFilingEntryDTO(
                accession_no=accession_no,
                filing_date=filing_date,
                report_date=report_date or None,
                form=form,
                items=items or None,
                primary_document=primary_document or None,
            )
        )
    return entries


class SecXbrlUnitDatapoint(BaseModel):
    """One value for one us-gaap concept, in one unit, for one filing/period.

    `fy`/`fp` are genuinely nullable in SEC's real data — older datapoints
    (roughly pre-2011, early XBRL adoption) omit fiscal year/period tagging
    entirely. `normalizer.py` only ever selects datapoints where both are
    present (a `financial_fact` row requires them), but the DTO itself must
    accept the real shape or parsing fails on legitimate historical data.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    end: str
    val: Decimal
    accn: str
    fy: int | None = None
    fp: str | None = None
    form: str
    filed: str


class SecXbrlConcept(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    units: dict[str, list[SecXbrlUnitDatapoint]]


class SecCompanyFactsFacts(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    us_gaap: dict[str, SecXbrlConcept] = Field(default_factory=dict, alias="us-gaap")


class SecCompanyFactsDTO(BaseModel):
    """`GET https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10}.json`."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    cik: int
    entityName: str
    facts: SecCompanyFactsFacts
