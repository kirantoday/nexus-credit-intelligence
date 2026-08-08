"""Integration tests for `app/services/universe_classification_service.py`
(PLAN.md Milestone 7.5 section 14) against the live nexus schema.
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.types import (
    AlertStatus,
    DetectionMethod,
    EvidenceSeverity,
    EvidenceType,
    ProviderName,
    VerificationStatus,
)
from app.domain.alert import AlertEventCreate
from app.domain.collection import CollectionMembershipCreate
from app.domain.issuer import IssuerCreate
from app.domain.research_evidence import ResearchEvidence, ResearchEvidenceCreate
from app.repositories import (
    alert_repository,
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


def _alert_covering(
    db: Session,
    evidence: ResearchEvidence,
    *,
    severity: EvidenceSeverity,
    issuer_is_subject: bool | None,
) -> None:
    """Creates the AI-reviewed alert `_effective_reviews` looks up by bundle
    key for a piece of evidence with no `filing_id`/`docket_entry_id` set
    (`_source_key` resolves to `"none"` — matches `_evidence`'s fixture
    shape), so tests can exercise the alert-severity/issuer-is-subject gate
    without going through the full alert-synthesis pipeline."""
    alert_repository.create_alert(
        db,
        AlertEventCreate(
            issuer_id=evidence.issuer_id,
            category=evidence.evidence_type.value,
            severity=severity,
            headline="Test alert headline.",
            explanation="Test alert explanation.",
            evidence_ids=[evidence.id],
            bundle_key=f"{evidence.evidence_provider}:{evidence.source_type}:none",
            primary_evidence_provider=evidence.evidence_provider,
            primary_source_label="Test source",
            detection_method=DetectionMethod.AI_ASSISTED,
            ai_assisted=True,
            confidence=0.8,
            as_of_date=date(2026, 7, 9),
            provenance_id=evidence.provenance_id,
            status=AlertStatus.NEW,
            issuer_is_subject=issuer_is_subject,
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
    # AI-confirmed the issuer itself is the subject — required for
    # `verified` since Milestone 7.5.1 (see
    # test_definitive_evidence_falls_back_to_partial_without_an_alert).
    _alert_covering(db_session, evidence, severity=EvidenceSeverity.HIGH, issuer_is_subject=True)

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
    _alert_covering(
        db_session, strong_evidence, severity=EvidenceSeverity.HIGH, issuer_is_subject=True
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


def test_definitive_evidence_demoted_to_partial_when_not_about_the_issuer(
    db_session: Session,
) -> None:
    """Regression test for Milestone 7.5.1's core finding: a bare Layer-1
    Chapter 11 phrase match scores HIGH regardless of whose bankruptcy it
    describes (live-verified in production: BlackSky Technology's "Chapter
    11" evidence was actually about a director's former employer, Hooper
    Holmes). The AI-reviewed alert already makes this distinction — a
    HIGH-severity alert whose `issuer_is_subject` is `False` must classify
    the issuer as `partial` (system-suggested), never `verified`, since the
    issuer itself did not file."""
    universe_classification_service.seed_evidence_driven_universes(db_session)
    db_session.commit()
    issuer_id = _seed_issuer(db_session, legal_name="Classification Subsidiary Test Co")
    evidence = _evidence(
        db_session,
        issuer_id,
        evidence_type=EvidenceType.CHAPTER_11,
        severity=EvidenceSeverity.HIGH,
        excerpt="...after Mr. Doe's tenure as CEO of Unrelated Corp, which filed a voluntary "
        "petition...",
    )
    _alert_covering(db_session, evidence, severity=EvidenceSeverity.HIGH, issuer_is_subject=False)

    universe_classification_service.classify_issuer(
        db_session, issuer_id, [evidence], as_of_date=date(2026, 7, 9)
    )

    chapter_11 = collection_repository.get_collection_by_slug(db_session, "system-chapter-11")
    assert chapter_11 is not None
    membership = collection_repository.get_membership(db_session, chapter_11.id, issuer_id)
    assert membership is not None
    assert membership.verification_status is VerificationStatus.PARTIAL

    distressed_core = collection_repository.get_collection_by_slug(
        db_session, "system-distressed-core"
    )
    assert distressed_core is not None
    core_membership = collection_repository.get_membership(
        db_session, distressed_core.id, issuer_id
    )
    assert core_membership is not None
    assert core_membership.verification_status is VerificationStatus.PARTIAL


def test_suggestive_evidence_excluded_when_ai_reviewed_alert_downgrades_severity(
    db_session: Session,
) -> None:
    """Regression test: `phrase_event_of_default` scores HIGH on bare
    boilerplate ("...consequences of an Event of Default as defined
    therein...") with no requirement that a default actually occurred —
    live-verified as a systemic false-positive source in production. When
    the AI review correctly downgrades the covering alert to `low` (e.g.
    "routine credit-agreement boilerplate, no default reported"), that
    evidence must not qualify the issuer for Default / Covenant Stress at
    all, regardless of its own raw Layer-1 severity."""
    universe_classification_service.seed_evidence_driven_universes(db_session)
    db_session.commit()
    issuer_id = _seed_issuer(db_session, legal_name="Classification Boilerplate Test Co")
    evidence = _evidence(
        db_session,
        issuer_id,
        evidence_type=EvidenceType.COVENANT_BREACH,
        severity=EvidenceSeverity.HIGH,
        excerpt="The Credit Agreement contains customary provisions regarding an Event of Default.",
    )
    _alert_covering(db_session, evidence, severity=EvidenceSeverity.LOW, issuer_is_subject=True)

    universe_classification_service.classify_issuer(db_session, issuer_id, [evidence])

    default_covenant_stress = collection_repository.get_collection_by_slug(
        db_session, "system-default-covenant-stress"
    )
    assert default_covenant_stress is not None
    assert (
        collection_repository.get_membership(db_session, default_covenant_stress.id, issuer_id)
        is None
    )

    distressed_core = collection_repository.get_collection_by_slug(
        db_session, "system-distressed-core"
    )
    assert distressed_core is not None
    assert collection_repository.get_membership(db_session, distressed_core.id, issuer_id) is None


def test_definitive_evidence_falls_back_to_partial_without_an_alert(
    db_session: Session,
) -> None:
    """No alert on file for the bundle (e.g. a caller invoking
    `classify_issuer` ahead of alert synthesis, or AI review genuinely
    unavailable) falls back to the item's own Layer-1 severity for the
    HIGH-severity gate, but — since there is no entity confirmation at all
    — must classify as `partial`, never `verified`. This is a deliberate
    Milestone 7.5.1 tightening, not a bug: a bare Layer-1 phrase match
    proved unreliable at telling the issuer's own bankruptcy apart from a
    director's former employer's, a customer's, or SEC boilerplate (see
    BUILD_LOG.md), so an objective, high-precision-required category like
    Chapter 11 must never auto-verify without positive AI confirmation that
    the issuer itself is the subject — suggestive evidence still surfaces
    the signal (`partial`), it just doesn't overclaim it as settled."""
    universe_classification_service.seed_evidence_driven_universes(db_session)
    db_session.commit()
    issuer_id = _seed_issuer(db_session, legal_name="Classification No Alert Test Co")
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
    assert membership.verification_status is VerificationStatus.PARTIAL


