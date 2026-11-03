"""Unit tests for `app.retrieval.eligibility` (Milestone 10D.2): the
server-controlled allowlist decision. Covers approval, revocation,
archived, restricted/reclassified, superseded, checksum drift, and the
fail-closed ordering. The SQL predicate that must match this logic is
10D.3's, tested there for parity."""

from __future__ import annotations

import dataclasses

from app.retrieval.eligibility import (
    PUBLIC_ALLOWLIST_SCOPE,
    EligibilityFacts,
    EligibilityReason,
    evaluate_eligibility,
)

_SHA = "a" * 64

OK = EligibilityFacts(
    document_found=True,
    is_archived=False,
    confidentiality_classification="standard",
    payload_checksum=_SHA,
    active_approval_checksum=_SHA,
    extraction_found=True,
    extraction_belongs_to_document=True,
    extraction_is_current=True,
    extraction_status="completed",
)


def _reason(**changes: object) -> EligibilityReason:
    return evaluate_eligibility(dataclasses.replace(OK, **changes)).reason  # type: ignore[arg-type]


def test_fully_approved_current_completed_standard_document_is_eligible() -> None:
    decision = evaluate_eligibility(OK)
    assert decision.eligible
    assert decision.reason is EligibilityReason.ELIGIBLE


def test_standard_classification_alone_is_never_sufficient() -> None:
    # A client-supplied 'standard' label with no approval must be denied.
    assert _reason(active_approval_checksum=None) is EligibilityReason.NOT_APPROVED


def test_revoked_approval_is_not_approved() -> None:
    # A revoked approval is represented by the repository as "no active
    # approval checksum".
    decision = evaluate_eligibility(dataclasses.replace(OK, active_approval_checksum=None))
    assert not decision.eligible


def test_document_missing_is_denied() -> None:
    assert _reason(document_found=False) is EligibilityReason.DOCUMENT_NOT_FOUND


def test_archived_document_is_denied() -> None:
    assert _reason(is_archived=True) is EligibilityReason.ARCHIVED


def test_document_reclassified_to_restricted_after_approval_is_denied() -> None:
    assert (
        _reason(confidentiality_classification="restricted")
        is EligibilityReason.NOT_STANDARD_CLASSIFICATION
    )


def test_unknown_or_missing_classification_is_denied() -> None:
    assert _reason(confidentiality_classification=None) is (
        EligibilityReason.NOT_STANDARD_CLASSIFICATION
    )
    assert _reason(confidentiality_classification="public") is (
        EligibilityReason.NOT_STANDARD_CLASSIFICATION
    )


def test_file_that_no_longer_matches_the_approved_checksum_is_denied() -> None:
    assert _reason(payload_checksum="b" * 64) is EligibilityReason.CHECKSUM_MISMATCH
    assert _reason(payload_checksum=None) is EligibilityReason.CHECKSUM_MISMATCH


def test_missing_extraction_is_denied() -> None:
    assert _reason(extraction_found=False) is EligibilityReason.EXTRACTION_NOT_FOUND


def test_extraction_of_another_document_is_denied() -> None:
    assert (
        _reason(extraction_belongs_to_document=False)
        is EligibilityReason.EXTRACTION_NOT_FOR_DOCUMENT
    )


def test_superseded_extraction_is_denied() -> None:
    assert _reason(extraction_is_current=False) is EligibilityReason.EXTRACTION_NOT_CURRENT


def test_non_completed_extraction_is_denied() -> None:
    for status in ("pending", "processing", "failed", "needs_ocr", None):
        assert _reason(extraction_status=status) is EligibilityReason.EXTRACTION_NOT_COMPLETED


def test_allowlist_is_checked_before_anything_else_and_fails_closed() -> None:
    worst = dataclasses.replace(
        OK,
        active_approval_checksum=None,
        is_archived=True,
        confidentiality_classification="restricted",
        extraction_is_current=False,
    )
    assert evaluate_eligibility(worst).reason is EligibilityReason.NOT_APPROVED


def test_public_allowlist_scope_takes_no_input_and_matches_the_function() -> None:
    assert PUBLIC_ALLOWLIST_SCOPE.name == "public_allowlist"
    assert PUBLIC_ALLOWLIST_SCOPE.evaluate(OK) == evaluate_eligibility(OK)
    denied = dataclasses.replace(OK, is_archived=True)
    assert PUBLIC_ALLOWLIST_SCOPE.evaluate(denied) == evaluate_eligibility(denied)
