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


class SecSubmissionsDTO(BaseModel):
    """`GET https://data.sec.gov/submissions/CIK{cik10}.json` — issuer identity fields only.

    The full response also includes filing history (`filings.recent`), which
    this DTO doesn't model: Milestone 3 identifies "the filing" a financial
    fact came from via the XBRL datapoint itself (`SecXbrlUnitDatapoint.accn`/
    `.filed`/`.form`), not by cross-referencing the submissions filing list.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    cik: str
    name: str
    sic: str | None = None
    sicDescription: str | None = None
    tickers: list[str] = Field(default_factory=list)
    exchanges: list[str] = Field(default_factory=list)
    lei: str | None = None


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
