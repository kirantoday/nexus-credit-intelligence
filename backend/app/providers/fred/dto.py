"""Provider DTOs for FRED — mirror api.stlouisfed.org's real JSON response
shapes closely enough to parse them, not exhaustively (unused fields ignored
via `extra="ignore"`, not modeled). Verified against live requests during
Milestone 5 development (`/fred/series` and `/fred/series/observations` for
series `SOFR` and `BAMLH0A0HYM2`).

DTOs are allowed to be provider-specific, unlike canonical domain objects
(`app/domain/**`) — these field names match FRED's API verbatim; the
normalizer (`normalizer.py`) is the only place that translation happens.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class FredSeriesInfo(BaseModel):
    """One entry in `/fred/series`'s `seriess` array.

    FRED's real response has no `category` field (a series' category
    requires a separate `/fred/category` call this project doesn't make) and
    no explicit `discontinued`/`redistribution_allowed` booleans — see
    `app/domain/fred.py`'s module docstring for how those three registry
    fields are actually populated (not parsed off this DTO).
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    id: str
    title: str
    units: str
    frequency: str
    observation_start: str
    observation_end: str
    last_updated: str


class FredSeriesResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    seriess: list[FredSeriesInfo] = Field(default_factory=list)


class FredObservationEntry(BaseModel):
    """One entry in `/fred/series/observations`'s `observations` array.

    `value` is a string, not a number — FRED represents a missing
    observation (e.g. a market holiday on a "daily" series) as the literal
    string `"."`, which a numeric field couldn't hold. `normalizer.py`
    filters those out rather than persisting a fabricated/null fact for that
    date (see `app/domain/fred.py`'s `FredObservationCreate` docstring).
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    date: str
    value: str


class FredObservationsResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    observations: list[FredObservationEntry] = Field(default_factory=list)