def test_apply_correction_downgrades_a_wrongly_verified_membership(db_session: Session) -> None:
    """Regression test for the reconciliation path (PLAN.md Milestone
    7.5.1 section 9): `classify_issuer`'s live path is upgrade-only by
    design, so it cannot fix a membership this exact bug already wrote as
    `verified` before the fix existed. `apply_correction` is the one and
    only path that may downgrade — used solely by
    `app.scripts.reclassify_system_universes`."""
    universe_classification_service.seed_evidence_driven_universes(db_session)
    db_session.commit()
    issuer_id = _seed_issuer(db_session, legal_name="Correction Downgrade Test Co")
    evidence = _evidence(
        db_session, issuer_id, evidence_type=EvidenceType.CHAPTER_11, severity=EvidenceSeverity.HIGH
    )
    chapter_11 = collection_repository.get_collection_by_slug(db_session, "system-chapter-11")
    assert chapter_11 is not None
    # Simulates the pre-fix bug directly (classify_issuer itself can no
    # longer produce this state without an entity-confirming alert, by
    # design) — a membership wrongly written `verified` with no entity
    # check, exactly what the historical Chapter 11 audit found live.
    collection_repository.add_membership(
        db_session,
        CollectionMembershipCreate(
            collection_id=chapter_11.id,
            issuer_id=issuer_id,
            rationale="Pre-fix simulated membership.",
            verification_status=VerificationStatus.VERIFIED,
        ),
    )
    before = collection_repository.get_membership(db_session, chapter_11.id, issuer_id)
    assert before is not None
    assert before.verification_status is VerificationStatus.VERIFIED

    # The corrected computation, now aware the evidence concerns a
    # subsidiary/third party, only supports `partial`.
    expected = {
        "system-chapter-11": (VerificationStatus.PARTIAL, evidence),
        "system-distressed-core": (VerificationStatus.PARTIAL, evidence),
    }
    changes = universe_classification_service.apply_correction(db_session, issuer_id, expected)

    after = collection_repository.get_membership(db_session, chapter_11.id, issuer_id)
    assert after is not None
    assert after.verification_status is VerificationStatus.PARTIAL
    assert any("downgraded" in c and "verified -> partial" in c for c in changes)


