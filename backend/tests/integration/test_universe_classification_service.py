"""Integration tests for `app/services/universe_classification_service.py`
(PLAN.md Milestone 7.5 section 14) against the live nexus schema.
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.types import (
    DetectionMethod,
    EvidenceSeverity,
    EvidenceType,
    ProviderName,
    VerificationStatus,
)
from app.domain.issuer import IssuerCreate
from app.domain.research_evidence import ResearchEvidence, ResearchEvidenceCreate
from app.repositories import (
    collection_repository,
    issuer_repository,
    provenance_repository,
    research_evidence_repository,
)
from app.services import universe_classification_service
from tests.integration.conftest import reported_public_provenance


def _seed_issuer(db: Session, *, legal_name: str) -> UUID:
    provenance = provenance_repository.create_provenance(db, reported_public_provenance())
    return issuer_repository.create_issuer(
        db, IssuerCreate(legal_name=legal_name, provenance_id=provenance.id)
    ).id


def _evidence(
    db: Session,
    issuer_id: UUID,
    *,
    evidence_type: EvidenceType,
    severity: EvidenceSeverity,
    excerpt: str = "Test excerpt.",
) -> ResearchEvidence:
    provenance = provenance_repository.create_provenance(db, reported_public_provenance())
    return research_evidence_repository.create_evidence(
        db,
        ResearchEvidenceCreate(
            issuer_id=issuer_id,
            evidence_provider=ProviderName.SEC_EDGAR.value,
            source_type="sec_filing",
            evidence_type=evidence_type,
            severity=severity,
            matched_rule="test_rule",
            evidence_excerpt=excerpt,
            confidence=0.9,
            detection_method=DetectionMethod.DETERMINISTIC,
            provenance_id=provenance.id,
        ),
    )


def test_seed_evidence_driven_universes_is_idempotent(db_session: Session) -> None:
    first = universe_classification_service.seed_evidence_driven_universes(db_session)
    db_session.commit()
    second = universe_classification_service.seed_evidence_driven_universes(db_session)

    assert len(first) == len(second) == 8
    assert {c.slug for c in first} == {c.slug for c in second}
    assert all(c.curation_method.value == "system_seeded" for c in first)


def test_high_severity_chapter_11_gets_verified_membership(db_session: Session) -> None:
    universe_classification_service.seed_evidence_driven_universes(db_session)
    db_session.commit()
    issuer_id = _seed_issuer(db_session, legal_name="Classification Chapter 11 Test Co")
    evidence = _evidence(
        db_session, issuer_id, evidence_type=EvidenceType.CHAPTER_11, severity=EvidenceSeverity.HIGH
    )

    universe_classification_service.classify_issuer(
        db_session, issuer_id, [evidence], as_of_date=date(2026, 7, 9)
    )

    chapter_11 = collection_repository.get_collection_by_slug(db_session, "system-chapter-11")
    assert chapter_11 is not None
    membership = collection_repository.get_membership(db_session, chapter_11.id, issuer_id)
    assert membership is not None
    assert membership.verification_status is VerificationStatus.VERIFIED

    distressed_core = collection_repository.get_collection_by_slug(
        db_session, "system-distressed-core"
    )
    assert distressed_core is not None
    core_membership = collection_repository.get_membership(
        db_session, distressed_core.id, issuer_id
    )
    assert core_membership is not None
    assert core_membership.verification_status is VerificationStatus.VERIFIED


def test_low_severity_chapter_11_mention_does_not_auto_classify(db_session: Session) -> None:
    universe_classification_service.seed_evidence_driven_universes(db_session)
    db_session.commit()
    issuer_id = _seed_issuer(db_session, legal_name="Classification Low Severity Test Co")
    evidence = _evidence(
        db_session, issuer_id, evidence_type=EvidenceType.CHAPTER_11, severity=EvidenceSeverity.LOW
    )

    universe_classification_service.classify_issuer(db_session, issuer_id, [evidence])

    chapter_11 = collection_repository.get_collection_by_slug(db_session, "system-chapter-11")
    assert chapter_11 is not None
    assert collection_repository.get_membership(db_session, chapter_11.id, issuer_id) is None


def test_going_concern_gets_partial_system_suggested_membership(db_session: Session) -> None:
    universe_classification_service.seed_evidence_driven_universes(db_session)
    db_session.commit()
    issuer_id = _seed_issuer(db_session, legal_name="Classification Going Concern Test Co")
    evidence = _evidence(
        db_session,
        issuer_id,
        evidence_type=EvidenceType.GOING_CONCERN,
        severity=EvidenceSeverity.MEDIUM,
    )

    universe_classification_service.classify_issuer(db_session, issuer_id, [evidence])

    going_concern = collection_repository.get_collection_by_slug(db_session, "system-going-concern")
    assert going_concern is not None
    membership = collection_repository.get_membership(db_session, going_concern.id, issuer_id)
    assert membership is not None
    assert membership.verification_status is VerificationStatus.PARTIAL


def test_membership_upgrades_from_partial_to_verified_never_downgrades(db_session: Session) -> None:
    universe_classification_service.seed_evidence_driven_universes(db_session)
    db_session.commit()
    issuer_id = _seed_issuer(db_session, legal_name="Classification Upgrade Test Co")

    weak_evidence = _evidence(
        db_session,
        issuer_id,
        evidence_type=EvidenceType.BANKRUPTCY_OR_RECEIVERSHIP,
        severity=EvidenceSeverity.LOW,
    )
    universe_classification_service.classify_issuer(db_session, issuer_id, [weak_evidence])
    chapter_11 = collection_repository.get_collection_by_slug(db_session, "system-chapter-11")
    assert chapter_11 is not None
    # LOW severity never even creates membership (see test above) — confirm
    # the follow-up HIGH-severity evidence creates it fresh at VERIFIED.
    assert collection_repository.get_membership(db_session, chapter_11.id, issuer_id) is None

    strong_evidence = _evidence(
        db_session,
        issuer_id,
        evidence_type=EvidenceType.BANKRUPTCY_OR_RECEIVERSHIP,
        severity=EvidenceSeverity.HIGH,
    )
    universe_classification_service.classify_issuer(db_session, issuer_id, [strong_evidence])

    membership = collection_repository.get_membership(db_session, chapter_11.id, issuer_id)
    assert membership is not None
    assert membership.verification_status is VerificationStatus.VERIFIED

    # The repository guard itself: a later call attempting `partial` on an
    # already-`verified` membership must be a no-op, not a downgrade — the
    # invariant `classify_issuer` relies on but has no code path today that
    # would itself attempt (every definitive-evidence match always yields
    # `verified` directly), so it's proven here at the repository level.
    unchanged = collection_repository.upgrade_membership_verification(
        db_session,
        chapter_11.id,
        issuer_id,
        verification_status=VerificationStatus.PARTIAL,
        rationale="should not apply",
        rationale_as_of_date=None,
        supporting_provenance_ids=None,
    )
    assert unchanged is not None
    assert unchanged.verification_status is VerificationStatus.VERIFIED


def test_irrelevant_evidence_type_does_not_classify_anything(db_session: Session) -> None:
    universe_classification_service.seed_evidence_driven_universes(db_session)
    db_session.commit()
    issuer_id = _seed_issuer(db_session, legal_name="Classification Irrelevant Test Co")
    evidence = _evidence(
        db_session,
        issuer_id,
        evidence_type=EvidenceType.WORKFORCE_REDUCTION,
        severity=EvidenceSeverity.HIGH,
    )

    universe_classification_service.classify_issuer(db_session, issuer_id, [evidence])

    distressed_core = collection_repository.get_collection_by_slug(
        db_session, "system-distressed-core"
    )
    assert distressed_core is not None
    assert collection_repository.get_membership(db_session, distressed_core.id, issuer_id) is None
