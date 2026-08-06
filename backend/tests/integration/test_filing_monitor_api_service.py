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


def test_get_morning_brief_counts_alerts_by_severity(db_session: Session) -> None:
    issuer = _seed_issuer(db_session, legal_name=f"Brief Test Co {uuid4()}")
    _seed_alert(db_session, issuer_id=issuer.id, severity=EvidenceSeverity.HIGH)
    _seed_alert(db_session, issuer_id=issuer.id, severity=EvidenceSeverity.HIGH, ai_assisted=True)

    brief = filing_monitor_api_service.get_morning_brief(db_session)

    assert brief.alerts_total >= 2
    assert brief.alerts_by_severity.high >= 2
    assert brief.ai_assisted_alert_count >= 1