def test_apply_correction_removes_membership_that_no_longer_qualifies(
    db_session: Session,
) -> None:
    """Once alert-severity gating correctly excludes boilerplate evidence
    (e.g. MasterBrand's covenant_breach items, live-verified all `low`),
    an issuer with an existing system-suggested membership but no
    remaining qualifying evidence must have that membership removed
    entirely, not merely left at a stale status."""
    universe_classification_service.seed_evidence_driven_universes(db_session)
    db_session.commit()
    issuer_id = _seed_issuer(db_session, legal_name="Correction Removal Test Co")
    evidence = _evidence(
        db_session,
        issuer_id,
        evidence_type=EvidenceType.COVENANT_BREACH,
        severity=EvidenceSeverity.HIGH,
    )
    universe_classification_service.classify_issuer(db_session, issuer_id, [evidence])
    default_covenant_stress = collection_repository.get_collection_by_slug(
        db_session, "system-default-covenant-stress"
    )
    assert default_covenant_stress is not None
    before = collection_repository.get_membership(db_session, default_covenant_stress.id, issuer_id)
    assert before is not None

    changes = universe_classification_service.apply_correction(db_session, issuer_id, {})

    after = collection_repository.get_membership(db_session, default_covenant_stress.id, issuer_id)
    assert after is None
    assert any("removed" in c for c in changes)


def test_apply_correction_is_idempotent(db_session: Session) -> None:
    universe_classification_service.seed_evidence_driven_universes(db_session)
    db_session.commit()
    issuer_id = _seed_issuer(db_session, legal_name="Correction Idempotent Test Co")
    evidence = _evidence(
        db_session, issuer_id, evidence_type=EvidenceType.CHAPTER_11, severity=EvidenceSeverity.HIGH
    )
    _alert_covering(db_session, evidence, severity=EvidenceSeverity.HIGH, issuer_is_subject=True)
    universe_classification_service.classify_issuer(db_session, issuer_id, [evidence])
    expected = {
        "system-chapter-11": (VerificationStatus.VERIFIED, evidence),
        "system-distressed-core": (VerificationStatus.VERIFIED, evidence),
    }

    first = universe_classification_service.apply_correction(db_session, issuer_id, expected)
    second = universe_classification_service.apply_correction(db_session, issuer_id, expected)

    assert first == []  # already verified from classify_issuer; nothing to change
    assert second == []


def test_apply_correction_never_touches_a_non_system_seeded_membership(
    db_session: Session,
) -> None:
    """Defensive test: even if a non-`system_seeded` membership somehow
    exists at an evidence-driven slug (should be architecturally
    impossible per `seed_evidence_driven_universes`'s collision guard),
    `apply_correction` must never remove or modify it — analyst-curated
    memberships are never touched, no exceptions (PLAN.md Milestone 7.5.1
    section 9)."""
    universe_classification_service.seed_evidence_driven_universes(db_session)
    db_session.commit()
    issuer_id = _seed_issuer(db_session, legal_name="Correction Analyst Curated Test Co")
    chapter_11 = collection_repository.get_collection_by_slug(db_session, "system-chapter-11")
    assert chapter_11 is not None
    collection_repository.add_membership(
        db_session,
        CollectionMembershipCreate(
            collection_id=chapter_11.id,
            issuer_id=issuer_id,
            rationale="Analyst-added for this test.",
            verification_status=VerificationStatus.VERIFIED,
            system_seeded=False,
        ),
    )

    changes = universe_classification_service.apply_correction(db_session, issuer_id, {})

    membership = collection_repository.get_membership(db_session, chapter_11.id, issuer_id)
    assert membership is not None
    assert membership.verification_status is VerificationStatus.VERIFIED
    assert changes == []
