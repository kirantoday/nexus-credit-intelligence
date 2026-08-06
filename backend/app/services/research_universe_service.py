"""Assembles Research Universes API responses (PLAN.md 24.1, 24.8).

Cross-repository orchestration lives here, not in the route (kept thin per
PLAN.md section 3) or the repository (single-table concern).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.types import CollectionType
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
    """Every Research Universe / Watchlist / Benchmark an issuer belongs to
    — backs Issuer Detail's membership section (PLAN.md 24.9)."""
    collections = collection_repository.list_collections_for_issuer(db, issuer_id)

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
                rationale=membership.rationale,
                rationale_as_of_date=membership.rationale_as_of_date,
            )
        )
    return result
