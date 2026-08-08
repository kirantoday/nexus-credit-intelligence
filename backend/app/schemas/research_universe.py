"""Response schemas for the Research Universes API (PLAN.md section 24.1, 24.8).

Research Universes and Watchlists share one underlying `collection` table
(ADR-016), distinguished by `collection_type` — the API surfaces that same
distinction rather than hiding it.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.core.types import (
    CollectionPriority,
    CollectionScope,
    CollectionType,
    CollectionVisibility,
    CurationMethod,
    VerificationStatus,
)


class ResearchUniverseSummary(BaseModel):
    """One Research Universe / Watchlist / Benchmark collection, with its
    member count — the row shape for the Research Universes listing page."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    slug: str
    name: str
    description: str
    collection_type: CollectionType
    scope: CollectionScope
    visibility: CollectionVisibility
    curation_method: CurationMethod
    verification_status: VerificationStatus
    last_verified_at: datetime | None
    priority: CollectionPriority | None
    issuer_count: int


class ResearchUniverseListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    universes: list[ResearchUniverseSummary]


class ResearchUniverseMembershipRow(BaseModel):
    """One issuer's membership in one collection — used on both the
    Research Universes detail page and Issuer Detail's membership section.
    Never asserts current status: `rationale` + `rationale_as_of_date` are
    dated text a human wrote/verified (PLAN.md 24.1)."""

    model_config = ConfigDict(frozen=True)

    issuer_id: UUID
    issuer_legal_name: str
    issuer_ticker: str | None
    rationale: str
    rationale_as_of_date: date | None
    verification_status: VerificationStatus
    added_at: datetime
    system_seeded: bool


class ResearchUniverseIssuersResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    universe: ResearchUniverseSummary
    issuers: list[ResearchUniverseMembershipRow]


class IssuerUniverseMembership(BaseModel):
    """A universe an issuer belongs to — shown on Issuer Detail, clearly
    separated from factual-status sections (PLAN.md 24.9).

    `verification_status` distinguishes an analyst-verified/definitive-
    evidence membership (`verified`) from a system-suggested one
    (`partial`, pending analyst confirmation) — surfaced explicitly per
    Milestone 7.5.1 section 4: a `partial` membership must never read as a
    settled fact in the UI."""

    model_config = ConfigDict(frozen=True)

    collection_id: UUID
    slug: str
    name: str
    collection_type: CollectionType
    rationale: str
    rationale_as_of_date: date | None
    verification_status: VerificationStatus
