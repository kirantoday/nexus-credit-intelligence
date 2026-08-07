"""Unit tests for `app/core/court_docket_matcher.py` (PLAN.md Milestone 7.5
section 10, ADR-020). Pure functions, no I/O — no live CourtListener calls.

Covers the specific correction the user required during planning: a debtor
filing far from its headquarters must not be rejected on jurisdiction
grounds, since jurisdiction is never a required signal.
"""

from __future__ import annotations

from datetime import date

from app.core.court_docket_matcher import (
    evaluate_candidate,
    normalize_company_name,
    select_best_match,
)
from app.core.types import CourtDocketLinkMatchOutcome
from app.providers.courtlistener.dto import CourtListenerSearchResultDTO


def _candidate(
    *,
    docket_id: int = 1,
    case_name: str = "Test Debtor Corp",
    docket_number: str = "23-90602",
    court: str | None = "United States Bankruptcy Court for the District of Delaware",
    date_filed: str | None = "2026-07-15",
    chapter: str | None = "11",
) -> CourtListenerSearchResultDTO:
    return CourtListenerSearchResultDTO(
        docket_id=docket_id,
        caseName=case_name,
        docketNumber=docket_number,
        court=court,
        dateFiled=date_filed,
        chapter=chapter,
    )


def test_normalize_company_name_strips_suffixes_and_punctuation() -> None:
    assert normalize_company_name("Diebold Nixdorf, Incorporated") == "diebold nixdorf"
    assert normalize_company_name("Diebold Nixdorf Holding Company, Inc.") == "diebold nixdorf"


def test_verified_match_never_requires_jurisdiction_correspondence() -> None:
    """The exact correction required during planning: a debtor headquartered
    somewhere with no connection to the filing court must still verify on
    name + case number + date alone. Court is deliberately something the
    triggering evidence text never mentions here."""
    candidate = _candidate(
        case_name="Example Distressed Co, Inc.", docket_number="26-12345", date_filed="2026-07-10"
    )
    evidence_text = (
        "On July 9, 2026, Example Distressed Co filed a voluntary petition "
        "under chapter 11, case number 26-12345."
    )

    signals = evaluate_candidate(
        candidate,
        issuer_legal_name="Example Distressed Co",
        evidence_text=evidence_text,
        evidence_as_of_date=date(2026, 7, 9),
    )

    assert signals.court_referenced_in_evidence is False
    assert signals.passes is True


def test_case_number_match_alone_is_sufficient() -> None:
    candidate = _candidate(docket_number="26-99999")
    signals = evaluate_candidate(
        candidate,
        issuer_legal_name="Totally Different Name LLC",
        evidence_text="Case number 26-99999 was filed in bankruptcy court.",
        evidence_as_of_date=None,
    )

    assert signals.case_number_match is True
    assert signals.name_match is False
    assert signals.passes is True


def test_name_match_alone_without_a_second_strong_signal_does_not_pass() -> None:
    candidate = _candidate(docket_number="26-00001", date_filed=None)
    signals = evaluate_candidate(
        candidate,
        issuer_legal_name="Test Debtor Corp",
        evidence_text="The company continues to operate.",
        evidence_as_of_date=None,
    )

    assert signals.name_match is True
    assert signals.case_number_match is False
    assert signals.date_correlated is False
    assert signals.passes is False


def test_non_bankruptcy_docket_never_passes_regardless_of_name_match() -> None:
    candidate = _candidate(chapter=None, docket_number="26-00002")
    signals = evaluate_candidate(
        candidate,
        issuer_legal_name="Test Debtor Corp",
        evidence_text="Case number 26-00002 referenced.",
        evidence_as_of_date=None,
    )

    assert signals.case_type_consistent is False
    assert signals.passes is False


def test_select_best_match_zero_candidates_is_checked_no_relevant_docket() -> None:
    outcome, best, evaluated = select_best_match(
        [], issuer_legal_name="Any Co", evidence_text="", evidence_as_of_date=None
    )

    assert outcome is CourtDocketLinkMatchOutcome.CHECKED_NO_RELEVANT_DOCKET
    assert best is None
    assert evaluated == []


def test_select_best_match_two_passing_candidates_is_ambiguous_never_a_guess() -> None:
    candidates = [
        _candidate(docket_id=1, case_name="Example Co A", docket_number="26-11111"),
        _candidate(docket_id=2, case_name="Example Co B", docket_number="26-22222"),
    ]
    evidence_text = "Case numbers 26-11111 and 26-22222 both referenced in this filing."

    outcome, best, evaluated = select_best_match(
        candidates,
        issuer_legal_name="Example Co",
        evidence_text=evidence_text,
        evidence_as_of_date=None,
    )

    assert outcome is CourtDocketLinkMatchOutcome.AMBIGUOUS_MANUAL_REVIEW
    assert best is None
    assert len(evaluated) == 2


def test_select_best_match_unique_passing_candidate_is_verified() -> None:
    candidates = [
        _candidate(docket_id=1, case_name="Real Match Co", docket_number="26-33333"),
        _candidate(docket_id=2, case_name="Unrelated Co", docket_number="26-44444", chapter=None),
    ]
    evidence_text = "Real Match Co filed case number 26-33333."

    outcome, best, evaluated = select_best_match(
        candidates,
        issuer_legal_name="Real Match Co",
        evidence_text=evidence_text,
        evidence_as_of_date=None,
    )

    assert outcome is CourtDocketLinkMatchOutcome.VERIFIED_DOCKET_MATCH
    assert best is not None
    assert best.candidate.docket_id == 1
    assert len(evaluated) == 2
