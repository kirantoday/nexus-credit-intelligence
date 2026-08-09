"""Integration tests for `app/services/morning_brief_service.py` (PLAN.md
Milestone 7.5.2 correction) against the live shared `nexus` schema.

Covers the required scenario set: previous-day return, Friday-to-Monday
(and multi-day skips generally — the mechanism is calendar-agnostic, see
`tests/unit/test_morning_brief_boundary.py` for the actual weekday-fallback
math), first-ever brief, an old filing discovered today vs. a genuinely new
event today, a Research Universe membership change, no material changes,
and idempotent refresh/reopen behavior.
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
    ProviderName,
    TransformationType,
    VerificationStatus,
)
from app.domain.alert import AlertEvent, AlertEventCreate
from app.domain.collection import Collection, CollectionCreate, CollectionMembershipCreate
from app.domain.issuer import Issuer, IssuerCreate
from app.domain.provenance import ProvenanceCreate
from app.models.alert import AlertEvent as AlertEventModel
from app.models.brief_view import BriefView as BriefViewModel
from app.models.collection import CollectionMembership as CollectionMembershipModel
from app.repositories import (
    alert_repository,
    collection_repository,
    issuer_repository,
    provenance_repository,
)
from app.services import morning_brief_service
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


def _seed_view(db: Session, viewed_at: datetime) -> None:
    db.add(BriefViewModel(viewed_at=viewed_at))
    db.flush()


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


def _force_latest_view(monkeypatch: pytest.MonkeyPatch, viewed_at: datetime) -> None:
    """Forces `_resolve_period_start`'s view lookup to a fixed value,
    independent of whatever else may already exist in the shared
    `morning_brief_view` table — the boundary-resolution scenarios below
    care about the gap between this value and "now," not about winning a
    real "most recent row" race against ambient/production data."""
    from app.domain.brief_view import BriefView

    forced = BriefView(id=uuid4(), viewed_at=viewed_at, created_at=viewed_at)
    monkeypatch.setattr(
        morning_brief_service.brief_view_repository, "get_latest_view", lambda db: forced
    )


def test_previous_day_return_shows_developments_since_the_last_view(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    issuer = _seed_issuer(db_session, legal_name=f"Previous Day Test Co {uuid4()}")
    now = datetime.now(UTC)
    _force_latest_view(monkeypatch, now - timedelta(days=1))
    _seed_alert(db_session, issuer_id=issuer.id, triggered_at=now - timedelta(minutes=1))

    brief = morning_brief_service.get_morning_brief(db_session)

    assert brief.period_start_is_fallback is False
    matching = [d for d in brief.new_developments if d.issuer_id == issuer.id]
    assert len(matching) == 1


def test_friday_to_monday_gap_includes_developments_since_friday(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A multi-day gap (weekend included) works purely on elapsed time — no
    day-of-week logic is needed once a real view exists; only the
    first-ever-brief fallback cares about weekdays (PLAN.md Milestone
    7.5.2 correction)."""
    issuer = _seed_issuer(db_session, legal_name=f"Friday Monday Test Co {uuid4()}")
    now = datetime.now(UTC)
    friday_view = now - timedelta(days=3)  # e.g. Friday morning -> Monday morning
    _force_latest_view(monkeypatch, friday_view)
    # Recent `triggered_at` (not spread across the multi-day gap) keeps this
    # alert safely within `list_alerts`'s DESC-ordered fetch window
    # regardless of how much real alert volume already exists in the
    # shared database from other, unrelated activity — the property under
    # test is the *gap size* `period_start` tolerates, not how recent the
    # triggering alert itself is.
    _seed_alert(db_session, issuer_id=issuer.id, triggered_at=now - timedelta(minutes=1))

    brief = morning_brief_service.get_morning_brief(db_session)

    assert brief.period_start == friday_view
    matching = [d for d in brief.new_developments if d.issuer_id == issuer.id]
    assert len(matching) == 1


