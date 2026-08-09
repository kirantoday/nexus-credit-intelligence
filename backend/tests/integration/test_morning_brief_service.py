"""Integration tests for `app/services/morning_brief_service.py` (PLAN.md
Milestone 7.5.2's business-day-cycle correction) against the live shared
`nexus` schema.

Covers the required scenario set: Friday->Thursday, Monday->Friday
(weekend skip), a genuinely first-ever research cycle (no successful
daily run has ever completed), an old filing discovered within the
latest cycle vs. a genuinely new event within it, a Research Universe
membership change, no material changes, idempotent repeated calls (the
window never changes across multiple "page opens"), and that only a new,
later successful daily run advances the window.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session

from app.core.types import (
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
from app.domain.market_discovery import MarketDiscoveryRun, MarketDiscoveryRunCreate
from app.domain.provenance import ProvenanceCreate
from app.models.alert import AlertEvent as AlertEventModel
from app.models.collection import CollectionMembership as CollectionMembershipModel
from app.repositories import (
    alert_repository,
    collection_repository,
    issuer_repository,
    market_discovery_repository,
    provenance_repository,
)
from app.schemas.filing_monitor import DailyRunSummary
from app.services import morning_brief_service
from tests.integration.conftest import reported_public_provenance

# 2026-08-07 is a Friday; 2026-08-10 is the following Monday.
_FRIDAY = date(2026, 8, 7)
_THURSDAY = date(2026, 8, 6)
_MONDAY = date(2026, 8, 10)


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
    is_backfill: bool = False,
    as_of: date = date(2026, 8, 7),
    triggered_at: datetime,
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
            headline="Test headline for morning_brief_service tests.",
            explanation="Test alert seeded for morning_brief_service tests.",
            evidence_ids=[uuid4()],
            bundle_key=f"sec_edgar:sec_filing:{uuid4()}",
            primary_evidence_provider="sec_edgar",
            primary_source_label="Test source label",
            primary_source_url=None,
            detection_method=DetectionMethod.DETERMINISTIC,
            ai_assisted=False,
            confidence=0.9,
            as_of_date=as_of,
            provenance_id=calc_provenance.id,
            is_backfill=is_backfill,
        ),
    )
    row = db.get(AlertEventModel, alert.id)
    assert row is not None
    row.triggered_at = triggered_at
    db.flush()
    return alert


def _seed_daily_run(
    db: Session, *, window_start: date, window_end: date | None = None
) -> MarketDiscoveryRun:
    """A real, successful `market_discovery_run` (`mode=delta`) with an
    explicit `window_start_date` — this is what `research_day` is derived
    from. `complete_run` uses `datetime.now()` for `completed_at`, so this
    row is always the most recently *completed* daily run relative to any
    already-committed production data, regardless of how far in the past
    or future `window_start` itself is."""
    run = market_discovery_repository.create_run(
        db,
        MarketDiscoveryRunCreate(
            mode=FilingMonitorRunMode.DELTA,
            window_start_date=window_start,
            window_end_date=window_end or window_start,
        ),
    )
    return market_discovery_repository.complete_run(
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


def _seed_system_seeded_universe(db: Session, *, slug: str) -> Collection:
    return collection_repository.create_collection(
        db,
        CollectionCreate(
            slug=slug,
            name=slug.replace("-", " ").title(),
            description="Seeded for morning_brief_service tests.",
            collection_type=CollectionType.RESEARCH_UNIVERSE,
            scope=CollectionScope.ORGANIZATION,
            visibility=CollectionVisibility.PUBLIC,
            curation_method=CurationMethod.SYSTEM_SEEDED,
            verification_status=VerificationStatus.VERIFIED,
        ),
    )


def test_friday_research_day_compares_with_thursday(db_session: Session) -> None:
    _seed_daily_run(db_session, window_start=_FRIDAY)

    brief = morning_brief_service.get_morning_brief(db_session)

    assert brief.latest_research_day == _FRIDAY
    assert brief.preceding_research_day == _THURSDAY
    assert brief.research_cycle_is_fallback is False


def test_monday_research_day_compares_with_friday_skipping_weekend(db_session: Session) -> None:
    _seed_daily_run(db_session, window_start=_MONDAY)

    brief = morning_brief_service.get_morning_brief(db_session)

    assert brief.latest_research_day == _MONDAY
    assert brief.preceding_research_day == _FRIDAY


def test_first_ever_research_cycle_uses_most_recent_business_day_fallback(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No successful daily run has ever completed for this (real, shared)
    database in general, so the fallback path is exercised directly via
    monkeypatching the lookup to `None`, rather than assuming the live
    run tables start empty (they don't — real daily runs already exist
    from prior milestone work)."""
    monkeypatch.setattr(morning_brief_service, "_latest_successful_daily_run", lambda db: None)

    brief = morning_brief_service.get_morning_brief(db_session)

    assert brief.research_cycle_is_fallback is True
    assert brief.latest_research_day.weekday() < 5  # Mon-Fri
    assert brief.preceding_research_day.weekday() < 5
    assert brief.preceding_research_day < brief.latest_research_day


