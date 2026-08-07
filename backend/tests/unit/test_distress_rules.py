"""Unit tests for the Layer 1 deterministic distress-rules engine (PLAN.md 24.4).

No DB, no network — pure pattern matching against real-style filing text.
"""

from __future__ import annotations

from app.core.distress_rules import DOCKET_EXCLUDED_RULE_IDS, match_rules
from app.core.types import EvidenceSeverity, EvidenceType


def test_item_code_rule_matches_bankruptcy_item_1_03() -> None:
    matches = match_rules(form_type="8-K", item_codes="1.03", text="")

    assert len(matches) == 1
    match = matches[0]
    assert match.rule_id == "8k_item_1_03_bankruptcy"
    assert match.evidence_type is EvidenceType.BANKRUPTCY_OR_RECEIVERSHIP
    assert match.severity is EvidenceSeverity.HIGH
    assert match.source_item == "Item 1.03"
    assert match.confidence >= 0.9


def test_item_code_rule_ignores_unrelated_items() -> None:
    matches = match_rules(form_type="8-K", item_codes="2.02,9.01", text="")
    assert matches == []


def test_item_code_rule_handles_multiple_codes_on_one_filing() -> None:
    matches = match_rules(form_type="8-K", item_codes="1.03,2.04", text="")
    rule_ids = {m.rule_id for m in matches}
    assert rule_ids == {"8k_item_1_03_bankruptcy", "8k_item_2_04_debt_acceleration"}


def test_chapter_11_petition_phrase_matches_high_confidence() -> None:
    text = (
        "On August 5, 2026, the Company and certain of its subsidiaries filed "
        "voluntary petitions for relief under chapter 11 of the United States "
        "Bankruptcy Code in the United States Bankruptcy Court."
    )
    matches = match_rules(form_type="8-K", item_codes=None, text=text)

    strong = [m for m in matches if m.rule_id == "phrase_chapter_11_petition"]
    assert len(strong) == 1
    assert strong[0].evidence_type is EvidenceType.CHAPTER_11
    assert strong[0].severity is EvidenceSeverity.HIGH
    assert "voluntary petitions" in strong[0].excerpt.lower()


def test_chapter_11_false_positive_irs_code_is_suppressed() -> None:
    """A real false-positive shape: 'chapter 11' referring to the Internal
    Revenue Code, not a bankruptcy filing — must not fire the bare-mention
    rule at all (PLAN.md's explicit false-positive safeguard requirement)."""
    text = (
        "The Company's tax position is governed by chapter 11 of the "
        "Internal Revenue Code and related Treasury regulations."
    )
    matches = match_rules(form_type="10-K", item_codes=None, text=text)

    assert not any(m.rule_id == "phrase_chapter_11_bare_mention" for m in matches)
    assert not any(m.evidence_type is EvidenceType.CHAPTER_11 for m in matches)


def test_chapter_11_bare_mention_without_false_positive_context_is_low_confidence() -> None:
    text = "Management continues to evaluate options, including chapter 11, as part of its review."
    matches = match_rules(form_type="10-Q", item_codes=None, text=text)

    bare = [m for m in matches if m.rule_id == "phrase_chapter_11_bare_mention"]
    assert len(bare) == 1
    assert bare[0].severity is EvidenceSeverity.LOW
    assert bare[0].confidence < 0.5


def test_substantial_doubt_going_concern_phrase() -> None:
    text = (
        "These conditions raise substantial doubt about the Company's "
        "ability to continue as a going concern."
    )
    matches = match_rules(form_type="10-Q", item_codes=None, text=text)

    strong = [m for m in matches if m.rule_id == "phrase_substantial_doubt_going_concern"]
    assert len(strong) == 1
    assert strong[0].evidence_type is EvidenceType.SUBSTANTIAL_DOUBT
    assert strong[0].severity is EvidenceSeverity.HIGH


def test_restructuring_support_agreement_phrase() -> None:
    text = (
        "The Company entered into a Restructuring Support Agreement with "
        "holders of its senior notes."
    )
    matches = match_rules(form_type="8-K", item_codes=None, text=text)

    assert any(
        m.rule_id == "phrase_restructuring_support_agreement"
        and m.evidence_type is EvidenceType.RESTRUCTURING_SUPPORT_AGREEMENT
        for m in matches
    )


def test_dip_financing_phrase() -> None:
    text = "The Company obtained debtor-in-possession financing of $100 million."
    matches = match_rules(form_type="8-K", item_codes=None, text=text)

    assert any(m.evidence_type is EvidenceType.DIP_FINANCING for m in matches)


def test_no_matches_on_clean_filing_text() -> None:
    text = (
        "Revenue increased 12% year over year, driven by strong demand in "
        "our core product lines. We remain focused on operational excellence."
    )
    matches = match_rules(form_type="10-Q", item_codes=None, text=text)
    assert matches == []


def test_each_matched_rule_fires_at_most_once_per_filing() -> None:
    text = "chapter 11 " * 5  # same phrase repeated many times
    matches = match_rules(form_type="10-Q", item_codes=None, text=text)

    bare_mentions = [m for m in matches if m.rule_id == "phrase_chapter_11_bare_mention"]
    assert len(bare_mentions) == 1, "one excerpt per rule per filing, not one per occurrence"


def test_excerpt_includes_surrounding_context() -> None:
    text = "A" * 200 + " event of default " + "B" * 200
    matches = match_rules(form_type="8-K", item_codes=None, text=text)

    match = next(m for m in matches if m.rule_id == "phrase_event_of_default")
    assert "event of default" in match.excerpt.lower()
    assert len(match.excerpt) < len(text), "excerpt is a window, not the whole document"


