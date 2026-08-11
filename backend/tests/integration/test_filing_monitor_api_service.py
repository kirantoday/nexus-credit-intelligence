"""Integration tests for filing_monitor_api_service against the live nexus schema."""

from __future__ import annotations

from datetime import date
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
from app.domain.collection import Collection, CollectionCreate, CollectionMembershipCreate
from app.domain.issuer import Issuer, IssuerCreate
from app.domain.provenance import ProvenanceCreate
from app.repositories import (
    alert_repository,
    collection_repository,
    issuer_repository,
    provenance_repository,
)
from app.services import filing_monitor_api_service
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
    status: AlertStatus = AlertStatus.NEW,
    ai_assisted: bool = False,
) -> AlertEvent:
    calc_provenance = provenance_repository.create_provenance(
        db,
        ProvenanceCreate(
            provider=ProviderName.SEC_EDGAR,
            source_record_id=f"test-bundle-{uuid4()}",
            as_of_date=date.today(),
            retrieved_at=reported_public_provenance().retrieved_at,
            transformation=TransformationType.REPORTED,
            classification=DataClassification.PUBLIC,
        ),
    )
    return alert_repository.create_alert(
        db,
        AlertEventCreate(
            issuer_id=issuer_id,
            category="bankruptcy_or_receivership",
            severity=severity,
            headline="Potential bankruptcy or receivership filing detected in a new 8-K.",
            explanation="Test alert seeded for filing_monitor_api_service tests.",
            evidence_ids=[uuid4()],
            bundle_key=f"sec_edgar:sec_filing:{uuid4()}",
            primary_evidence_provider="sec_edgar",
            primary_source_label="8-K filed 2026-08-01, Accession 0000000000-26-000001",
            primary_source_url="https://example.invalid/filing.htm",
            detection_method=(
                DetectionMethod.AI_ASSISTED if ai_assisted else DetectionMethod.DETERMINISTIC
            ),
            ai_assisted=ai_assisted,
            confidence=0.9,
            as_of_date=date.today(),
            provenance_id=calc_provenance.id,
            status=status,
        ),
    )


