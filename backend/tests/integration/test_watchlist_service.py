"""Integration tests for `app/services/watchlist_service.py` (PLAN.md
section 24.1; Milestone 8) against the live shared `nexus` schema.

Covers: create/list/rename/delete Watchlist, add/duplicate-add/remove
issuer, nonexistent issuer/watchlist handling, deletion doesn't delete the
underlying issuer, issuer counts, latest-development calculation, the
research-cycle "new development" boundary (reusing
`morning_brief_service.resolve_research_cycle`/`is_new_development`
exactly as Morning Brief does), severity aggregation, and that Watchlist
membership never leaks into "current status" (Research Universe territory).
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.core.types import (
    AlertStatus,
    CollectionScope,
    CollectionType,
    CollectionVisibility,
    CurationMethod,
    DataClassification,
    DetectionMethod,
    EvidenceSeverity,
    FilingMonitorRunMode,
    FilingMonitorRunStatus,
    ProviderName,
    TransformationType,
    VerificationStatus,
)
from app.domain.alert import AlertEvent, AlertEventCreate
from app.domain.collection import Collection, CollectionCreate, CollectionMembershipCreate
from app.domain.issuer import Issuer, IssuerCreate
from app.domain.market_discovery import MarketDiscoveryRunCreate
from app.domain.provenance import ProvenanceCreate
from app.repositories import (
    alert_repository,
    collection_repository,
    issuer_repository,
    market_discovery_repository,
    provenance_repository,
)
from app.services import watchlist_service
from tests.integration.conftest import reported_public_provenance


def _seed_issuer(db: Session, *, legal_name: str) -> Issuer:
    provenance = provenance_repository.create_provenance(db, reported_public_provenance())
    return issuer_repository.create_issuer(
        db, IssuerCreate(legal_name=legal_name, provenance_id=provenance.id)
    )


def _seed_alert(
    db: Session,
    *,
    issuer_id: UUID,
    severity: EvidenceSeverity = EvidenceSeverity.HIGH,
    as_of: date,
    headline: str = "Test headline.",
    status: AlertStatus | None = None,
    issuer_is_subject: bool | None = True,
) -> AlertEvent:
    calc_provenance = provenance_repository.create_provenance(
        db,
        ProvenanceCreate(
            provider=ProviderName.SEC_EDGAR,
            source_record_id=f"test-bundle-{uuid4()}",
            as_of_date=as_of,
            retrieved_at=reported_public_provenance().retrieved_at,
            transformation=TransformationType.REPORTED,
            classification=DataClassification.PUBLIC,
        ),
    )
    alert = alert_repository.create_alert(
        db,
        AlertEventCreate(
            issuer_id=issuer_id,
            category="bankruptcy_or_receivership",
            severity=severity,
            headline=headline,
            explanation="Test alert seeded for watchlist_service tests.",
            evidence_ids=[uuid4()],
            bundle_key=f"sec_edgar:test:{uuid4()}",
            primary_evidence_provider="sec_edgar",
            primary_source_label="Test source label",
            primary_source_url=None,
            detection_method=DetectionMethod.DETERMINISTIC,
            ai_assisted=False,
            confidence=0.9,
            as_of_date=as_of,
            provenance_id=calc_provenance.id,
            status=status or AlertStatus.NEW,
            issuer_is_subject=issuer_is_subject,
        ),
    )
    return alert


def _seed_daily_run(db: Session, *, window_start: date) -> None:
    """Deterministically pins `morning_brief_service.resolve_research_cycle`
    within this test's rolled-back transaction — same helper pattern as
    `test_morning_brief_service.py`'s `_seed_daily_run`."""
    run = market_discovery_repository.create_run(
        db,
        MarketDiscoveryRunCreate(
            mode=FilingMonitorRunMode.DELTA,
            window_start_date=window_start,
            window_end_date=window_start,
        ),
    )
    market_discovery_repository.complete_run(
        db,
        run.id,
        status=FilingMonitorRunStatus.SUCCESS,
        resulting_watermark=datetime.now(UTC),
        queries_executed=1,
        filings_examined=0,
        candidate_filings=0,
        issuers_resolved_existing=0,
        issuers_resolved_new=0,
        issuers_ambiguous=0,
        issuers_rejected=0,
        evidence_created=0,
        alerts_created=0,
        errors_count=0,
        error_summary=None,
    )