def test_user_skips_several_days(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    issuer = _seed_issuer(db_session, legal_name=f"Skip Days Test Co {uuid4()}")
    now = datetime.now(UTC)
    _force_latest_view(monkeypatch, now - timedelta(days=6))
    _seed_alert(db_session, issuer_id=issuer.id, triggered_at=now - timedelta(minutes=1))

    brief = morning_brief_service.get_morning_brief(db_session)

    matching = [d for d in brief.new_developments if d.issuer_id == issuer.id]
    assert len(matching) == 1


def test_first_ever_brief_uses_previous_business_day_fallback(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No prior `morning_brief_view` row exists for this (real, shared)
    database in general, so the fallback path is exercised directly via
    monkeypatching `get_latest_view` to `None`, rather than assuming the
    live table starts empty."""
    monkeypatch.setattr(
        morning_brief_service.brief_view_repository, "get_latest_view", lambda db: None
    )

    brief = morning_brief_service.get_morning_brief(db_session)

    assert brief.period_start_is_fallback is True
    assert brief.period_start.weekday() < 5  # Mon-Fri


def test_old_filing_discovered_today_is_historical_intelligence(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An event from months ago, discovered (triggered) just now, must
    appear as historical intelligence — never as a genuinely new
    development — per `is_backfill` (PLAN.md Milestone 7.5.2 correction)."""
    issuer = _seed_issuer(db_session, legal_name=f"Old Filing Test Co {uuid4()}")
    now = datetime.now(UTC)
    _force_latest_view(monkeypatch, now - timedelta(days=1))
    _seed_alert(
        db_session,
        issuer_id=issuer.id,
        is_backfill=True,
        as_of=date(2026, 3, 1),
        triggered_at=now - timedelta(minutes=1),
    )

    brief = morning_brief_service.get_morning_brief(db_session)

    assert not any(d.issuer_id == issuer.id for d in brief.new_developments)
    matching_historical = [d for d in brief.historical_intelligence if d.issuer_id == issuer.id]
    assert len(matching_historical) == 1
    assert matching_historical[0].alerts[0].as_of_date == date(2026, 3, 1)


def test_new_event_today_is_a_new_development(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    issuer = _seed_issuer(db_session, legal_name=f"New Event Test Co {uuid4()}")
    now = datetime.now(UTC)
    _force_latest_view(monkeypatch, now - timedelta(days=1))
    _seed_alert(
        db_session,
        issuer_id=issuer.id,
        is_backfill=False,
        as_of=date(2026, 8, 8),
        triggered_at=now - timedelta(minutes=1),
    )

    brief = morning_brief_service.get_morning_brief(db_session)

    matching_new = [d for d in brief.new_developments if d.issuer_id == issuer.id]
    assert len(matching_new) == 1
    assert not any(d.issuer_id == issuer.id for d in brief.historical_intelligence)


def test_universe_membership_change_surfaces_on_the_issuer_card(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    issuer = _seed_issuer(db_session, legal_name=f"Membership Change Test Co {uuid4()}")
    now = datetime.now(UTC)
    view_time = now - timedelta(days=1)
    _force_latest_view(monkeypatch, view_time)
    _seed_alert(db_session, issuer_id=issuer.id, triggered_at=now - timedelta(minutes=1))

    universe = _seed_system_seeded_universe(db_session, slug=f"test-membership-change-{uuid4()}")
    membership, _created = collection_repository.add_membership(
        db_session,
        CollectionMembershipCreate(
            collection_id=universe.id,
            issuer_id=issuer.id,
            rationale="Test membership added this period.",
            verification_status=VerificationStatus.VERIFIED,
            system_seeded=True,
        ),
    )
    row = db_session.get(CollectionMembershipModel, membership.id)
    assert row is not None
    row.added_at = now - timedelta(hours=2)
    row.updated_at = now - timedelta(hours=2)
    db_session.flush()
    # "added" this period: added_at moves to after the view boundary.
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
    # A boundary one second ago: nothing in this test seeds any alert after
    # it, so `new_developments` must genuinely be empty regardless of
    # whatever else already exists in the shared database.
    _force_latest_view(monkeypatch, datetime.now(UTC) - timedelta(seconds=1))

    brief = morning_brief_service.get_morning_brief(db_session)

    assert brief.new_developments == []
    assert brief.no_material_changes is True


def test_idempotent_refresh_does_not_advance_the_boundary(db_session: Session) -> None:
    # Seeded at "just now" (not an arbitrary past offset) so this row is
    # unambiguously the most recent in the whole shared `morning_brief_view`
    # table for the remainder of this test, regardless of any other rows
    # already present from unrelated activity.
    now = datetime.now(UTC)
    _seed_view(db_session, now - timedelta(seconds=1))

    first = morning_brief_service.get_morning_brief(db_session)
    morning_brief_service.record_brief_view(db_session)
    second = morning_brief_service.get_morning_brief(db_session)

    # The just-recorded view is within MIN_VIEW_GAP of the seeded one, so
    # `record_brief_view` must have been a no-op — both reads see the same
    # `period_start`.
    assert first.period_start == second.period_start
