"""Assembles Research Universes API responses (PLAN.md 24.1, 24.8).

Cross-repository orchestration lives here, not in the route (kept thin per
PLAN.md section 3) or the repository (single-table concern).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.types import CollectionType, CurationMethod, VerificationStatus
from app.domain.collection import Collection
from app.repositories import collection_repository
from app.schemas.research_universe import (
    IssuerUniverseMembership,
    ResearchUniverseIssuersResponse,
    ResearchUniverseMembershipRow,
    ResearchUniverseSummary,
)


def _to_summary(db: Session, collection: Collection) -> ResearchUniverseSummary:
    issuer_count = collection_repository.count_members(db, collection.id)
    return ResearchUniverseSummary(
        id=collection.id,
        slug=collection.slug,
        name=collection.name,
        description=collection.description,
        collection_type=collection.collection_type,
        scope=collection.scope,
        visibility=collection.visibility,
        curation_method=collection.curation_method,
        verification_status=collection.verification_status,
        last_verified_at=collection.last_verified_at,
        priority=collection.priority,
        issuer_count=issuer_count,
    )


def list_research_universes(
    db: Session, *, collection_type: CollectionType | None = None
) -> list[ResearchUniverseSummary]:
    collections = collection_repository.list_collections(db, collection_type=collection_type)
    return [_to_summary(db, c) for c in collections]


def get_research_universe(db: Session, collection_id: UUID) -> ResearchUniverseSummary | None:
    collection = collection_repository.get_collection(db, collection_id)
    if collection is None:
        return None
    return _to_summary(db, collection)


def get_research_universe_issuers(
    db: Session, collection_id: UUID
) -> ResearchUniverseIssuersResponse | None:
    """`None` when the universe itself doesn't exist — the route maps that to a 404."""
    collection = collection_repository.get_collection(db, collection_id)
    if collection is None:
        return None

    summary = _to_summary(db, collection)
    rows = collection_repository.list_issuers_for_collection(db, collection_id)
    issuer_rows = [
        ResearchUniverseMembershipRow(
            issuer_id=issuer.id,
            issuer_legal_name=issuer.legal_name,
            issuer_ticker=issuer.ticker,
            rationale=membership.rationale,
            rationale_as_of_date=membership.rationale_as_of_date,
            verification_status=membership.verification_status,
            added_at=membership.added_at,
            system_seeded=membership.system_seeded,
        )
        for issuer, membership in rows
    ]
    return ResearchUniverseIssuersResponse(universe=summary, issuers=issuer_rows)


def get_issuer_universe_memberships(db: Session, issuer_id: UUID) -> list[IssuerUniverseMembership]:
    """Research Universe / Benchmark memberships an issuer belongs to —
    backs Issuer Detail's "Which Research Universes is this issuer in?"
    section (PLAN.md 24.9). Deliberately excludes `collection_type=
    WATCHLIST` (Milestone 8): that section is specifically about
    organization-wide curated research coverage, not an analyst's personal
    tracking lists — a Watchlist an issuer happens to be on is a different
    question, answered by the Watchlist views themselves, not by mixing it
    into this Research-Universe-scoped section."""
    collections = [
        c
        for c in collection_repository.list_collections_for_issuer(db, issuer_id)
        if c.collection_type != CollectionType.WATCHLIST
    ]

    result: list[IssuerUniverseMembership] = []
    for collection in collections:
        membership = collection_repository.get_membership(db, collection.id, issuer_id)
        if membership is None:
            continue
        result.append(
            IssuerUniverseMembership(
                collection_id=collection.id,
                slug=collection.slug,
                name=collection.name,
                collection_type=collection.collection_type,
                curation_method=collection.curation_method,
                rationale=membership.rationale,
                rationale_as_of_date=membership.rationale_as_of_date,
                verification_status=membership.verification_status,
            )
        )
    return result


def get_issuer_universe_memberships_batch(
    db: Session, issuer_ids: list[UUID]
) -> dict[UUID, list[IssuerUniverseMembership]]:
    """Batch form of `get_issuer_universe_memberships` — one query for many
    issuers instead of one query (or more) per issuer. Same
    `collection_type=WATCHLIST` exclusion applies. Backs Watchlist detail's
    per-issuer "current status" column (Milestone 8), which would otherwise
    N+1 across up to dozens of watched issuers."""
    by_issuer = collection_repository.list_collections_with_membership_for_issuers(db, issuer_ids)
    result: dict[UUID, list[IssuerUniverseMembership]] = {}
    for issuer_id, pairs in by_issuer.items():
        result[issuer_id] = [
            IssuerUniverseMembership(
                collection_id=collection.id,
                slug=collection.slug,
                name=collection.name,
                collection_type=collection.collection_type,
                curation_method=collection.curation_method,
                rationale=membership.rationale,
                rationale_as_of_date=membership.rationale_as_of_date,
                verification_status=membership.verification_status,
            )
            for collection, membership in pairs
            if collection.collection_type != CollectionType.WATCHLIST
        ]
    return result


def derive_current_status(memberships: list[IssuerUniverseMembership]) -> list[str]:
    """Collapses an issuer's Research Universe memberships into the small
    set of names safe to state as its current status — shared by the Issuer
    Distress Timeline (PLAN.md Milestone 7.5.4) and Watchlist detail
    (Milestone 8), so "current status" means exactly one thing everywhere
    it's shown. Only `verified` memberships qualify — a `partial`
    (system-suggested, unconfirmed) one must never read as a settled fact.
    Manually-curated names are the polished, product-facing labels used
    elsewhere in the app; System-Detected: * universes are shown (prefix
    stripped) only when no curated membership is verified — never both,
    which would just state the same real status twice under different
    names."""
    verified = [m for m in memberships if m.verification_status == VerificationStatus.VERIFIED]
    curated = {m.name for m in verified if m.curation_method == CurationMethod.MANUAL_CURATED}
    if curated:
        return sorted(curated)
    return sorted({m.name.removeprefix("System-Detected: ") for m in verified})