def _seed_verified_universe_membership(db: Session, *, issuer_id: UUID, name: str) -> Collection:
    universe = collection_repository.create_collection(
        db,
        CollectionCreate(
            slug=f"test-universe-{uuid4()}",
            name=name,
            description="Seeded for watchlist_service tests.",
            collection_type=CollectionType.RESEARCH_UNIVERSE,
            scope=CollectionScope.ORGANIZATION,
            visibility=CollectionVisibility.PUBLIC,
            curation_method=CurationMethod.MANUAL_CURATED,
            verification_status=VerificationStatus.VERIFIED,
        ),
    )
    collection_repository.add_membership(
        db,
        CollectionMembershipCreate(
            collection_id=universe.id,
            issuer_id=issuer_id,
            rationale="Test membership.",
            verification_status=VerificationStatus.VERIFIED,
        ),
    )
    return universe


def test_create_watchlist_defaults_to_empty(db_session: Session) -> None:
    summary = watchlist_service.create_watchlist(
        db_session, name=f"CFO Demo {uuid4()}", description="Test watchlist."
    )

    assert summary.issuer_count == 0
    assert summary.issuers_with_new_developments == 0
    assert summary.high_severity_count == 0
    assert summary.last_activity_at is None


def test_create_watchlist_generates_unique_slug_on_name_collision(db_session: Session) -> None:
    name = f"Duplicate Name Co {uuid4()}"
    first = watchlist_service.create_watchlist(db_session, name=name, description="")
    second = watchlist_service.create_watchlist(db_session, name=name, description="")

    assert first.slug != second.slug


def test_list_watchlists_only_returns_watchlist_type(db_session: Session) -> None:
    watchlist = watchlist_service.create_watchlist(
        db_session, name=f"List Test {uuid4()}", description=""
    )
    # A Research Universe with the same collection_type table must never
    # leak into the Watchlists listing (ADR-016 discriminator).
    collection_repository.create_collection(
        db_session,
        CollectionCreate(
            slug=f"not-a-watchlist-{uuid4()}",
            name="Not A Watchlist",
            description="",
            collection_type=CollectionType.RESEARCH_UNIVERSE,
            scope=CollectionScope.ORGANIZATION,
            visibility=CollectionVisibility.PUBLIC,
            curation_method=CurationMethod.MANUAL_CURATED,
            verification_status=VerificationStatus.VERIFIED,
        ),
    )

    listed = watchlist_service.list_watchlists(db_session)

    ids = {w.id for w in listed}
    assert watchlist.id in ids
    assert all(w.slug != "not-a-watchlist" for w in listed)


def test_update_watchlist_renames(db_session: Session) -> None:
    watchlist = watchlist_service.create_watchlist(
        db_session, name=f"Original Name {uuid4()}", description="Original description."
    )

    updated = watchlist_service.update_watchlist(
        db_session, watchlist.id, name="Renamed Watchlist", description="New description."
    )

    assert updated is not None
    assert updated.name == "Renamed Watchlist"
    assert updated.description == "New description."


def test_update_watchlist_returns_none_for_unknown_id(db_session: Session) -> None:
    result = watchlist_service.update_watchlist(
        db_session, uuid4(), name="Doesn't matter", description=None
    )
    assert result is None


def test_delete_watchlist_does_not_delete_the_issuer(db_session: Session) -> None:
    watchlist = watchlist_service.create_watchlist(
        db_session, name=f"Delete Test {uuid4()}", description=""
    )
    issuer = _seed_issuer(db_session, legal_name=f"Delete Test Co {uuid4()}")
    watchlist_service.add_issuer(
        db_session, watchlist.id, issuer_id=issuer.id, rationale="Tracking."
    )

    deleted = watchlist_service.delete_watchlist(db_session, watchlist.id)

    assert deleted is True
    assert watchlist_service.get_watchlist_detail(db_session, watchlist.id) is None
    # The issuer itself must survive the Watchlist's deletion.
    assert issuer_repository.get_issuer(db_session, issuer.id) is not None


def test_delete_watchlist_returns_false_for_unknown_id(db_session: Session) -> None:
    assert watchlist_service.delete_watchlist(db_session, uuid4()) is False


def test_add_issuer_to_unknown_watchlist_returns_none(db_session: Session) -> None:
    issuer = _seed_issuer(db_session, legal_name=f"Orphan Co {uuid4()}")
    result = watchlist_service.add_issuer(db_session, uuid4(), issuer_id=issuer.id, rationale="x")
    assert result is None


def test_add_unknown_issuer_returns_none(db_session: Session) -> None:
    watchlist = watchlist_service.create_watchlist(
        db_session, name=f"Unknown Issuer Test {uuid4()}", description=""
    )
    result = watchlist_service.add_issuer(
        db_session, watchlist.id, issuer_id=uuid4(), rationale="x"
    )
    assert result is None