# Docket-specific rules (Milestone 7) — the same `match_rules` entry point
# court docket entries share with SEC filing text (PLAN.md 24.4/section 4.5).
# Text below matches real CourtListener docket-entry language patterns
# confirmed live during Milestone 7 development (see BUILD_LOG.md), not
# guessed at.


def test_docket_chapter_11_voluntary_petition_matches_existing_sec_rule() -> None:
    """A real CourtListener docket entry #1 description — deliberately
    reuses the same `phrase_chapter_11_petition` rule SEC filings already
    match; no separate docket rule engine is needed for this signal."""
    text = (
        "Chapter 11 Voluntary Petition Non-Individual Fee Amount $1738 "
        "Filed by Diebold Holding Company, Inc.. (Argeroplos, Victoria) (Entered: 06/01/2023)"
    )
    matches = match_rules(form_type="Docket Entry", item_codes=None, text=text)

    assert any(m.rule_id == "phrase_chapter_11_petition" for m in matches)
    assert any(m.evidence_type is EvidenceType.CHAPTER_11 for m in matches)


def test_docket_plan_confirmed_phrase() -> None:
    text = "Order Confirming Debtors' Third Amended Joint Plan of Reorganization."
    matches = match_rules(form_type="Docket Entry", item_codes=None, text=text)

    assert any(
        m.rule_id == "phrase_plan_confirmed" and m.evidence_type is EvidenceType.PLAN_CONFIRMED
        for m in matches
    )


def test_docket_case_dismissed_phrase() -> None:
    text = "Order Dismissing Chapter 11 Case entered by the Court."
    matches = match_rules(form_type="Docket Entry", item_codes=None, text=text)

    assert any(
        m.rule_id == "phrase_case_dismissed" and m.evidence_type is EvidenceType.CASE_DISMISSED
        for m in matches
    )


def test_docket_case_converted_to_chapter_7_phrase() -> None:
    text = "Order granting motion to convert case to chapter 7."
    matches = match_rules(form_type="Docket Entry", item_codes=None, text=text)

    assert any(
        m.rule_id == "phrase_case_converted_chapter_7"
        and m.evidence_type is EvidenceType.CASE_CONVERTED
        and m.severity is EvidenceSeverity.HIGH
        for m in matches
    )


def test_docket_trustee_appointed_phrase() -> None:
    text = "Notice of Appointment of Chapter 11 Trustee filed by the U.S. Trustee."
    matches = match_rules(form_type="Docket Entry", item_codes=None, text=text)

    assert any(
        m.rule_id == "phrase_trustee_appointed"
        and m.evidence_type is EvidenceType.TRUSTEE_APPOINTED
        for m in matches
    )


def test_docket_claims_bar_date_phrase() -> None:
    text = "Order Establishing Bar Date for Filing Proofs of Claim."
    matches = match_rules(form_type="Docket Entry", item_codes=None, text=text)

    assert any(
        m.rule_id == "phrase_claims_bar_date"
        and m.evidence_type is EvidenceType.CLAIMS_BAR_DATE_SET
        for m in matches
    )


def test_exclude_rule_ids_suppresses_the_bare_mention_rule() -> None:
    """Regression test for a real signal-to-noise problem caught live: an
    active Chapter 11 case's real docket routinely references "the Chapter
    11 Case(s)" in nearly every procedural entry's boilerplate — one real
    429-entry docket produced 83 near-duplicate low-value alerts before
    `court_docket_service` started passing `DOCKET_EXCLUDED_RULE_IDS` (see
    BUILD_LOG.md)."""
    text = "Notice of Appearance and Request for Notice Filed in the Chapter 11 Cases."

    unfiltered = match_rules(form_type="Docket Entry", item_codes=None, text=text)
    assert any(m.rule_id == "phrase_chapter_11_bare_mention" for m in unfiltered)

    filtered = match_rules(
        form_type="Docket Entry",
        item_codes=None,
        text=text,
        exclude_rule_ids=DOCKET_EXCLUDED_RULE_IDS,
    )
    assert not any(m.rule_id == "phrase_chapter_11_bare_mention" for m in filtered)
    assert filtered == []


def test_exclude_rule_ids_does_not_suppress_a_strong_signal() -> None:
    """The exclusion only removes the two ambiguous "bare mention" rules —
    a genuinely strong docket-entry signal (e.g. a real petition or relief-
    from-stay motion) still fires normally."""
    text = "Receipt of Motion for Relief From Stay Filing Fee. Fee amount $188.00."

    filtered = match_rules(
        form_type="Docket Entry",
        item_codes=None,
        text=text,
        exclude_rule_ids=DOCKET_EXCLUDED_RULE_IDS,
    )
    assert any(m.rule_id == "phrase_relief_from_stay" for m in filtered)


def test_docket_relief_from_stay_phrase() -> None:
    """A real docket-entry pattern confirmed live: 'Receipt of Motion for
    Relief From Stay' (Diebold Nixdorf docket 23-90602)."""
    text = "Receipt of Motion for Relief From Stay Filing Fee. Fee amount $188.00."
    matches = match_rules(form_type="Docket Entry", item_codes=None, text=text)

    assert any(
        m.rule_id == "phrase_relief_from_stay"
        and m.evidence_type is EvidenceType.RELIEF_FROM_STAY_MOTION
        for m in matches
    )
