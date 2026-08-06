"""Unit tests for `app/ai/evidence_review.py` (PLAN.md 24.4) — fail-closed
behavior on any malformed/ungrounded AI response, via a fake `LLMProvider`.
No network.
"""

from __future__ import annotations

from app.ai.evidence_review import review_evidence_candidates
from app.ai.providers.base import CompletionRequest, CompletionResponse
from app.core.distress_rules import RuleMatch
from app.core.types import EvidenceSeverity, EvidenceType


class _FakeLLMProvider:
    """Implements just enough of `LLMProvider` for these tests — returns a
    fixed response text regardless of the request, so tests control the
    model's "response" directly."""

    def __init__(self, response_text: str) -> None:
        self._response_text = response_text

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        return CompletionResponse(text=self._response_text, model="fake-model")

    def call_tools(self, request: object) -> object:
        raise NotImplementedError

    def create_embeddings(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError


def _candidate() -> RuleMatch:
    return RuleMatch(
        rule_id="8k_item_1_03_bankruptcy",
        evidence_type=EvidenceType.BANKRUPTCY_OR_RECEIVERSHIP,
        severity=EvidenceSeverity.HIGH,
        matched_text="Item 1.03",
        excerpt="8-K Item 1.03 reported.",
        start_offset=0,
        end_offset=0,
        source_item="Item 1.03",
        confidence=0.95,
    )


def test_no_candidates_returns_none_without_calling_the_model() -> None:
    llm = _FakeLLMProvider(response_text="should never be read")

    result = review_evidence_candidates(
        llm, issuer_name="Example Corp", source_description="SEC Form 8-K", candidates=[]
    )

    assert result is None


def test_well_formed_response_parses_successfully() -> None:
    llm = _FakeLLMProvider(
        response_text=(
            '{"headline": "Potential bankruptcy filing detected in a new 8-K", '
            '"explanation": "The filing reports an Item 1.03 bankruptcy or receivership '
            'event.", "severity": "high", "confidence": 0.9}'
        )
    )

    result = review_evidence_candidates(
        llm,
        issuer_name="Example Corp",
        source_description="SEC Form 8-K filed 2026-08-01",
        candidates=[_candidate()],
    )

    assert result is not None
    assert result.headline == "Potential bankruptcy filing detected in a new 8-K"
    assert result.severity is EvidenceSeverity.HIGH
    assert result.confidence == 0.9


def test_non_json_response_fails_closed() -> None:
    llm = _FakeLLMProvider(response_text="I think this company might be going bankrupt soon.")

    result = review_evidence_candidates(
        llm,
        issuer_name="Example Corp",
        source_description="SEC Form 8-K",
        candidates=[_candidate()],
    )

    assert result is None


def test_missing_required_field_fails_closed() -> None:
    llm = _FakeLLMProvider(response_text='{"headline": "X", "severity": "high", "confidence": 0.9}')

    result = review_evidence_candidates(
        llm,
        issuer_name="Example Corp",
        source_description="SEC Form 8-K",
        candidates=[_candidate()],
    )

    assert result is None


def test_invalid_severity_value_fails_closed() -> None:
    llm = _FakeLLMProvider(
        response_text=(
            '{"headline": "X", "explanation": "Y", "severity": "catastrophic", "confidence": 0.9}'
        )
    )

    result = review_evidence_candidates(
        llm,
        issuer_name="Example Corp",
        source_description="SEC Form 8-K",
        candidates=[_candidate()],
    )

    assert result is None


def test_confidence_out_of_range_fails_closed() -> None:
    llm = _FakeLLMProvider(
        response_text='{"headline": "X", "explanation": "Y", "severity": "high", "confidence": 1.5}'
    )

    result = review_evidence_candidates(
        llm,
        issuer_name="Example Corp",
        source_description="SEC Form 8-K",
        candidates=[_candidate()],
    )

    assert result is None


def test_empty_headline_fails_closed() -> None:
    llm = _FakeLLMProvider(
        response_text=(
            '{"headline": "  ", "explanation": "Y", "severity": "high", "confidence": 0.9}'
        )
    )

    result = review_evidence_candidates(
        llm,
        issuer_name="Example Corp",
        source_description="SEC Form 8-K",
        candidates=[_candidate()],
    )

    assert result is None
