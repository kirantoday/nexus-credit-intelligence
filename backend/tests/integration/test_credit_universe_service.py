"""Integration tests for credit_universe_service against the live nexus schema."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.freshness import FreshnessTier
from app.core.types import (
    CollectionScope,
    CollectionType,
    CollectionVisibility,
    CurationMethod,
    DataClassification,
    InstrumentType,
    ProviderName,
    VerificationStatus,
)
from app.domain.collection import CollectionCreate, CollectionMembershipCreate
from app.domain.issuer import IssuerCreate
from app.domain.security import SecurityCreate
from app.repositories import (
    collection_repository,
    issuer_repository,
    provenance_repository,
    security_repository,
)
from app.services import credit_universe_service
from tests.integration.conftest import reported_public_provenance


def _seed_one_security(
    db: Session, *, legal_name: str, benchmark: str | None = None, spread: Decimal | None = None
) -> None:
    provenance = provenance_repository.create_provenance(db, reported_public_provenance())
    issuer = issuer_repository.create_issuer(
        db, IssuerCreate(legal_name=legal_name, provenance_id=provenance.id)
    )
    security_repository.create_security(
        db,
        SecurityCreate(
            issuer_id=issuer.id,
            instrument_type=InstrumentType.BOND,
            description=f"{legal_name} — Test Bond",
            maturity_date=date(2030, 1, 1),
            amount_outstanding=Decimal("500000000"),
            benchmark=benchmark,
            spread=spread,
            provenance_id=provenance.id,
        ),
    )


def test_get_credit_universe_page_returns_assembled_rows(db_session: Session) -> None:
    _seed_one_security(db_session, legal_name="Service Test Issuer Alpha")

    page = credit_universe_service.get_credit_universe_page(
        db_session, search="Service Test Issuer Alpha"
    )

    assert page.total == 1
    assert len(page.rows) == 1
    row = page.rows[0]
    assert row.issuer_legal_name == "Service Test Issuer Alpha"
    assert row.instrument_type is InstrumentType.BOND
    assert row.amount_outstanding == Decimal("500000000")
    assert row.freshness is FreshnessTier.LIVE, "just-created row should be freshly retrieved"
    assert row.provider is not None
    assert row.classification is not None


def test_get_credit_universe_page_pagination_metadata(db_session: Session) -> None:
    _seed_one_security(db_session, legal_name="Service Test Issuer Beta")

    page = credit_universe_service.get_credit_universe_page(
        db_session, search="Service Test Issuer Beta", page=1, page_size=10
    )

    assert page.page == 1
    assert page.page_size == 10


def test_get_credit_universe_page_empty_search_returns_empty_page(db_session: Session) -> None:
    page = credit_universe_service.get_credit_universe_page(
        db_session, search="NoSuchIssuerNameWillEverMatchThis"
    )

    assert page.total == 0
    assert page.rows == []


def test_get_credit_universe_page_defaults_to_real_only(db_session: Session) -> None:
    """PLAN.md Milestone 7.5 section 2/18: synthetic data must not appear
    mixed with real data in the normal Credit Universe view — the default
    call (no `is_synthetic` argument) must exclude a synthetic security,
    while an explicit `is_synthetic=None` (unfiltered) or `is_synthetic=True`
    still surface it for scenario/testing use."""
    provenance = provenance_repository.create_provenance(
        db_session, reported_public_provenance(classification=DataClassification.SYNTHETIC)
    )
    issuer = issuer_repository.create_issuer(
        db_session,
        IssuerCreate(
            legal_name="Synthetic Default Filter Test Co",
            provenance_id=provenance.id,
            is_synthetic=True,
            synthetic_reason="SYNTHETIC_DEMO_DATA",
        ),
    )
    security_repository.create_security(
        db_session,
        SecurityCreate(
            issuer_id=issuer.id,
            instrument_type=InstrumentType.LOAN,
            description="Synthetic Default Filter Test Co — Term Loan B",
            amount_outstanding=Decimal("100000000"),
            provenance_id=provenance.id,
            is_synthetic=True,
            synthetic_reason="SYNTHETIC_DEMO_DATA",
        ),
    )

    default_page = credit_universe_service.get_credit_universe_page(
        db_session, search="Synthetic Default Filter Test Co"
    )
    unfiltered_page = credit_universe_service.get_credit_universe_page(
        db_session, search="Synthetic Default Filter Test Co", is_synthetic=None
    )

    assert default_page.total == 0
    assert unfiltered_page.total == 1


def test_get_credit_universe_page_filters_by_universe(db_session: Session) -> None:
    """Milestone 6.5 (PLAN.md 24.9) — clicking a Research Universe opens
    Credit Universe pre-filtered to it."""
    provenance = provenance_repository.create_provenance(db_session, reported_public_provenance())
    in_universe_issuer = issuer_repository.create_issuer(
        db_session,
        IssuerCreate(legal_name="Universe Filter Test Issuer In", provenance_id=provenance.id),
    )
    _seed_one_security(db_session, legal_name="Universe Filter Test Issuer Out")

    collection = collection_repository.create_collection(
        db_session,
        CollectionCreate(
            slug="test-credit-universe-filter",
            name="Test Credit Universe Filter",
            description="Seeded for a credit_universe_service test.",
            collection_type=CollectionType.RESEARCH_UNIVERSE,
            scope=CollectionScope.ORGANIZATION,
            visibility=CollectionVisibility.PUBLIC,
            curation_method=CurationMethod.SYSTEM_SEEDED,
            verification_status=VerificationStatus.VERIFIED,
        ),
    )
    security_repository.create_security(
        db_session,
        SecurityCreate(
            issuer_id=in_universe_issuer.id,
            instrument_type=InstrumentType.BOND,
            description="Universe Filter Test Issuer In — Test Bond",
            maturity_date=date(2030, 1, 1),
            amount_outstanding=Decimal("500000000"),
            provenance_id=provenance.id,
        ),
    )
    collection_repository.add_membership(
        db_session,
        CollectionMembershipCreate(
            collection_id=collection.id,
            issuer_id=in_universe_issuer.id,
            rationale="Test membership.",
            verification_status=VerificationStatus.VERIFIED,
        ),
    )

    page = credit_universe_service.get_credit_universe_page(db_session, universe_id=collection.id)

    assert page.total == 1
    assert page.rows[0].issuer_legal_name == "Universe Filter Test Issuer In"


def test_get_credit_universe_page_universe_filter_aggregates_multiple_member_issuers(
    db_session: Session,
) -> None:
    """PLAN.md Milestone 7.5.3 CFO-demo fix: a universe with several member
    issuers must surface securities from *all* of them, not just one —
    the earlier single-issuer test alone wouldn't catch a query that only
    happened to work for a single membership row."""
    provenance = provenance_repository.create_provenance(db_session, reported_public_provenance())
    issuer_one = issuer_repository.create_issuer(
        db_session,
        IssuerCreate(legal_name="Universe Multi Test Issuer One", provenance_id=provenance.id),
    )
    issuer_two = issuer_repository.create_issuer(
        db_session,
        IssuerCreate(legal_name="Universe Multi Test Issuer Two", provenance_id=provenance.id),
    )
    for issuer in (issuer_one, issuer_two):
        security_repository.create_security(
            db_session,
            SecurityCreate(
                issuer_id=issuer.id,
                instrument_type=InstrumentType.BOND,
                description=f"{issuer.legal_name} — Test Bond",
                maturity_date=date(2030, 1, 1),
                amount_outstanding=Decimal("100000000"),
                provenance_id=provenance.id,
            ),
        )

    collection = collection_repository.create_collection(
        db_session,
        CollectionCreate(
            slug="test-credit-universe-filter-multi",
            name="Test Credit Universe Filter Multi",
            description="Seeded for a credit_universe_service test.",
            collection_type=CollectionType.RESEARCH_UNIVERSE,
            scope=CollectionScope.ORGANIZATION,
            visibility=CollectionVisibility.PUBLIC,
            curation_method=CurationMethod.SYSTEM_SEEDED,
            verification_status=VerificationStatus.VERIFIED,
        ),
    )
    for issuer in (issuer_one, issuer_two):
        collection_repository.add_membership(
            db_session,
            CollectionMembershipCreate(
                collection_id=collection.id,
                issuer_id=issuer.id,
                rationale="Test membership.",
                verification_status=VerificationStatus.VERIFIED,
            ),
        )

    page = credit_universe_service.get_credit_universe_page(db_session, universe_id=collection.id)

    assert page.total == 2
    returned_names = {row.issuer_legal_name for row in page.rows}
    assert returned_names == {"Universe Multi Test Issuer One", "Universe Multi Test Issuer Two"}


def test_get_credit_universe_page_universe_member_with_zero_securities_returns_empty_not_error(
    db_session: Session,
) -> None:
    """PLAN.md Milestone 7.5.3 CFO-demo fix: a real universe member with no
    securities loaded is a legitimate, common state (issuer-level
    membership vs. security-level Credit Universe data) — the query must
    return a clean empty page, never an error, so the frontend can render
    an honest explanation instead of a misleading generic empty state."""
    provenance = provenance_repository.create_provenance(db_session, reported_public_provenance())
    issuer_no_securities = issuer_repository.create_issuer(
        db_session,
        IssuerCreate(
            legal_name="Universe Zero Securities Test Issuer", provenance_id=provenance.id
        ),
    )
    collection = collection_repository.create_collection(
        db_session,
        CollectionCreate(
            slug="test-credit-universe-filter-zero-securities",
            name="Test Credit Universe Filter Zero Securities",
            description="Seeded for a credit_universe_service test.",
            collection_type=CollectionType.RESEARCH_UNIVERSE,
            scope=CollectionScope.ORGANIZATION,
            visibility=CollectionVisibility.PUBLIC,
            curation_method=CurationMethod.SYSTEM_SEEDED,
            verification_status=VerificationStatus.VERIFIED,
        ),
    )
    collection_repository.add_membership(
        db_session,
        CollectionMembershipCreate(
            collection_id=collection.id,
            issuer_id=issuer_no_securities.id,
            rationale="Test membership.",
            verification_status=VerificationStatus.VERIFIED,
        ),
    )

    page = credit_universe_service.get_credit_universe_page(db_session, universe_id=collection.id)

    assert page.total == 0
    assert page.rows == []


def test_sofr_benchmarked_row_gets_a_real_benchmark_rate(db_session: Session) -> None:
    """SOFR is a real, live-synced FRED series (Milestone 5's seed script,
    see BUILD_LOG.md) — a row referencing it as `benchmark` should be
    attached the actual latest SOFR observation, not a guess."""
    _seed_one_security(
        db_session,
        legal_name="Service Test Issuer Gamma",
        benchmark="SOFR",
        spread=Decimal("4.50"),
    )

    page = credit_universe_service.get_credit_universe_page(
        db_session, search="Service Test Issuer Gamma"
    )

    assert page.total == 1
    row = page.rows[0]
    assert row.benchmark == "SOFR"
    assert row.benchmark_rate is not None
    assert row.benchmark_rate > Decimal(0)
    assert row.benchmark_rate_provider is ProviderName.FRED
    assert row.benchmark_rate_as_of_date is not None
    # A plain reported fact, not blended with spread into a new number.
    assert row.benchmark_rate != row.spread


def test_row_with_unsynced_benchmark_gets_no_benchmark_rate(db_session: Session) -> None:
    _seed_one_security(
        db_session,
        legal_name="Service Test Issuer Delta",
        benchmark="LIBOR",  # not a series this platform syncs
        spread=Decimal("3.00"),
    )

    page = credit_universe_service.get_credit_universe_page(
        db_session, search="Service Test Issuer Delta"
    )

    assert page.total == 1
    row = page.rows[0]
    assert row.benchmark_rate is None
    assert row.benchmark_rate_as_of_date is None
    assert row.benchmark_rate_provider is None


def test_row_with_no_benchmark_gets_no_benchmark_rate(db_session: Session) -> None:
    _seed_one_security(db_session, legal_name="Service Test Issuer Epsilon")

    page = credit_universe_service.get_credit_universe_page(
        db_session, search="Service Test Issuer Epsilon"
    )

    assert page.total == 1
    assert page.rows[0].benchmark_rate is None