def test_old_filing_this_cycle_is_historical_intelligence(db_session: Session) -> None:
    """An event from months ago, discovered (triggered) during the latest
    research cycle, must appear as historical intelligence — never as a
    genuinely new development — per `is_backfill` (unchanged from the
    prior correction)."""
    issuer = _seed_issuer(db_session, legal_name=f"Old Filing Test Co {uuid4()}")
    _seed_daily_run(db_session, window_start=_FRIDAY)
    _seed_alert(
        db_session,
        issuer_id=issuer.id,
        is_backfill=True,
        as_of=date(2026, 3, 1),
        triggered_at=datetime.now(UTC) - timedelta(minutes=1),
    )

    brief = morning_brief_service.get_morning_brief(db_session)

    assert not any(d.issuer_id == issuer.id for d in brief.new_developments)
    matching_historical = [d for d in brief.historical_intelligence if d.issuer_id == issuer.id]
    assert len(matching_historical) == 1
    assert matching_historical[0].alerts[0].as_of_date == date(2026, 3, 1)


def test_new_event_this_cycle_is_a_new_development(db_session: Session) -> None:
    issuer = _seed_issuer(db_session, legal_name=f"New Event Test Co {uuid4()}")
    _seed_daily_run(db_session, window_start=_FRIDAY)
    _seed_alert(
        db_session,
        issuer_id=issuer.id,
        is_backfill=False,
        as_of=_FRIDAY,
        triggered_at=datetime.now(UTC) - timedelta(minutes=1),
    )

    brief = morning_brief_service.get_morning_brief(db_session)

    matching_new = [d for d in brief.new_developments if d.issuer_id == issuer.id]
    assert len(matching_new) == 1
    assert not any(d.issuer_id == issuer.id for d in brief.historical_intelligence)


def test_universe_membership_change_surfaces_on_the_issuer_card(db_session: Session) -> None:
    issuer = _seed_issuer(db_session, legal_name=f"Membership Change Test Co {uuid4()}")
    _seed_daily_run(db_session, window_start=_FRIDAY)
    now = datetime.now(UTC)
    _seed_alert(db_session, issuer_id=issuer.id, triggered_at=now - timedelta(minutes=1))

    universe = _seed_system_seeded_universe(db_session, slug=f"test-membership-change-{uuid4()}")
    membership, _created = collection_repository.add_membership(
        db_session,
        CollectionMembershipCreate(
            collection_id=universe.id,
            issuer_id=issuer.id,
            rationale="Test membership added this cycle.",
            verification_status=VerificationStatus.VERIFIED,
            system_seeded=True,
        ),
    )
    row = db_session.get(CollectionMembershipModel, membership.id)
    assert row is not None
    row.added_at = now - timedelta(minutes=30)
    db_session.flush()

    brief = morning_brief_service.get_morning_brief(db_session)

    matching = [d for d in brief.new_developments if d.issuer_id == issuer.id]
    assert len(matching) == 1
    assert any(
        change.universe_name == universe.name and change.change_type == "added"
        for change in matching[0].universe_changes
    )


def test_no_material_changes_when_nothing_new(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A research day whose cycle-start boundary is one second ago: nothing
    # in this test seeds any alert after it, so `new_developments` must
    # genuinely be empty regardless of whatever else already exists in the
    # shared database.
    almost_now = datetime.now(UTC) - timedelta(seconds=1)
    today_et = almost_now.astimezone(morning_brief_service._BRIEF_TIMEZONE).date()
    fake_run = DailyRunSummary(
        id=uuid4(),
        pipeline="market_discovery",
        mode=FilingMonitorRunMode.DELTA,
        status=FilingMonitorRunStatus.SUCCESS,
        started_at=almost_now,
        completed_at=almost_now,
        window_start_date=today_et,
        window_end_date=today_et,
        research_day=today_et,
        errors_count=0,
    )
    monkeypatch.setattr(morning_brief_service, "_latest_successful_daily_run", lambda db: fake_run)

    brief = morning_brief_service.get_morning_brief(db_session)

    assert brief.new_developments == []
    assert brief.no_material_changes is True


def test_idempotent_repeated_calls_return_identical_window(db_session: Session) -> None:
    """Proves the explicit requirement: opening, refreshing, or revisiting
    the brief must never alter the comparison window — calling
    `get_morning_brief` repeatedly against unchanged canonical run data
    must return byte-identical `latest_research_day`/
    `preceding_research_day` every time."""
    _seed_daily_run(db_session, window_start=_FRIDAY)

    first = morning_brief_service.get_morning_brief(db_session)
    second = morning_brief_service.get_morning_brief(db_session)
    third = morning_brief_service.get_morning_brief(db_session)

    assert first.latest_research_day == second.latest_research_day == third.latest_research_day
    assert (
        first.preceding_research_day
        == second.preceding_research_day
        == third.preceding_research_day
    )
    assert first.research_cycle_is_fallback == second.research_cycle_is_fallback


def test_only_a_new_later_run_advances_the_window(db_session: Session) -> None:
    """The window must never change on its own (no view/visit/refresh
    logic) — it only ever changes because a genuinely new, later
    successful daily run completed."""
    _seed_daily_run(db_session, window_start=_THURSDAY)
    before = morning_brief_service.get_morning_brief(db_session)
    assert before.latest_research_day == _THURSDAY

    # Repeated reads against the same data change nothing.
    still_before = morning_brief_service.get_morning_brief(db_session)
    assert still_before.latest_research_day == _THURSDAY

    # A new, later-completing daily run for Friday supersedes it.
    _seed_daily_run(db_session, window_start=_FRIDAY)
    after = morning_brief_service.get_morning_brief(db_session)
    assert after.latest_research_day == _FRIDAY
    assert after.preceding_research_day == _THURSDAY
