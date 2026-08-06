"""Provider DTOs for OpenFIGI — mirror api.openfigi.com's real JSON response
shapes closely enough to parse them, not exhaustively (unused fields ignored
via `extra="ignore"`, not modeled). Verified against live requests during
Milestone 5 development (`POST /v3/search`, query "APPLE INC").

DTOs are allowed to be provider-specific, unlike canonical domain objects
(`app/domain/**`) — these field names match OpenFIGI's API verbatim; the
normalizer (`normalizer.py`) is the only place that translation happens.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class OpenFigiSearchResult(BaseModel):
    """One instrument from `POST /v3/search`'s `data` array.

    OpenFIGI's public search/mapping API does NOT return CUSIP/ISIN as output
    fields (confirmed live — Bloomberg/ANNA license those separately from
    FIGI) — there is no `cusip`/`isin` field to model here at all, not a
    field this DTO happens to leave unset. `ticker` for a corporate bond
    (`marketSector = "Corp"`) is OpenFIGI's own free-text convention encoding
    coupon + maturity, e.g. `"AAPL 3.85 05/04/43"` — `normalizer.py` parses
    it, it isn't a separate structured field OpenFIGI provides.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    figi: str
    name: str
    ticker: str
    exchCode: str | None = None
    compositeFIGI: str | None = None
    securityType: str | None = None
    securityType2: str | None = None
    marketSector: str
    shareClassFIGI: str | None = None
    securityDescription: str | None = None


class OpenFigiSearchResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    data: list[OpenFigiSearchResult] = Field(default_factory=list)
    error: str | None = None
