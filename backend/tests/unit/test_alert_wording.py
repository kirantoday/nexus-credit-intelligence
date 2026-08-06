"""Unit tests for `app/services/alert_synthesis_service.py`'s deterministic
wording (PLAN.md 24.4's cautious-wording rule) — no DB, tests the pure
`_deterministic_summary` function directly against constructed evidence.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.core.types import DetectionMethod, EvidenceSeverity, EvidenceType, ReviewStatus
from app.domain.evidence_bundle import EvidenceBundle
from app.domain.research_evidence import ResearchEvidence
from app.services.alert_synthesis_service import _TOPIC_PHRASES, _deterministic_summary

_FORBIDDEN_PHRASES = (
    "is distressed",
    "is bankrupt",
    "will liquidate",
    "will file for bankruptcy",
    "is insolvent",
)


def _evidence(evidence_type: EvidenceType, severity: EvidenceSeverity) -> ResearchEvidence:
    return ResearchEvidence(
        id=uuid4(),
        issuer_id=uuid4(),
        evidence_provider="sec_edgar",
        source_type="sec_filing",
        filing_id=uuid4(),
        evidence_type=evidence_type,
        severity=severity,
        source_section=None,
        source_item=None,
        matched_rule="some_rule",
        evidence_excerpt="excerpt",
        evidence_start_offset=None,
        evidence_end_offset=None,
        confidence=0.7,
        detection_method=DetectionMethod.DETERMINISTIC,
        provenance_id=uuid4(),
        created_at=datetime.now(UTC),
        review_status=ReviewStatus.UNREVIEWED,
        reviewed_by=None,
        reviewed_at=None,
    )


def test_every_evidence_type_has_a_topic_phrase() -> None:
    """Every value the deterministic rule engine can produce must have cautious
    wording — no evidence type silently falls back to a raw snake_case value."""
    for evidence_type in EvidenceType:
        assert evidence_type in _TOPIC_PHRASES, f"missing topic phrase for {evidence_type}"


def test_headline_follows_the_cautious_potential_x_detected_template() -> None:
    bundle = EvidenceBundle(
        issuer_id=uuid4(),
        bundle_key="sec_edgar:sec_filing:x",
        evidence=(_evidence(EvidenceType.LIQUIDITY_WARNING, EvidenceSeverity.MEDIUM),),
    )

    headline, explanation = _deterministic_summary(bundle, source_phrase="a new 10-Q")

    assert headline == "Potential liquidity warning detected in a new 10-Q."
    assert "a new 10-Q" in explanation


def test_bankruptcy_headline_never_asserts_unsupported_claim() -> None:
    bundle = EvidenceBundle(
        issuer_id=uuid4(),
        bundle_key="sec_edgar:sec_filing:x",
        evidence=(_evidence(EvidenceType.BANKRUPTCY_OR_RECEIVERSHIP, EvidenceSeverity.HIGH),),
    )

    headline, explanation = _deterministic_summary(bundle, source_phrase="a new 8-K")

    for forbidden in _FORBIDDEN_PHRASES:
        assert forbidden not in headline.lower()
        assert forbidden not in explanation.lower()
    assert headline.startswith("Potential ")


def test_no_evidence_type_ever_produces_a_forbidden_phrase() -> None:
    for evidence_type in EvidenceType:
        bundle = EvidenceBundle(
            issuer_id=uuid4(),
            bundle_key="sec_edgar:sec_filing:x",
            evidence=(_evidence(evidence_type, EvidenceSeverity.HIGH),),
        )
        headline, explanation = _deterministic_summary(bundle, source_phrase="a new 8-K")
        for forbidden in _FORBIDDEN_PHRASES:
            assert forbidden not in headline.lower(), f"{evidence_type} headline: {headline!r}"
            assert (
                forbidden not in explanation.lower()
            ), f"{evidence_type} explanation: {explanation!r}"


def test_multi_evidence_bundle_explanation_mentions_signal_count() -> None:
    bundle = EvidenceBundle(
        issuer_id=uuid4(),
        bundle_key="sec_edgar:sec_filing:x",
        evidence=(
            _evidence(EvidenceType.BANKRUPTCY_OR_RECEIVERSHIP, EvidenceSeverity.HIGH),
            _evidence(EvidenceType.DEBT_ACCELERATION, EvidenceSeverity.HIGH),
        ),
    )

    _, explanation = _deterministic_summary(bundle, source_phrase="a new 8-K")

    assert "2 signals" in explanation
