"""Live proof of the AI evidence-review layer (PLAN.md 24.4, 24.7, ADR-017):
a real call to the configured Anthropic model, over a real-shaped Layer 1
candidate, confirming the round-trip actually produces a well-formed,
cautiously-worded result — not just that the mocked unit tests pass.

Skipped gracefully (not failed) if no LLM provider is configured, matching
this project's established gating pattern (`sec_http_client`, `fred_api_key`,
...). No database access — this test only proves the AI call itself works.
"""

from __future__ import annotations

from app.ai.evidence_review import review_evidence_candidates
from app.ai.providers.base import LLMProvider
from app.core.distress_rules import RuleMatch
from app.core.types import EvidenceSeverity, EvidenceType


def test_live_anthropic_call_reviews_a_real_shaped_candidate(
    live_llm_provider: LLMProvider,
) -> None:
    candidate = RuleMatch(
        rule_id="8k_item_1_03_bankruptcy",
        evidence_type=EvidenceType.BANKRUPTCY_OR_RECEIVERSHIP,
        severity=EvidenceSeverity.HIGH,
        matched_text="Item 1.03",
        excerpt=(
            "On August 5, 2026, Example Holdings Corp. and certain of its "
            "subsidiaries filed voluntary petitions for relief under chapter "
            "11 of title 11 of the United States Code in the United States "
            "Bankruptcy Court for the District of Delaware."
        ),
        start_offset=0,
        end_offset=0,
        source_item="Item 1.03",
        confidence=0.95,
    )

    result = review_evidence_candidates(
        live_llm_provider,
        issuer_name="Example Holdings Corp.",
        source_description="SEC Form 8-K filed 2026-08-05",
        candidates=[candidate],
    )

    assert result is not None, "a real Anthropic response for this clear-cut excerpt must parse"
    assert result.headline.strip() != ""
    assert result.explanation.strip() != ""
    assert result.severity in (EvidenceSeverity.HIGH, EvidenceSeverity.MEDIUM)
    assert 0.0 <= result.confidence <= 1.0
    # Cautious-wording spot check: the excerpt genuinely says "bankruptcy",
    # so "bankrupt"/"chapter 11" appearing in the headline is expected and
    # fine — what must NOT appear is a claim beyond what the excerpt states.
    assert "will liquidate" not in result.headline.lower()
    assert "will liquidate" not in result.explanation.lower()
