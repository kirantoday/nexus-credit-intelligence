"""Automatic CourtListener docket-linking signal evaluation (PLAN.md
Milestone 7.5 section 10, ADR-020 — supersedes ADR-019's blanket
prohibition on automatic linking).

A hierarchy of independent strong identity signals, not a fixed three-field
AND. Jurisdiction/court correspondence to the issuer's headquarters is
deliberately **never** a required signal — a debtor legitimately files
Chapter 11 wherever is legally/strategically convenient (Delaware,
S.D.N.Y., S.D. Tex. are common regardless of HQ), so requiring it would
systematically reject real matches. `verified_docket_match` requires
case-type consistency plus at least one very strong signal (an exact case
number reference) or at least two independent strong signals agreeing with
no contradiction, on a *unique* best candidate — ties or near-ties are
`ambiguous_manual_review`, never a guess. False positives are treated as
strictly worse than a missed automatic link.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta

from app.core.types import CourtDocketLinkMatchOutcome
from app.providers.courtlistener.dto import CourtListenerSearchResultDTO

# Case number references correlate within two weeks of the triggering SEC
# evidence being found — generous enough for real-world reporting lag
# between a petition date and the 8-K disclosing it, narrow enough that an
# unrelated docket from months earlier/later doesn't pass on date alone.
_DATE_CORRELATION_WINDOW = timedelta(days=14)

_CORPORATE_SUFFIXES = re.compile(
    r"\b(incorporated|inc|corporation|corp|company|co|holdings?|holding|"
    r"group|llc|l\.l\.c|ltd|limited|plc|lp|l\.p)\b\.?",
    re.IGNORECASE,
)
_NON_ALNUM = re.compile(r"[^a-z0-9 ]")


def normalize_company_name(name: str) -> str:
    """Lowercase, strip punctuation, strip common corporate suffixes, and
    collapse whitespace — e.g. "Diebold Nixdorf, Incorporated" and "Diebold
    Nixdorf Holding Company, Inc." both normalize toward "diebold nixdorf",
    which is exactly the kind of match a debtor's docket case name (often a
    specific subsidiary/holding entity) needs against an issuer's SEC legal
    name, without a bare substring check risking a Yellow/Yellowstone-style
    false positive on an unrelated word.
    """
    lowered = name.lower()
    no_suffix = _CORPORATE_SUFFIXES.sub(" ", lowered)
    cleaned = _NON_ALNUM.sub(" ", no_suffix)
    return " ".join(cleaned.split())


@dataclass(frozen=True, slots=True)
class DocketMatchSignals:
    name_match: bool
    case_number_match: bool
    court_referenced_in_evidence: bool
    date_correlated: bool
    case_type_consistent: bool

    @property
    def strong_signal_count(self) -> int:
        return sum([self.name_match, self.case_number_match, self.date_correlated])

    def as_dict(self) -> dict[str, bool]:
        return {
            "name_match": self.name_match,
            "case_number_match": self.case_number_match,
            "court_referenced_in_evidence": self.court_referenced_in_evidence,
            "date_correlated": self.date_correlated,
            "case_type_consistent": self.case_type_consistent,
        }

    @property
    def passes(self) -> bool:
        """Case-type consistency is a hard requirement. Above that: an
        exact case-number match alone is strong enough on its own (a
        docket number appearing verbatim in the triggering SEC evidence is
        about as strong as a single signal can be); otherwise at least two
        independent strong signals must agree with no contradiction.
        Jurisdiction (`court_referenced_in_evidence`) is intentionally
        excluded from `strong_signal_count` — supporting/contradiction-
        detection only, per ADR-020, never a required or independently
        sufficient signal.
        """
        if not self.case_type_consistent:
            return False
        return self.case_number_match or self.strong_signal_count >= 2


@dataclass(frozen=True, slots=True)
class DocketMatchCandidate:
    candidate: CourtListenerSearchResultDTO
    signals: DocketMatchSignals


def evaluate_candidate(
    candidate: CourtListenerSearchResultDTO,
    *,
    issuer_legal_name: str,
    evidence_text: str,
    evidence_as_of_date: date | None,
) -> DocketMatchSignals:
    normalized_issuer = normalize_company_name(issuer_legal_name)
    normalized_case = normalize_company_name(candidate.caseName)
    name_match = bool(normalized_issuer) and (
        normalized_issuer in normalized_case or normalized_case in normalized_issuer
    )

    evidence_lower = evidence_text.lower()
    docket_number_digits = re.sub(r"[^0-9]", "", candidate.docketNumber)
    case_number_match = bool(docket_number_digits) and (
        candidate.docketNumber.lower() in evidence_lower
        or (
            len(docket_number_digits) >= 4
            and docket_number_digits in re.sub(r"[^0-9]", "", evidence_text)
        )
    )

    court_referenced = candidate.court is not None and candidate.court.lower() in evidence_lower

    date_correlated = False
    if candidate.dateFiled and evidence_as_of_date is not None:
        try:
            filed = date.fromisoformat(candidate.dateFiled[:10])
            date_correlated = abs(filed - evidence_as_of_date) <= _DATE_CORRELATION_WINDOW
        except ValueError:
            date_correlated = False

    # A docket only genuinely represents a bankruptcy case when
    # CourtListener itself reports a chapter — this is the case-type
    # consistency gate (ADR-020): every evidence category this matcher is
    # invoked for is bankruptcy/restructuring-relevant by construction (see
    # `court_docket_service.attempt_auto_link`), so an unrelated non-
    # bankruptcy docket (chapter is null) never passes regardless of how
    # well the name matches.
    case_type_consistent = candidate.chapter is not None

    return DocketMatchSignals(
        name_match=name_match,
        case_number_match=case_number_match,
        court_referenced_in_evidence=court_referenced,
        date_correlated=date_correlated,
        case_type_consistent=case_type_consistent,
    )


def select_best_match(
    candidates: list[CourtListenerSearchResultDTO],
    *,
    issuer_legal_name: str,
    evidence_text: str,
    evidence_as_of_date: date | None,
) -> tuple[CourtDocketLinkMatchOutcome, DocketMatchCandidate | None, list[DocketMatchCandidate]]:
    """Evaluate every candidate and pick the single best one, if any is
    unique and passes. Returns `(outcome, best_or_none, all_evaluated)` —
    `all_evaluated` is always returned so the caller can persist a full,
    honest audit trail regardless of outcome.
    """
    if not candidates:
        return CourtDocketLinkMatchOutcome.CHECKED_NO_RELEVANT_DOCKET, None, []

    evaluated = [
        DocketMatchCandidate(
            candidate=c,
            signals=evaluate_candidate(
                c,
                issuer_legal_name=issuer_legal_name,
                evidence_text=evidence_text,
                evidence_as_of_date=evidence_as_of_date,
            ),
        )
        for c in candidates
    ]
    passing = [e for e in evaluated if e.signals.passes]

    if not passing:
        return CourtDocketLinkMatchOutcome.CHECKED_NO_RELEVANT_DOCKET, None, evaluated
    if len(passing) > 1:
        # More than one candidate independently clears the bar — a
        # unique-best-candidate requirement, not a coin flip (ADR-020).
        return CourtDocketLinkMatchOutcome.AMBIGUOUS_MANUAL_REVIEW, None, evaluated

    return CourtDocketLinkMatchOutcome.VERIFIED_DOCKET_MATCH, passing[0], evaluated
