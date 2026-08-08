"""Integration tests for research_universe_service against the live nexus schema."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.types import (
    CollectionScope,
    CollectionType,
    CollectionVisibility,
    CurationMethod,
    VerificationStatus,
)
from app.domain.collection import Collection, CollectionCreate, CollectionMembershipCreate
from app.domain.issuer import Issuer, IssuerCreate
from app.repositories import collection_repository, issuer_repository, provenance_repository
from app.services import research_universe_service
from tests.integration.conftest import reported_public_provenance


def _seed_issuer(db: Session, *, legal_name: str) -> Issuer:
    provenance = provenance_repository.create_provenance(db, reported_public_provenance())
    return issuer_repository.create_issuer(
        db, IssuerCreate(legal_name=legal_name, provenance_id=provenance.id)
    )


def _seed_universe(
    db: Session, *, slug: str, collection_type: CollectionType = CollectionType.RESEARCH_UNIVERSE
) -> Collection:
    return collection_repository.create_collection(
        db,
        CollectionCreate(
            slug=slug,
            name=f"Test {slug}",
            description="Seeded for research_universe_service tests.",
            collection_type=collection_type,
            scope=CollectionScope.ORGANIZATION,
            visibility=CollectionVisibility.PUBLIC,
            curation_method=CurationMethod.SYSTEM_SEEDED,
            verification_status=VerificationStatus.VERIFIED,
        ),
    )


def test_list_research_universes_includes_issuer_count(db_session: Session) -> None:
    slug = f"test-universe-{uuid4()}"
    universe = _seed_universe(db_session, slug=slug)
    issuer = _seed_issuer(db_session, legal_name=f"Universe Service Test Co {uuid4()}")
    collection_repository.add_membership(
        db_session,
        CollectionMembershipCreate(
            collection_id=universe.id,
            issuer_id=issuer.id,
            rationale="Test membership.",
            verification_status=VerificationStatus.VERIFIED,
        ),
    )

    universes = research_universe_service.list_research_universes(db_session)

    match = next(u for u in universes if u.slug == slug)
    assert match.issuer_count == 1


def test_get_research_universe_returns_none_for_unknown_id(db_session: Session) -> None:
    result = research_universe_service.get_research_universe(db_session, uuid4())
    assert result is None


def test_get_research_universe_issuers_includes_rationale(db_session: Session) -> None:
    slug = f"test-universe-{uuid4()}"
    universe = _seed_universe(db_session, slug=slug)
    issuer = _seed_issuer(db_session, legal_name=f"Universe Rationale Test Co {uuid4()}")
    collection_repository.add_membership(
        db_session,
        CollectionMembershipCreate(
            collection_id=universe.id,
            issuer_id=issuer.id,
            rationale="A specific, dated curatorial reason.",
            verification_status=VerificationStatus.VERIFIED,
        ),
    )

    result = research_universe_service.get_research_universe_issuers(db_session, universe.id)

    assert result is not None
    assert result.universe.slug == slug
    assert len(result.issuers) == 1
    assert result.issuers[0].rationale == "A specific, dated curatorial reason."


def test_get_research_universe_issuers_returns_none_for_unknown_universe(
    db_session: Session,
) -> None:
    result = research_universe_service.get_research_universe_issuers(db_session, uuid4())
    assert result is None


def test_get_issuer_universe_memberships_lists_every_universe(db_session: Session) -> None:
    issuer = _seed_issuer(db_session, legal_name=f"Multi-Universe Test Co {uuid4()}")
    universe_a = _seed_universe(db_session, slug=f"universe-a-{uuid4()}")
    universe_b = _seed_universe(
        db_session, slug=f"universe-b-{uuid4()}", collection_type=CollectionType.BENCHMARK
    )
    for universe in (universe_a, universe_b):
        collection_repository.add_membership(
            db_session,
            CollectionMembershipCreate(
                collection_id=universe.id,
                issuer_id=issuer.id,
                rationale="Test membership.",
                verification_status=VerificationStatus.VERIFIED,
            ),
        )

    memberships = research_universe_service.get_issuer_universe_memberships(db_session, issuer.id)

    assert {m.slug for m in memberships} == {universe_a.slug, universe_b.slug}
    # Milestone 7.5.1 section 4: verification_status must be surfaced, not
    # dropped — the frontend relies on it to distinguish a verified
    # membership from a system-suggested (partial) one.
    assert all(m.verification_status is VerificationStatus.VERIFIED for m in memberships)


def test_get_issuer_universe_memberships_surfaces_partial_status(db_session: Session) -> None:
    """A system-suggested (`partial`) membership must be returned as such,
    never silently reported as `verified` — the whole point of the
    distinction (Milestone 7.5.1 section 4)."""
    issuer = _seed_issuer(db_session, legal_name=f"Partial Membership Test Co {uuid4()}")
    universe = _seed_universe(db_session, slug=f"universe-partial-{uuid4()}")
    collection_repository.add_membership(
        db_session,
        CollectionMembershipCreate(
            collection_id=universe.id,
            issuer_id=issuer.id,
            rationale="System-suggested test membership.",
            verification_status=VerificationStatus.PARTIAL,
        ),
    )

    memberships = research_universe_service.get_issuer_universe_memberships(db_session, issuer.id)

    assert len(memberships) == 1
    assert memberships[0].verification_status is VerificationStatus.PARTIAL


def test_get_issuer_universe_memberships_empty_for_unaffiliated_issuer(
    db_session: Session,
) -> None:
    issuer = _seed_issuer(db_session, legal_name=f"Unaffiliated Test Co {uuid4()}")

    memberships = research_universe_service.get_issuer_universe_memberships(db_session, issuer.id)

    assert memberships == []
