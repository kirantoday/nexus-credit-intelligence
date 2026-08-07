"""Layer 1: deterministic distress-signal detection (PLAN.md 24.4).

Explainable rules over filing metadata (8-K item codes — structured, the
highest-confidence signal available) and plain-text phrase matching. Every
match records exactly which rule fired, the excerpt, and offsets — no
black-box scoring. Deliberately conservative: an ambiguous phrase (a bare
"chapter 11" mention with no stronger context) gets low confidence rather
than being excluded outright or over-trusted, and a specific known
false-positive context ("chapter 11 of the Internal Revenue Code") is
suppressed via `exclude_if_nearby`.

Pure, DB-free, no I/O — only Layer 1 candidates are ever passed to the AI
review layer (`app/ai/evidence_review.py`); this module never calls an LLM.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.types import EvidenceSeverity, EvidenceType

_EXCERPT_CONTEXT_CHARS = 160


@dataclass(frozen=True, slots=True)
class RuleMatch:
    rule_id: str
    evidence_type: EvidenceType
    severity: EvidenceSeverity
    matched_text: str
    excerpt: str
    start_offset: int
    end_offset: int
    source_item: str | None
    confidence: float


@dataclass(frozen=True, slots=True)
class _ItemCodeRule:
    """Matches an 8-K item number present in SEC's `items` metadata field —
    structured data, not a text pattern, so it's the highest-confidence
    signal this layer has."""

    rule_id: str
    item_code: str
    evidence_type: EvidenceType
    severity: EvidenceSeverity
    confidence: float


@dataclass(frozen=True, slots=True)
class _PhraseRule:
    rule_id: str
    pattern: re.Pattern[str]
    evidence_type: EvidenceType
    severity: EvidenceSeverity
    confidence: float
    exclude_if_nearby: re.Pattern[str] | None = None


def _phrase(text: str) -> re.Pattern[str]:
    return re.compile(re.escape(text), re.IGNORECASE)


_ITEM_CODE_RULES: tuple[_ItemCodeRule, ...] = (
    _ItemCodeRule(
        rule_id="8k_item_1_03_bankruptcy",
        item_code="1.03",
        evidence_type=EvidenceType.BANKRUPTCY_OR_RECEIVERSHIP,
        severity=EvidenceSeverity.HIGH,
        confidence=0.95,
    ),
    _ItemCodeRule(
        rule_id="8k_item_2_04_debt_acceleration",
        item_code="2.04",
        evidence_type=EvidenceType.DEBT_ACCELERATION,
        severity=EvidenceSeverity.HIGH,
        confidence=0.85,
    ),
    _ItemCodeRule(
        rule_id="8k_item_3_01_delisting",
        item_code="3.01",
        evidence_type=EvidenceType.DELISTING_NOTICE,
        severity=EvidenceSeverity.MEDIUM,
        confidence=0.85,
    ),
    _ItemCodeRule(
        rule_id="8k_item_4_01_auditor_change",
        item_code="4.01",
        evidence_type=EvidenceType.AUDITOR_RESIGNATION,
        severity=EvidenceSeverity.MEDIUM,
        confidence=0.6,
    ),
)

_PHRASE_RULES: tuple[_PhraseRule, ...] = (
    _PhraseRule(
        rule_id="phrase_chapter_11_petition",
        pattern=re.compile(
            r"(voluntary petition|filed.{0,40}under chapter 11"
            r"|chapter 11.{0,40}bankruptcy|commenced.{0,40}chapter 11)",
            re.IGNORECASE,
        ),
        evidence_type=EvidenceType.CHAPTER_11,
        severity=EvidenceSeverity.HIGH,
        confidence=0.9,
    ),
    _PhraseRule(
        rule_id="phrase_chapter_11_bare_mention",
        pattern=_phrase("chapter 11"),
        evidence_type=EvidenceType.CHAPTER_11,
        severity=EvidenceSeverity.LOW,
        confidence=0.3,
        exclude_if_nearby=re.compile(
            r"internal revenue code|title 11.{0,20}code|chapter 11 of the", re.IGNORECASE
        ),
    ),
    _PhraseRule(
        rule_id="phrase_chapter_7_petition",
        pattern=re.compile(r"chapter 7.{0,40}(bankruptcy|petition|liquidation)", re.IGNORECASE),
        evidence_type=EvidenceType.CHAPTER_7,
        severity=EvidenceSeverity.HIGH,
        confidence=0.9,
    ),
    _PhraseRule(
        rule_id="phrase_missed_interest_payment",
        pattern=re.compile(
            r"(missed.{0,20}interest payment"
            r"|failed to make.{0,30}(interest|principal) payment)",
            re.IGNORECASE,
        ),
        evidence_type=EvidenceType.DEFAULT_OR_MISSED_PAYMENT,
        severity=EvidenceSeverity.HIGH,
        confidence=0.85,
    ),
    _PhraseRule(
        rule_id="phrase_event_of_default",
        pattern=_phrase("event of default"),
        evidence_type=EvidenceType.COVENANT_BREACH,
        severity=EvidenceSeverity.HIGH,
        confidence=0.8,
    ),
    _PhraseRule(
        rule_id="phrase_debt_acceleration",
        pattern=re.compile(
            r"acceleration of.{0,40}(indebtedness|obligations|maturity)", re.IGNORECASE
        ),
        evidence_type=EvidenceType.DEBT_ACCELERATION,
        severity=EvidenceSeverity.HIGH,
        confidence=0.8,
    ),
    _PhraseRule(
        rule_id="phrase_substantial_doubt_going_concern",
        pattern=re.compile(
            r"substantial doubt.{0,40}ability to continue as a going concern", re.IGNORECASE
        ),
        evidence_type=EvidenceType.SUBSTANTIAL_DOUBT,
        severity=EvidenceSeverity.HIGH,
        confidence=0.9,
    ),
    _PhraseRule(
        rule_id="phrase_going_concern_bare_mention",
        pattern=_phrase("going concern"),
        evidence_type=EvidenceType.GOING_CONCERN,
        severity=EvidenceSeverity.LOW,
        confidence=0.35,
    ),
    _PhraseRule(
        rule_id="phrase_liquidity_shortfall",
        pattern=re.compile(
            r"(liquidity shortfall|insufficient liquidity|liquidity constraints)", re.IGNORECASE
        ),
        evidence_type=EvidenceType.LIQUIDITY_WARNING,
        severity=EvidenceSeverity.MEDIUM,
        confidence=0.65,
    ),
    _PhraseRule(
        rule_id="phrase_restructuring_advisor",
        pattern=re.compile(
            r"(engaged|retained).{0,40}(restructuring|financial) advisor", re.IGNORECASE
        ),
        evidence_type=EvidenceType.RESTRUCTURING_ADVISOR,
        severity=EvidenceSeverity.MEDIUM,
        confidence=0.6,
    ),
    _PhraseRule(
        rule_id="phrase_restructuring_support_agreement",
        pattern=_phrase("restructuring support agreement"),
        evidence_type=EvidenceType.RESTRUCTURING_SUPPORT_AGREEMENT,
        severity=EvidenceSeverity.HIGH,
        confidence=0.9,
    ),
    _PhraseRule(
        rule_id="phrase_exchange_offer",
        pattern=_phrase("exchange offer"),
        evidence_type=EvidenceType.EXCHANGE_OFFER,
        severity=EvidenceSeverity.MEDIUM,
        confidence=0.7,
    ),
    _PhraseRule(
        rule_id="phrase_liability_management",
        pattern=re.compile(r"liability management (transaction|exercise)", re.IGNORECASE),
        evidence_type=EvidenceType.LIABILITY_MANAGEMENT_TRANSACTION,
        severity=EvidenceSeverity.MEDIUM,
        confidence=0.7,
    ),
    _PhraseRule(
        rule_id="phrase_amend_and_extend",
        pattern=_phrase("amend and extend"),
        evidence_type=EvidenceType.MATURITY_EXTENSION,
        severity=EvidenceSeverity.MEDIUM,
        confidence=0.7,
    ),
    _PhraseRule(
        rule_id="phrase_maturity_extension",
        pattern=re.compile(r"extend(ed|s|ing)? the maturity", re.IGNORECASE),
        evidence_type=EvidenceType.MATURITY_EXTENSION,
        severity=EvidenceSeverity.MEDIUM,
        confidence=0.65,
    ),
    _PhraseRule(
        rule_id="phrase_refinancing",
        pattern=re.compile(
            r"refinanc(e|ed|ing) (its|the|our) (debt|credit facility|notes)", re.IGNORECASE
        ),
        evidence_type=EvidenceType.REFINANCING,
        severity=EvidenceSeverity.LOW,
        confidence=0.5,
    ),
    _PhraseRule(
        rule_id="phrase_dip_financing",
        pattern=re.compile(r"(debtor.in.possession|\bDIP\b) financing", re.IGNORECASE),
        evidence_type=EvidenceType.DIP_FINANCING,
        severity=EvidenceSeverity.HIGH,
        confidence=0.9,
    ),
    _PhraseRule(
        rule_id="phrase_emergency_financing",
        pattern=re.compile(r"emergency (financing|funding|credit facility)", re.IGNORECASE),
        evidence_type=EvidenceType.EMERGENCY_FINANCING,
        severity=EvidenceSeverity.HIGH,
        confidence=0.75,
    ),
    _PhraseRule(
        rule_id="phrase_material_asset_sale",
        pattern=re.compile(
            r"sale of (substantially all|a material portion of).{0,20}assets", re.IGNORECASE
        ),
        evidence_type=EvidenceType.MATERIAL_ASSET_SALE,
        severity=EvidenceSeverity.MEDIUM,
        confidence=0.7,
    ),
    _PhraseRule(
        rule_id="phrase_delisting_notice",
        pattern=re.compile(
            r"(delisting|noncompliance with.{0,30}listing (standards|requirements))",
            re.IGNORECASE,
        ),
        evidence_type=EvidenceType.DELISTING_NOTICE,
        severity=EvidenceSeverity.MEDIUM,
        confidence=0.75,
    ),
    _PhraseRule(
        rule_id="phrase_workforce_reduction",
        pattern=re.compile(
            r"(workforce reduction|reduction in force|reduce.{0,20}workforce by)", re.IGNORECASE
        ),
        evidence_type=EvidenceType.WORKFORCE_REDUCTION,
        severity=EvidenceSeverity.LOW,
        confidence=0.6,
    ),
    _PhraseRule(
        rule_id="phrase_facility_closure",
        pattern=re.compile(
            r"clos(e|ing|ed) (the|its|a) (facility|plant|manufacturing facility)", re.IGNORECASE
        ),
        evidence_type=EvidenceType.FACILITY_CLOSURE,
        severity=EvidenceSeverity.LOW,
        confidence=0.55,
    ),
    _PhraseRule(
        rule_id="phrase_material_impairment",
        pattern=re.compile(r"(material impairment|impairment charge)", re.IGNORECASE),
        evidence_type=EvidenceType.MATERIAL_IMPAIRMENT,
        severity=EvidenceSeverity.MEDIUM,
        confidence=0.6,
    ),
    _PhraseRule(
        rule_id="phrase_auditor_resignation",
        pattern=re.compile(r"(auditor|accountant).{0,20}resign", re.IGNORECASE),
        evidence_type=EvidenceType.AUDITOR_RESIGNATION,
        severity=EvidenceSeverity.MEDIUM,
        confidence=0.75,
    ),
    _PhraseRule(
        rule_id="phrase_adverse_audit_opinion",
        pattern=re.compile(r"adverse opinion", re.IGNORECASE),
        evidence_type=EvidenceType.ADVERSE_AUDIT_DEVELOPMENT,
        severity=EvidenceSeverity.MEDIUM,
        confidence=0.7,
    ),
    _PhraseRule(
        rule_id="phrase_strategic_alternatives",
        pattern=re.compile(
            r"(review of|explore|evaluating).{0,20}strategic alternatives", re.IGNORECASE
        ),
        evidence_type=EvidenceType.STRATEGIC_ALTERNATIVES,
        severity=EvidenceSeverity.MEDIUM,
        confidence=0.7,
    ),
    _PhraseRule(
        rule_id="phrase_debt_amendment",
        pattern=re.compile(
            r"amend(ed|ment).{0,30}(credit agreement|indenture|credit facility)", re.IGNORECASE
        ),
        evidence_type=EvidenceType.DEBT_AMENDMENT,
        severity=EvidenceSeverity.LOW,
        confidence=0.5,
    ),
    # Docket-specific rules added in Milestone 7 — real docket-entry
    # language patterns confirmed live against CourtListener's actual RECAP
    # data (BUILD_LOG.md), not guessed at. Applied through the same
    # `match_rules` entry point court docket entries share with SEC filing
    # text (both are just English prose to this layer) — no separate rule
    # engine needed.
    _PhraseRule(
        rule_id="phrase_plan_confirmed",
        pattern=re.compile(
            r"(order confirming.{0,30}plan|confirmation of.{0,20}plan"
            r"|plan.{0,20}(was |is |has been )?confirmed)",
            re.IGNORECASE,
        ),
        evidence_type=EvidenceType.PLAN_CONFIRMED,
        severity=EvidenceSeverity.MEDIUM,
        confidence=0.75,
    ),
    _PhraseRule(
        rule_id="phrase_case_dismissed",
        pattern=re.compile(
            r"(order dismissing|case.{0,10}(is |was )?dismissed"
            r"|dismissal of.{0,20}(case|petition))",
            re.IGNORECASE,
        ),
        evidence_type=EvidenceType.CASE_DISMISSED,
        severity=EvidenceSeverity.MEDIUM,
        confidence=0.7,
    ),
    _PhraseRule(
        rule_id="phrase_case_converted_chapter_7",
        pattern=re.compile(
            r"convert(ed|ing)?.{0,30}chapter 7|conversion to chapter 7", re.IGNORECASE
        ),
        evidence_type=EvidenceType.CASE_CONVERTED,
        severity=EvidenceSeverity.HIGH,
        confidence=0.85,
    ),
    _PhraseRule(
        rule_id="phrase_trustee_appointed",
        pattern=re.compile(
            r"(appointment of.{0,20}trustee|trustee.{0,20}(is |was )?appointed)", re.IGNORECASE
        ),
        evidence_type=EvidenceType.TRUSTEE_APPOINTED,
        severity=EvidenceSeverity.HIGH,
        confidence=0.8,
    ),
    _PhraseRule(
        rule_id="phrase_claims_bar_date",
        pattern=re.compile(r"(claims )?bar date", re.IGNORECASE),
        evidence_type=EvidenceType.CLAIMS_BAR_DATE_SET,
        severity=EvidenceSeverity.LOW,
        confidence=0.5,
    ),
    _PhraseRule(
        rule_id="phrase_relief_from_stay",
        pattern=re.compile(r"relief from.{0,10}(the )?(automatic )?stay", re.IGNORECASE),
        evidence_type=EvidenceType.RELIEF_FROM_STAY_MOTION,
        severity=EvidenceSeverity.MEDIUM,
        confidence=0.55,
    ),
)


# Layer 0 (PLAN.md Milestone 7.5) — a curated subset of the Layer 1 phrase
# vocabulary above, chosen for SEC full-text-search precision, not every
# regex mirrored 1:1. This is SEC's own server-side pre-filter across the
# *entire* market (every filer, not just Nexus's known issuers) — cheap
# because SEC's index does the narrowing, not a local download-and-regex
# pass. Every query here corresponds to a high-signal `_PHRASE_RULES` rule
# id (noted per entry) so a Layer-0 hit is very likely, though never
# guaranteed, to also produce a real Layer 1 match once the actual filing
# document is fetched and locally rule-matched — Layer 0 finds candidates,
# it does not itself decide evidence. Bare single-concept phrases ("chapter
# 11", "going concern") are intentionally included despite being lower
# local-rule confidence, precisely because narrowing the *discovery* net
# too aggressively would miss real distress filings that use less
# formulaic language — Layer 1 and Layer 2 remain the actual precision
# gates, not this list.
MARKET_DISCOVERY_FULL_TEXT_QUERIES: tuple[str, ...] = (
    "voluntary petition",  # phrase_chapter_11_petition
    "chapter 11",  # phrase_chapter_11_bare_mention / phrase_chapter_11_petition
    "chapter 7 bankruptcy",  # phrase_chapter_7_petition
    "missed interest payment",  # phrase_missed_interest_payment
    "event of default",  # phrase_event_of_default
    "acceleration of indebtedness",  # phrase_debt_acceleration
    "substantial doubt",  # phrase_substantial_doubt_going_concern
    "going concern",  # phrase_going_concern_bare_mention
    "liquidity shortfall",  # phrase_liquidity_shortfall
    "restructuring advisor",  # phrase_restructuring_advisor
    "restructuring support agreement",  # phrase_restructuring_support_agreement
    "exchange offer",  # phrase_exchange_offer
    "liability management transaction",  # phrase_liability_management
    "debtor-in-possession financing",  # phrase_dip_financing
    "strategic alternatives",  # phrase_strategic_alternatives
    "delisting",  # phrase_delisting_notice
    "material impairment",  # phrase_material_impairment
    "auditor resignation",  # phrase_auditor_resignation
)


def _excerpt_window(text: str, match: re.Match[str]) -> tuple[str, int, int]:
    start = max(0, match.start() - _EXCERPT_CONTEXT_CHARS)
    end = min(len(text), match.end() + _EXCERPT_CONTEXT_CHARS)
    return text[start:end].strip(), start, end


# Rules deliberately excluded from docket-entry text (PLAN.md sections 4.5,
# 15, Milestone 7). Their whole purpose is flagging an *ambiguous* mention
# in a context where distress status is otherwise unknown (e.g. "chapter
# 11" appearing in an SEC filing might mean the Internal Revenue Code, not
# bankruptcy). A docket entry never has that ambiguity — this codebase only
# ever syncs entries for a docket already confirmed to *be* the bankruptcy
# case (`app.scripts.link_court_dockets` requires live verification before
# linking). Live-caught real signal-to-noise problem, not a hypothetical:
# an active Chapter 11 case's docket routinely references "the Chapter 11
# Case"/"Chapter 11 Cases" in the boilerplate of nearly every procedural
# entry (hearing notices, receipts, appearances) — applying the bare-mention
# rule there produced 83 near-duplicate low-value alerts from one real
# docket's 429 entries before this exclusion existed (see BUILD_LOG.md).
DOCKET_EXCLUDED_RULE_IDS: frozenset[str] = frozenset(
    {"phrase_chapter_11_bare_mention", "phrase_going_concern_bare_mention"}
)


def match_rules(
    *,
    form_type: str,
    item_codes: str | None,
    text: str,
    exclude_rule_ids: frozenset[str] = frozenset(),
) -> list[RuleMatch]:
    """Run every Layer 1 rule against one filing's item codes + extracted
    text. A filing can trigger several rules — the caller (`filing_monitor_service`)
    decides how to aggregate matches into evidence/alerts, this function only
    detects and explains.

    `form_type` is accepted for future form-scoped rules (e.g. an item-code
    rule only makes sense for 8-K filings, which is naturally already true
    since only 8-Ks carry `items`) — no rule currently filters on it, kept in
    the signature so the caller doesn't need to change when one does.

    `exclude_rule_ids` lets a caller opt specific rule ids out entirely —
    used by `app.services.court_docket_service` to exclude
    `DOCKET_EXCLUDED_RULE_IDS` (see that constant's docstring); empty by
    default so every existing SEC-filing caller is unaffected.
    """
    matches: list[RuleMatch] = []

    codes = {code.strip() for code in (item_codes or "").split(",") if code.strip()}
    for item_rule in _ITEM_CODE_RULES:
        if item_rule.rule_id in exclude_rule_ids:
            continue
        if item_rule.item_code in codes:
            matches.append(
                RuleMatch(
                    rule_id=item_rule.rule_id,
                    evidence_type=item_rule.evidence_type,
                    severity=item_rule.severity,
                    matched_text=f"Item {item_rule.item_code}",
                    excerpt=f"{form_type} Item {item_rule.item_code} reported.",
                    start_offset=0,
                    end_offset=0,
                    source_item=f"Item {item_rule.item_code}",
                    confidence=item_rule.confidence,
                )
            )

    for phrase_rule in _PHRASE_RULES:
        if phrase_rule.rule_id in exclude_rule_ids:
            continue
        for m in phrase_rule.pattern.finditer(text):
            if phrase_rule.exclude_if_nearby is not None:
                window_start = max(0, m.start() - _EXCERPT_CONTEXT_CHARS)
                window_end = min(len(text), m.end() + _EXCERPT_CONTEXT_CHARS)
                if phrase_rule.exclude_if_nearby.search(text[window_start:window_end]):
                    continue
            excerpt, start, end = _excerpt_window(text, m)
            matches.append(
                RuleMatch(
                    rule_id=phrase_rule.rule_id,
                    evidence_type=phrase_rule.evidence_type,
                    severity=phrase_rule.severity,
                    matched_text=m.group(0),
                    excerpt=excerpt,
                    start_offset=start,
                    end_offset=end,
                    source_item=None,
                    confidence=phrase_rule.confidence,
                )
            )
            # One match per rule per filing is enough signal — avoids
            # flooding `research_evidence` with repeats of the same phrase.
            break
    return matches
