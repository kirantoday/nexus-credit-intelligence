"""Unit tests for the Layer 1 deterministic distress-rules engine (PLAN.md 24.4).

No DB, no network — pure pattern matching against real-style filing text.
"""

from __future__ import annotations

from app.core.distress_rules import match_rules
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