def _seed_universe_with_issuer(db: Session, issuer_id: UUID) -> Collection:
    universe = collection_repository.create_collection(
        db,
        CollectionCreate(
            slug=f"test-universe-{uuid4()}",
            name="Test Universe",
            description="Seeded for filing_monitor_api_service tests.",
            collection_type=CollectionType.RESEARCH_UNIVERSE,
            scope=CollectionScope.ORGANIZATION,
            visibility=CollectionVisibility.PUBLIC,
            curation_method=CurationMethod.SYSTEM_SEEDED,
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


def _seed_watchlist_with_issuers(
    db: Session, issuer_ids: list[UUID], *, name: str = "Test Watchlist"
) -> Collection:
    watchlist = collection_repository.create_collection(
        db,
        CollectionCreate(
            slug=f"test-watchlist-{uuid4()}",
            name=name,
            description="Seeded for filing_monitor_api_service tests.",
            collection_type=CollectionType.WATCHLIST,
            scope=CollectionScope.PERSONAL,
            visibility=CollectionVisibility.PUBLIC,
            curation_method=CurationMethod.USER_CREATED,
            verification_status=VerificationStatus.UNVERIFIED,
        ),
    )
    for issuer_id in issuer_ids:
        collection_repository.add_membership(
            db,
            CollectionMembershipCreate(
                collection_id=watchlist.id,
                issuer_id=issuer_id,
                rationale="Test membership.",
                verification_status=VerificationStatus.UNVERIFIED,
                system_seeded=False,
            ),
        )
    return watchlist


def test_list_alerts_filters_by_severity(db_session: Session) -> None:
    issuer = _seed_issuer(db_session, legal_name=f"Alert Severity Test Co {uuid4()}")
    _seed_alert(db_session, issuer_id=issuer.id, severity=EvidenceSeverity.HIGH)
    _seed_alert(db_session, issuer_id=issuer.id, severity=EvidenceSeverity.LOW)

    page = filing_monitor_api_service.list_alerts(
        db_session, issuer_id=issuer.id, severity=EvidenceSeverity.HIGH
    )

    assert page.total == 1
    assert page.alerts[0].severity == "high"


def test_list_alerts_filters_by_universe(db_session: Session) -> None:
    issuer_in = _seed_issuer(db_session, legal_name=f"In Universe Test Co {uuid4()}")
    issuer_out = _seed_issuer(db_session, legal_name=f"Out Of Universe Test Co {uuid4()}")
    universe = _seed_universe_with_issuer(db_session, issuer_in.id)
    _seed_alert(db_session, issuer_id=issuer_in.id)
    _seed_alert(db_session, issuer_id=issuer_out.id)

    page = filing_monitor_api_service.list_alerts(db_session, universe_id=universe.id)

    assert page.total == 1
    assert page.alerts[0].issuer_id == issuer_in.id
    assert universe.name in page.alerts[0].universe_names


def test_acknowledge_alert_updates_status(db_session: Session) -> None:
    issuer = _seed_issuer(db_session, legal_name=f"Ack Test Co {uuid4()}")
    alert = _seed_alert(db_session, issuer_id=issuer.id)

    updated = filing_monitor_api_service.acknowledge_alert(
        db_session, alert.id, acknowledged_by="test_suite"
    )

    assert updated.status == "acknowledged"
    assert updated.acknowledged_by == "test_suite"
    assert updated.acknowledged_at is not None


def test_dismiss_alert_records_reason(db_session: Session) -> None:
    issuer = _seed_issuer(db_session, legal_name=f"Dismiss Test Co {uuid4()}")
    alert = _seed_alert(db_session, issuer_id=issuer.id)

    updated = filing_monitor_api_service.dismiss_alert(
        db_session, alert.id, dismissed_by="test_suite", dismissal_reason="False positive."
    )

    assert updated.status == "dismissed"
    assert updated.dismissal_reason == "False positive."


def test_get_alert_evidence_detail_returns_none_for_unknown_alert(db_session: Session) -> None:
    result = filing_monitor_api_service.get_alert_evidence_detail(db_session, uuid4())
    assert result is None


def test_acknowledge_unknown_alert_raises(db_session: Session) -> None:
    try:
        filing_monitor_api_service.acknowledge_alert(db_session, uuid4(), acknowledged_by=None)
        raised = False
    except ValueError:
        raised = True
    assert raised


def test_dismiss_unknown_alert_raises(db_session: Session) -> None:
    try:
        filing_monitor_api_service.dismiss_alert(
            db_session, uuid4(), dismissed_by=None, dismissal_reason=None
        )
        raised = False
    except ValueError:
        raised = True
    assert raised


def test_dismissed_alert_is_retained_with_evidence_intact(db_session: Session) -> None:
    """Dismiss is analyst workflow state, never source-data destruction
    (Milestone 9, PLAN.md 24.11 Phase 6) — the alert row, its issuer, and
    its evidence must all still exist and be fetchable after dismissal."""
    issuer = _seed_issuer(db_session, legal_name=f"Dismiss Retain Test Co {uuid4()}")
    alert = _seed_alert(db_session, issuer_id=issuer.id)

    filing_monitor_api_service.dismiss_alert(
        db_session, alert.id, dismissed_by="test_suite", dismissal_reason="Not relevant."
    )

    still_there = alert_repository.get_alert(db_session, alert.id)
    assert still_there is not None
    assert still_there.status == AlertStatus.DISMISSED
    assert still_there.evidence_ids == alert.evidence_ids
    assert issuer_repository.get_issuer(db_session, issuer.id) is not None


def test_list_alerts_filters_by_watchlist(db_session: Session) -> None:
    issuer_in = _seed_issuer(db_session, legal_name=f"In Watchlist Test Co {uuid4()}")
    issuer_out = _seed_issuer(db_session, legal_name=f"Out Of Watchlist Test Co {uuid4()}")
    watchlist = _seed_watchlist_with_issuers(db_session, [issuer_in.id])
    _seed_alert(db_session, issuer_id=issuer_in.id)
    _seed_alert(db_session, issuer_id=issuer_out.id)

    page = filing_monitor_api_service.list_alerts(db_session, watchlist_id=watchlist.id)

    assert page.total == 1
    assert page.alerts[0].issuer_id == issuer_in.id
    assert watchlist.name in page.alerts[0].watchlist_names


def test_watchlist_names_never_appear_in_universe_names(db_session: Session) -> None:
    """Live-caught Milestone 9 regression: `universe_names` must never
    include a Watchlist's name, and `watchlist_names` must never include a
    Research Universe's name — the two are different product concepts
    (ADR-016) sharing one table."""
    issuer = _seed_issuer(db_session, legal_name=f"Split Names Test Co {uuid4()}")
    universe = _seed_universe_with_issuer(db_session, issuer.id)
    watchlist = _seed_watchlist_with_issuers(db_session, [issuer.id])
    _seed_alert(db_session, issuer_id=issuer.id)

    page = filing_monitor_api_service.list_alerts(db_session, issuer_id=issuer.id)

    assert page.total == 1
    row = page.alerts[0]
    assert universe.name in row.universe_names
    assert watchlist.name not in row.universe_names
    assert watchlist.name in row.watchlist_names
    assert universe.name not in row.watchlist_names


def test_list_alerts_watchlist_pagination_is_correct_across_multiple_issuers(
    db_session: Session,
) -> None:
    """Live-caught Milestone 9 regression: filtering by a multi-issuer
    collection (Watchlist or Research Universe) must report the correct
    `total` and never drop rows off a page — the original implementation
    fetched an already-paginated, unfiltered page and post-filtered it in
    Python, which silently under-reported `total` for any collection with
    more than one issuer."""
    issuers = [
        _seed_issuer(db_session, legal_name=f"Pagination Test Co {i} {uuid4()}") for i in range(3)
    ]
    watchlist = _seed_watchlist_with_issuers(db_session, [i.id for i in issuers])
    for issuer in issuers:
        _seed_alert(db_session, issuer_id=issuer.id)
    # An alert for an issuer NOT on the watchlist must never be counted.
    other_issuer = _seed_issuer(db_session, legal_name=f"Not On Watchlist Co {uuid4()}")
    _seed_alert(db_session, issuer_id=other_issuer.id)

    first_page = filing_monitor_api_service.list_alerts(
        db_session, watchlist_id=watchlist.id, page=1, page_size=2
    )
    second_page = filing_monitor_api_service.list_alerts(
        db_session, watchlist_id=watchlist.id, page=2, page_size=2
    )

    assert first_page.total == 3
    assert second_page.total == 3
    assert len(first_page.alerts) == 2
    assert len(second_page.alerts) == 1
    all_issuer_ids = {a.issuer_id for a in first_page.alerts} | {
        a.issuer_id for a in second_page.alerts
    }
    assert all_issuer_ids == {i.id for i in issuers}


def test_search_alert_issuers_matches_name(db_session: Session) -> None:
    unique = str(uuid4())[:8]
    issuer = _seed_issuer(db_session, legal_name=f"Searchable Alert Co {unique}")
    _seed_alert(db_session, issuer_id=issuer.id)

    result = filing_monitor_api_service.search_alert_issuers(db_session, unique)

    assert len(result.issuers) == 1
    assert result.issuers[0].issuer_id == issuer.id


def test_search_alert_issuers_excludes_issuers_without_alerts(db_session: Session) -> None:
    unique = str(uuid4())[:8]
    _seed_issuer(db_session, legal_name=f"No Alerts Co {unique}")

    result = filing_monitor_api_service.search_alert_issuers(db_session, unique)

    assert result.issuers == []


def test_get_alerts_summary_counts(db_session: Session) -> None:
    issuer_on_watchlist = _seed_issuer(db_session, legal_name=f"Summary Watchlist Co {uuid4()}")
    issuer_plain = _seed_issuer(db_session, legal_name=f"Summary Plain Co {uuid4()}")
    _seed_watchlist_with_issuers(db_session, [issuer_on_watchlist.id])
    _seed_alert(db_session, issuer_id=issuer_on_watchlist.id, severity=EvidenceSeverity.HIGH)
    _seed_alert(db_session, issuer_id=issuer_plain.id, severity=EvidenceSeverity.LOW)
    acknowledged = _seed_alert(db_session, issuer_id=issuer_plain.id)
    filing_monitor_api_service.acknowledge_alert(db_session, acknowledged.id, acknowledged_by=None)

    summary = filing_monitor_api_service.get_alerts_summary(db_session)

    # Scoped assertions (>=), not exact equality — this counts across the
    # whole shared `nexus` schema, not just this test's own rows.
    assert summary.new_count >= 2
    assert summary.high_severity_count >= 1
    assert summary.watchlist_alert_count >= 1
    assert summary.acknowledged_count >= 1


# Morning Brief assembly itself (`get_morning_brief`) moved to
# `app.services.morning_brief_service` in Milestone 7.5.2's correction — see
# `tests/integration/test_morning_brief_service.py` for its coverage,
# including the severity-breakdown-sums-to-total and provider-agnostic-
# evidence regression tests this file used to carry.
