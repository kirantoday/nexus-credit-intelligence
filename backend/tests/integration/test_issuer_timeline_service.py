"""Integration tests for `app/services/issuer_timeline_service.py` (PLAN.md
Milestone 7.5.4) against the live shared `nexus` schema.

Covers: multi-SEC-event issuer, SEC+CourtListener issuer, chronological
ordering, event-date-vs-processing-date behavior, same-day/same-category
collapsing across providers, an issuer with no qualifying events, source/
provenance rendering, severity rendering, and Research Universe state
display.
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
    ProviderName,
    TransformationType,
    VerificationStatus,
)
from app.domain.alert import AlertEvent, AlertEventCreate
from app.domain.collection import CollectionCreate, CollectionMembershipCreate
from app.domain.issuer import Issuer, IssuerCreate
from app.domain.provenance import ProvenanceCreate
from app.models.alert import AlertEvent as AlertEventModel
from app.repositories import (
    alert_repository,
    collection_repository,
    issuer_repository,
    provenance_repository,
)
from app.services import issuer_timeline_service
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
    category: str = "chapter_11",
    severity: EvidenceSeverity = EvidenceSeverity.HIGH,
    provider: str = "sec_edgar",
    as_of: date,
    headline: str = "Test headline.",
    explanation: str = "Test explanation.",
    confidence: float | None = 0.9,
    status: AlertStatus = AlertStatus.NEW,
    issuer_is_subject: bool | None = True,
    is_backfill: bool = False,
    source_label: str = "Test source label",
    source_url: str | None = "https://example.com/source",
    triggered_at: datetime | None = None,
) -> AlertEvent:
    calc_provenance = provenance_repository.create_provenance(
        db,
        ProvenanceCreate(
            provider=(
                ProviderName(provider) if provider in ("sec_edgar",) else ProviderName.SEC_EDGAR
            ),
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
            category=category,
            severity=severity,
            headline=headline,
            explanation=explanation,
            evidence_ids=[uuid4()],
            bundle_key=f"{provider}:test:{uuid4()}",
            primary_evidence_provider=provider,
            primary_source_label=source_label,
            primary_source_url=source_url,
            detection_method=DetectionMethod.DETERMINISTIC,
            ai_assisted=False,
            confidence=confidence,
            as_of_date=as_of,
            provenance_id=calc_provenance.id,
            status=status,
            is_backfill=is_backfill,
            issuer_is_subject=issuer_is_subject,
        ),
    )
    if triggered_at is not None:
        row = db.get(AlertEventModel, alert.id)
        assert row is not None
        row.triggered_at = triggered_at
        db.flush()
    return alert


def test_issuer_with_multiple_sec_events_produces_ordered_timeline(db_session: Session) -> None:
    issuer = _seed_issuer(db_session, legal_name="Timeline Test Multi-SEC Issuer")
    _seed_alert(
        db_session,
        issuer_id=issuer.id,
        category="covenant_breach",
        as_of=date(2026, 2, 1),
        headline="Early covenant breach.",
    )
    _seed_alert(
        db_session,
        issuer_id=issuer.id,
        category="going_concern",
        as_of=date(2026, 4, 1),
        headline="Going concern doubt.",
    )
    _seed_alert(
        db_session,
        issuer_id=issuer.id,
        category="chapter_11",
        as_of=date(2026, 6, 1),
        headline="Chapter 11 filed.",
    )

    timeline = issuer_timeline_service.get_issuer_timeline(db_session, issuer.id)

    assert timeline is not None
    assert timeline.total_events == 3
    assert [e.event_date for e in timeline.events] == [
        date(2026, 6, 1),
        date(2026, 4, 1),
        date(2026, 2, 1),
    ]
    assert timeline.date_range_start == date(2026, 2, 1)
    assert timeline.date_range_end == date(2026, 6, 1)
    assert timeline.most_recent_event_title == "Chapter 11"


def test_issuer_with_sec_and_courtlistener_events(db_session: Session) -> None:
    issuer = _seed_issuer(db_session, legal_name="Timeline Test SEC+CourtListener Issuer")
    _seed_alert(
        db_session,
        issuer_id=issuer.id,
        category="chapter_11",
        provider="sec_edgar",
        as_of=date(2026, 5, 1),
        headline="8-K discloses Chapter 11 filing plans.",
    )
    _seed_alert(
        db_session,
        issuer_id=issuer.id,
        category="plan_confirmed",
        provider="courtlistener",
        as_of=date(2026, 7, 1),
        headline="Docket entry confirms plan of reorganization.",
    )

    timeline = issuer_timeline_service.get_issuer_timeline(db_session, issuer.id)

    assert timeline is not None
    assert timeline.total_events == 2
    providers = {e.primary_source.provider for e in timeline.events}
    assert providers == {"sec_edgar", "courtlistener"}


def test_timeline_positions_events_by_source_date_not_processing_date(db_session: Session) -> None:
    """A filing filed May 15 but discovered/processed by Nexus in August must
    be positioned at May 15 — never the processing date (PLAN.md Milestone
    7.5.2's already-established date-semantics rule, reused here)."""
    issuer = _seed_issuer(db_session, legal_name="Timeline Test Source-Date Issuer")
    _seed_alert(
        db_session,
        issuer_id=issuer.id,
        as_of=date(2026, 5, 15),
        triggered_at=datetime(2026, 8, 10, 9, 0, tzinfo=UTC),
    )

    timeline = issuer_timeline_service.get_issuer_timeline(db_session, issuer.id)

    assert timeline is not None
    assert timeline.events[0].event_date == date(2026, 5, 15)


def test_same_day_same_category_alerts_from_two_providers_collapse_into_one_event(
    db_session: Session,
) -> None:
    """An SEC 8-K and a CourtListener docket entry about the same real-world
    Chapter 11 filing, same day, same category, must render as one timeline
    milestone with both sources — not two near-duplicate cards."""
    issuer = _seed_issuer(db_session, legal_name="Timeline Test Collapse Issuer")
    _seed_alert(
        db_session,
        issuer_id=issuer.id,
        category="chapter_11",
        provider="sec_edgar",
        as_of=date(2026, 6, 1),
        severity=EvidenceSeverity.HIGH,
        confidence=0.95,
        headline="8-K discloses Chapter 11 filing.",
        source_label="8-K filed 2026-06-01",
    )
    _seed_alert(
        db_session,
        issuer_id=issuer.id,
        category="chapter_11",
        provider="courtlistener",
        as_of=date(2026, 6, 1),
        severity=EvidenceSeverity.HIGH,
        confidence=0.85,
        headline="Docket confirms Chapter 11 petition.",
        source_label="Docket entry #1",
    )

    timeline = issuer_timeline_service.get_issuer_timeline(db_session, issuer.id)

    assert timeline is not None
    assert timeline.total_events == 1
    event = timeline.events[0]
    assert event.evidence_count == 2
    assert event.primary_source.provider == "sec_edgar"  # higher confidence wins
    assert len(event.supporting_sources) == 1
    assert event.supporting_sources[0].provider == "courtlistener"


def test_distinct_dates_never_collapse_even_when_close(db_session: Session) -> None:
    issuer = _seed_issuer(db_session, legal_name="Timeline Test No-False-Collapse Issuer")
    _seed_alert(db_session, issuer_id=issuer.id, category="chapter_11", as_of=date(2026, 6, 1))
    _seed_alert(db_session, issuer_id=issuer.id, category="chapter_11", as_of=date(2026, 6, 2))

    timeline = issuer_timeline_service.get_issuer_timeline(db_session, issuer.id)

    assert timeline is not None
    assert timeline.total_events == 2


def test_dismissed_and_third_party_alerts_are_excluded(db_session: Session) -> None:
    issuer = _seed_issuer(db_session, legal_name="Timeline Test Excluded-Alerts Issuer")
    _seed_alert(
        db_session, issuer_id=issuer.id, as_of=date(2026, 1, 1), status=AlertStatus.DISMISSED
    )
    _seed_alert(db_session, issuer_id=issuer.id, as_of=date(2026, 2, 1), issuer_is_subject=False)
    _seed_alert(db_session, issuer_id=issuer.id, as_of=date(2026, 3, 1), issuer_is_subject=None)

    timeline = issuer_timeline_service.get_issuer_timeline(db_session, issuer.id)

    assert timeline is not None
    assert timeline.total_events == 1
    assert timeline.events[0].event_date == date(2026, 3, 1)


def test_issuer_with_no_qualifying_events_has_an_empty_timeline(db_session: Session) -> None:
    issuer = _seed_issuer(db_session, legal_name="Timeline Test No-Events Issuer")

    timeline = issuer_timeline_service.get_issuer_timeline(db_session, issuer.id)

    assert timeline is not None
    assert timeline.events == []
    assert timeline.total_events == 0
    assert timeline.date_range_start is None
    assert timeline.date_range_end is None
    assert timeline.most_recent_event_title is None


def test_get_issuer_timeline_returns_none_for_a_nonexistent_issuer(db_session: Session) -> None:
    assert issuer_timeline_service.get_issuer_timeline(db_session, uuid4()) is None


def test_source_and_provenance_fields_render_on_the_primary_event(db_session: Session) -> None:
    issuer = _seed_issuer(db_session, legal_name="Timeline Test Source-Rendering Issuer")
    _seed_alert(
        db_session,
        issuer_id=issuer.id,
        as_of=date(2026, 3, 1),
        source_label="8-K filed 2026-03-01, Accession 0001234-26-000123",
        source_url="https://www.sec.gov/example",
        headline="Potential Chapter 11 filing detected.",
        explanation="Deterministic rule matching flagged this signal.",
        confidence=0.75,
    )

    timeline = issuer_timeline_service.get_issuer_timeline(db_session, issuer.id)

    assert timeline is not None
    event = timeline.events[0]
    assert event.short_summary == "Potential Chapter 11 filing detected."
    assert event.why_it_matters == "Deterministic rule matching flagged this signal."
    assert event.confidence == 0.75
    assert event.primary_source.label == "8-K filed 2026-03-01, Accession 0001234-26-000123"
    assert event.primary_source.url == "https://www.sec.gov/example"


def test_event_severity_reflects_the_most_severe_alert_in_its_collapsed_group(
    db_session: Session,
) -> None:
    issuer = _seed_issuer(db_session, legal_name="Timeline Test Severity Issuer")
    _seed_alert(
        db_session,
        issuer_id=issuer.id,
        category="covenant_breach",
        as_of=date(2026, 4, 1),
        provider="sec_edgar",
        severity=EvidenceSeverity.MEDIUM,
        confidence=0.5,
    )
    _seed_alert(
        db_session,
        issuer_id=issuer.id,
        category="covenant_breach",
        as_of=date(2026, 4, 1),
        provider="courtlistener",
        severity=EvidenceSeverity.HIGH,
        confidence=0.5,
    )

    timeline = issuer_timeline_service.get_issuer_timeline(db_session, issuer.id)

    assert timeline is not None
    assert timeline.events[0].severity == EvidenceSeverity.HIGH


def test_current_status_reflects_verified_research_universe_membership(db_session: Session) -> None:
    issuer = _seed_issuer(db_session, legal_name="Timeline Test Universe-Status Issuer")
    _seed_alert(db_session, issuer_id=issuer.id, category="chapter_11", as_of=date(2026, 6, 1))
    collection = collection_repository.create_collection(
        db_session,
        CollectionCreate(
            slug=f"timeline-test-chapter-11-{uuid4()}",
            name="Chapter 11 / Bankruptcy",
            description="Seeded for issuer_timeline_service tests.",
            collection_type=CollectionType.RESEARCH_UNIVERSE,
            scope=CollectionScope.ORGANIZATION,
            visibility=CollectionVisibility.PUBLIC,
            curation_method=CurationMethod.MANUAL_CURATED,
            verification_status=VerificationStatus.VERIFIED,
        ),
    )
    collection_repository.add_membership(
        db_session,
        CollectionMembershipCreate(
            collection_id=collection.id,
            issuer_id=issuer.id,
            rationale="Seeded for issuer_timeline_service tests.",
            verification_status=VerificationStatus.VERIFIED,
        ),
    )

    timeline = issuer_timeline_service.get_issuer_timeline(db_session, issuer.id)

    assert timeline is not None
    assert timeline.current_status == ["Chapter 11 / Bankruptcy"]
