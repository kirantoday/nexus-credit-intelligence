"""Response/request schemas for the Watchlists API (PLAN.md section 24.1;
Milestone 8).

Watchlists are `collection` rows with `collection_type=watchlist` (ADR-016)
— an analyst's personal "which issuers do I care about" list, distinct from
the organization-curated Research Universes that share the same table. This
module's job is purely presentation/aggregation of already-persisted data
(alerts, memberships, securities): no new intelligence is created here, and
building these responses makes zero Anthropic calls.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.types import EvidenceSeverity


class WatchlistSummary(BaseModel):
    """One Watchlist, with the roll-up counts an analyst dashboard needs —
    the row shape for the Watchlists landing page."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    slug: str
    name: str
    description: str
    issuer_count: int
    issuers_with_new_developments: int
    high_severity_count: int
    last_activity_at: datetime | None
    created_at: datetime
    updated_at: datetime
    # Only populated when the request supplied `issuer_id` — lets the
    # "Add to Watchlist" component show already-added state without a
    # second round trip per watchlist.
    contains_issuer: bool | None = None


class WatchlistListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    watchlists: list[WatchlistSummary]


class WatchlistCreateRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1, max_length=200)
    description: str = ""


class WatchlistUpdateRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None


class WatchlistIssuerRow(BaseModel):
    """One watched issuer, with the latest-development context Phase 4
    requires — assembled entirely from existing alert/membership/security
    data, never a new fact the Watchlist itself asserts."""

    model_config = ConfigDict(frozen=True)

    issuer_id: UUID
    issuer_legal_name: str
    issuer_ticker: str | None
    current_status: list[str]
    latest_development_headline: str | None
    latest_development_date: date | None
    severity: EvidenceSeverity | None
    new_developments_count: int
    securities_count: int
    rationale: str
    added_at: datetime


class WatchlistDetailResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    watchlist: WatchlistSummary
    issuers: list[WatchlistIssuerRow]


class AddIssuerToWatchlistRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    issuer_id: UUID
    rationale: str = "Added to watchlist"