def test_duplicate_add_issuer_is_idempotent(db_session: Session) -> None:
    watchlist = watchlist_service.create_watchlist(
        db_session, name=f"Duplicate Add Test {uuid4()}", description=""
    )
    issuer = _seed_issuer(db_session, legal_name=f"Duplicate Add Co {uuid4()}")

    first = watchlist_service.add_issuer(
        db_session, watchlist.id, issuer_id=issuer.id, rationale="First add."
    )
    second = watchlist_service.add_issuer(
        db_session, watchlist.id, issuer_id=issuer.id, rationale="Second add attempt."
    )

    assert first is not None and first[1] is True
    assert second is not None and second[1] is False
    detail = watchlist_service.get_watchlist_detail(db_session, watchlist.id)
    assert detail is not None
    assert len(detail.issuers) == 1


def test_remove_issuer(db_session: Session) -> None:
    watchlist = watchlist_service.create_watchlist(
        db_session, name=f"Remove Test {uuid4()}", description=""
    )
    issuer = _seed_issuer(db_session, legal_name=f"Remove Test Co {uuid4()}")
    watchlist_service.add_issuer(db_session, watchlist.id, issuer_id=issuer.id, rationale="x")

    removed = watchlist_service.remove_issuer(db_session, watchlist.id, issuer.id)

    assert removed is True
    detail = watchlist_service.get_watchlist_detail(db_session, watchlist.id)
    assert detail is not None
    assert detail.issuers == []


def test_remove_issuer_not_on_watchlist_returns_false(db_session: Session) -> None:
    watchlist = watchlist_service.create_watchlist(
        db_session, name=f"Remove Missing Test {uuid4()}", description=""
    )
    assert watchlist_service.remove_issuer(db_session, watchlist.id, uuid4()) is False


def test_issuer_count_reflects_memberships(db_session: Session) -> None:
    watchlist = watchlist_service.create_watchlist(
        db_session, name=f"Count Test {uuid4()}", description=""
    )
    issuer_a = _seed_issuer(db_session, legal_name=f"Count Co A {uuid4()}")
    issuer_b = _seed_issuer(db_session, legal_name=f"Count Co B {uuid4()}")
    watchlist_service.add_issuer(db_session, watchlist.id, issuer_id=issuer_a.id, rationale="x")
    watchlist_service.add_issuer(db_session, watchlist.id, issuer_id=issuer_b.id, rationale="x")

    result = watchlist_service.get_watchlist(db_session, watchlist.id)

    assert result is not None
    assert result.issuer_count == 2


def test_latest_development_reflects_most_recent_qualifying_alert(db_session: Session) -> None:
    watchlist = watchlist_service.create_watchlist(
        db_session, name=f"Latest Dev Test {uuid4()}", description=""
    )
    issuer = _seed_issuer(db_session, legal_name=f"Latest Dev Co {uuid4()}")
    watchlist_service.add_issuer(db_session, watchlist.id, issuer_id=issuer.id, rationale="x")
    _seed_alert(db_session, issuer_id=issuer.id, as_of=date(2026, 1, 1), headline="Old news")
    _seed_alert(db_session, issuer_id=issuer.id, as_of=date(2026, 6, 1), headline="Recent news")

    detail = watchlist_service.get_watchlist_detail(db_session, watchlist.id)

    assert detail is not None
    row = detail.issuers[0]
    assert row.latest_development_headline == "Recent news"
    assert row.latest_development_date == date(2026, 6, 1)


def test_latest_development_excludes_dismissed_and_third_party_alerts(
    db_session: Session,
) -> None:
    watchlist = watchlist_service.create_watchlist(
        db_session, name=f"Excludes Test {uuid4()}", description=""
    )
    issuer = _seed_issuer(db_session, legal_name=f"Excludes Co {uuid4()}")
    watchlist_service.add_issuer(db_session, watchlist.id, issuer_id=issuer.id, rationale="x")
    _seed_alert(
        db_session,
        issuer_id=issuer.id,
        as_of=date(2026, 6, 1),
        headline="Dismissed news",
        status=AlertStatus.DISMISSED,
    )
    _seed_alert(
        db_session,
        issuer_id=issuer.id,
        as_of=date(2026, 5, 1),
        headline="Third-party news",
        issuer_is_subject=False,
    )

    detail = watchlist_service.get_watchlist_detail(db_session, watchlist.id)

    assert detail is not None
    assert detail.issuers[0].latest_development_headline is None
    assert detail.issuers[0].severity is None


