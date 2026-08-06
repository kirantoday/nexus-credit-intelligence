"""Unit tests for `app/domain/evidence_bundle.py` (PLAN.md 24.3, ADR-018).

No DB — constructs `ResearchEvidence` objects directly. Proves the grouping
function isn't hardcoded to "one filing = one bundle" even though that's
today's only real grouping key.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.core.types import DetectionMethod, EvidenceSeverity, EvidenceType, ReviewStatus
from app.domain.evidence_bundle import group_evidence_into_bundles
from app.domain.research_evidence import ResearchEvidence

_ISSUER_A = uuid4()
_ISSUER_B = uuid4()
_FILING_1 = uuid4()
_FILING_2 = uuid4()


def _evidence(
    *,
    issuer_id: object,
    filing_id: object,
    evidence_type: EvidenceType = EvidenceType.LIQUIDITY_WARNING,
    severity: EvidenceSeverity = EvidenceSeverity.MEDIUM,
    evidence_provider: str = "sec_edgar",
    source_type: str = "sec_filing",
) -> ResearchEvidence:
    return ResearchEvidence(
        id=uuid4(),
        issuer_id=issuer_id,  # type: ignore[arg-type]
        evidence_provider=evidence_provider,
        source_type=source_type,
        filing_id=filing_id,  # type: ignore[arg-type]
        evidence_type=evidence_type,
        severity=severity,
        source_section=None,
        source_item=None,
        matched_rule="phrase_liquidity_shortfall",
        evidence_excerpt="Some excerpt text.",
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


def test_two_evidence_items_from_same_filing_group_into_one_bundle() -> None:
    e1 = _evidence(issuer_id=_ISSUER_A, filing_id=_FILING_1)
    e2 = _evidence(
        issuer_id=_ISSUER_A, filing_id=_FILING_1, evidence_type=EvidenceType.COVENANT_BREACH
    )

    bundles = group_evidence_into_bundles([e1, e2])

    assert len(bundles) == 1
    assert len(bundles[0].evidence) == 2
    assert bundles[0].issuer_id == _ISSUER_A


def test_evidence_from_different_filings_produces_separate_bundles() -> None:
    e1 = _evidence(issuer_id=_ISSUER_A, filing_id=_FILING_1)
    e2 = _evidence(issuer_id=_ISSUER_A, filing_id=_FILING_2)

    bundles = group_evidence_into_bundles([e1, e2])

    assert len(bundles) == 2
    assert {b.bundle_key for b in bundles} == {
        f"sec_edgar:sec_filing:{_FILING_1}",
        f"sec_edgar:sec_filing:{_FILING_2}",
    }


def test_evidence_from_different_issuers_never_shares_a_bundle_even_with_same_filing_id() -> None:
    """Defensive: bundle_key includes issuer_id implicitly via the grouping
    key even though this shouldn't happen in practice (a filing belongs to
    one issuer) — proves the grouping doesn't silently cross issuer
    boundaries if it ever did."""
    e1 = _evidence(issuer_id=_ISSUER_A, filing_id=_FILING_1)
    e2 = _evidence(issuer_id=_ISSUER_B, filing_id=_FILING_1)

    bundles = group_evidence_into_bundles([e1, e2])

    assert len(bundles) == 2
    issuer_ids = {b.issuer_id for b in bundles}
    assert issuer_ids == {_ISSUER_A, _ISSUER_B}


def test_grouping_key_is_provider_agnostic_not_filing_specific() -> None:
    """Proves the grouping function isn't hardcoded to SEC filings — a
    hypothetical future evidence_provider/source_type combination groups
    correctly using the exact same code path, no filing_id required."""
    e1 = ResearchEvidence(
        id=uuid4(),
        issuer_id=_ISSUER_A,
        evidence_provider="courtlistener",
        source_type="court_docket_entry",
        filing_id=None,
        evidence_type=EvidenceType.CHAPTER_11,
        severity=EvidenceSeverity.HIGH,
        source_section=None,
        source_item=None,
        matched_rule="docket_bankruptcy_petition",
        evidence_excerpt="A future non-SEC evidence source.",
        evidence_start_offset=None,
        evidence_end_offset=None,
        confidence=0.9,
        detection_method=DetectionMethod.DETERMINISTIC,
        provenance_id=uuid4(),
        created_at=datetime.now(UTC),
        review_status=ReviewStatus.UNREVIEWED,
        reviewed_by=None,
        reviewed_at=None,
    )

    bundles = group_evidence_into_bundles([e1])

    assert len(bundles) == 1
    assert bundles[0].bundle_key == "courtlistener:court_docket_entry:none"


def test_primary_evidence_prefers_highest_severity() -> None:
    low = _evidence(issuer_id=_ISSUER_A, filing_id=_FILING_1, severity=EvidenceSeverity.LOW)
    high = _evidence(
        issuer_id=_ISSUER_A,
        filing_id=_FILING_1,
        evidence_type=EvidenceType.BANKRUPTCY_OR_RECEIVERSHIP,
        severity=EvidenceSeverity.HIGH,
    )

    bundle = group_evidence_into_bundles([low, high])[0]

    assert bundle.primary_evidence.severity is EvidenceSeverity.HIGH
    assert bundle.primary_evidence.evidence_type is EvidenceType.BANKRUPTCY_OR_RECEIVERSHIP


def test_empty_evidence_list_produces_no_bundles() -> None:
    assert group_evidence_into_bundles([]) == []
