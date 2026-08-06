"""Layer 2: governed AI review of Layer 1 candidates (PLAN.md 24.4).

Only ever called with candidates a deterministic rule (`app.core.distress_rules`)
already matched — this module never scans raw filing text itself, and the AI
is never the sole detector of anything. `source_description` is a plain
string the caller builds (e.g. `"SEC Form 8-K filed 2026-08-01"`) — this
module has no SEC-specific fields, so a future evidence provider passes its
own description string without any change here (ADR-018).

Fails closed: any parse failure, missing/invalid field, or out-of-range value
in the model's response means `None` — the caller falls back to a
deterministic templated alert rather than accepting an ungrounded AI claim.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from app.ai.providers.base import CompletionRequest, LLMProvider
from app.core.distress_rules import RuleMatch
from app.core.types import EvidenceSeverity

_SYSTEM_PROMPT = (
    "You are a cautious credit-research assistant reviewing excerpts a "
    "deterministic rule engine already flagged in a real SEC filing. Use "
    "ONLY the excerpts provided below — do not infer, assume, or add any "
    "fact not directly supported by the excerpt text. Never assert that a "
    "company is bankrupt, insolvent, or distressed unless the excerpt text "
    "itself says so. Respond with strict JSON only, no markdown, no prose "
    'outside the JSON, matching this exact shape: {"headline": string, '
    '"explanation": string, "severity": "low"|"medium"|"high", "confidence": '
    "number between 0 and 1}. The headline and explanation must be cautious "
    'and evidence-based (e.g. "Potential liquidity warning detected in a '
    'new 10-Q", never "this company is distressed" or "will liquidate").'
)


@dataclass(frozen=True, slots=True)
class EvidenceReviewResult:
    headline: str
    explanation: str
    severity: EvidenceSeverity
    confidence: float


def _build_user_prompt(
    *, issuer_name: str, source_description: str, candidates: list[RuleMatch]
) -> str:
    excerpt_block = "\n".join(
        f'- [{i}] ({c.evidence_type.value}, rule={c.rule_id}): "{c.excerpt}"'
        for i, c in enumerate(candidates)
    )
    return (
        f"Issuer: {issuer_name}\nSource: {source_description}\n\n"
        f"Flagged excerpts:\n{excerpt_block}\n\n"
        "Return the JSON object described in the system prompt, summarizing "
        "and classifying these excerpts together."
    )


def review_evidence_candidates(
    llm: LLMProvider,
    *,
    issuer_name: str,
    source_description: str,
    candidates: list[RuleMatch],
) -> EvidenceReviewResult | None:
    if not candidates:
        return None

    request = CompletionRequest(
        system_prompt=_SYSTEM_PROMPT,
        user_prompt=_build_user_prompt(
            issuer_name=issuer_name, source_description=source_description, candidates=candidates
        ),
    )

    try:
        response = llm.complete(request)
        payload = json.loads(response.text)
        headline = str(payload["headline"]).strip()
        explanation = str(payload["explanation"]).strip()
        severity = EvidenceSeverity(str(payload["severity"]).lower())
        confidence = float(payload["confidence"])
    except (json.JSONDecodeError, KeyError, ValueError, TypeError):
        return None

    if not headline or not explanation:
        return None
    if not 0.0 <= confidence <= 1.0:
        return None

    return EvidenceReviewResult(
        headline=headline, explanation=explanation, severity=severity, confidence=confidence
    )