def test_new_developments_count_uses_morning_brief_research_cycle(db_session: Session) -> None:
    """The exact same `resolve_research_cycle`/`is_new_development`
    boundary Morning Brief uses — reused, not reimplemented (PLAN.md
    Milestone 8 Phase 5)."""
    _seed_daily_run(db_session, window_start=date(2026, 6, 10))
    watchlist = watchlist_service.create_watchlist(
        db_session, name=f"New Dev Cycle Test {uuid4()}", description=""
    )
    issuer = _seed_issuer(db_session, legal_name=f"New Dev Cycle Co {uuid4()}")
    watchlist_service.add_issuer(db_session, watchlist.id, issuer_id=issuer.id, rationale="x")
    # Within (preceding_research_day, latest_research_day] = new.
    _seed_alert(db_session, issuer_id=issuer.id, as_of=date(2026, 6, 10), headline="New")
    # Well before the cycle boundary = historical, not counted as new.
    _seed_alert(db_session, issuer_id=issuer.id, as_of=date(2026, 1, 1), headline="Old")

    detail = watchlist_service.get_watchlist_detail(db_session, watchlist.id)

    assert detail is not None
    assert detail.issuers[0].new_developments_count == 1


def test_high_severity_count_only_counts_new_high_severity_developments(
    db_session: Session,
) -> None:
    _seed_daily_run(db_session, window_start=date(2026, 6, 10))
    watchlist = watchlist_service.create_watchlist(
        db_session, name=f"High Severity Test {uuid4()}", description=""
    )
    issuer = _seed_issuer(db_session, legal_name=f"High Severity Co {uuid4()}")
    watchlist_service.add_issuer(db_session, watchlist.id, issuer_id=issuer.id, rationale="x")
    _seed_alert(
        db_session,
        issuer_id=issuer.id,
        as_of=date(2026, 6, 10),
        severity=EvidenceSeverity.HIGH,
        headline="New high severity",
    )

    result = watchlist_service.get_watchlist(db_session, watchlist.id)

    assert result is not None
    assert result.high_severity_count == 1
    assert result.issuers_with_new_developments == 1


def test_current_status_reflects_research_universe_not_watchlist(db_session: Session) -> None:
    """A Watchlist membership must never itself appear as "current status"
    — only verified Research Universe membership does (Milestone 8's
    explicit regression-protection requirement)."""
    watchlist = watchlist_service.create_watchlist(
        db_session, name=f"Status Test {uuid4()}", description=""
    )
    issuer = _seed_issuer(db_session, legal_name=f"Status Co {uuid4()}")
    watchlist_service.add_issuer(db_session, watchlist.id, issuer_id=issuer.id, rationale="x")
    _seed_verified_universe_membership(
        db_session, issuer_id=issuer.id, name="Distressed Core Universe"
    )

    detail = watchlist_service.get_watchlist_detail(db_session, watchlist.id)

    assert detail is not None
    assert detail.issuers[0].current_status == ["Distressed Core Universe"]


def test_contains_issuer_flag_reflects_membership(db_session: Session) -> None:
    watchlist = watchlist_service.create_watchlist(
        db_session, name=f"Contains Test {uuid4()}", description=""
    )
    issuer_in = _seed_issuer(db_session, legal_name=f"Contains In Co {uuid4()}")
    issuer_out = _seed_issuer(db_session, legal_name=f"Contains Out Co {uuid4()}")
    watchlist_service.add_issuer(db_session, watchlist.id, issuer_id=issuer_in.id, rationale="x")

    listed_in = watchlist_service.list_watchlists(db_session, issuer_id=issuer_in.id)
    listed_out = watchlist_service.list_watchlists(db_session, issuer_id=issuer_out.id)

    match_in = next(w for w in listed_in if w.id == watchlist.id)
    match_out = next(w for w in listed_out if w.id == watchlist.id)
    assert match_in.contains_issuer is True
    assert match_out.contains_issuer is False


def test_securities_count_defaults_to_zero(db_session: Session) -> None:
    watchlist = watchlist_service.create_watchlist(
        db_session, name=f"Securities Test {uuid4()}", description=""
    )
    issuer = _seed_issuer(db_session, legal_name=f"Securities Co {uuid4()}")
    watchlist_service.add_issuer(db_session, watchlist.id, issuer_id=issuer.id, rationale="x")

    detail = watchlist_service.get_watchlist_detail(db_session, watchlist.id)

    assert detail is not None
    assert detail.issuers[0].securities_count == 0


def test_get_watchlist_detail_returns_none_for_a_research_universe_id(
    db_session: Session,
) -> None:
    """A Research Universe id must not be servable through the Watchlists
    API even though both share the `collection` table (ADR-016)."""
    universe = collection_repository.create_collection(
        db_session,
        CollectionCreate(
            slug=f"not-watchlist-{uuid4()}",
            name="Some Research Universe",
            description="",
            collection_type=CollectionType.RESEARCH_UNIVERSE,
            scope=CollectionScope.ORGANIZATION,
            visibility=CollectionVisibility.PUBLIC,
            curation_method=CurationMethod.MANUAL_CURATED,
            verification_status=VerificationStatus.VERIFIED,
        ),
    )

    assert watchlist_service.get_watchlist_detail(db_session, universe.id) is None
