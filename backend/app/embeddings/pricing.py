"""Embedding price table and cost estimation (Milestone 10D.2).

Mirrors `app.ai.pricing`'s honesty rule: **an unknown price is `None`,
never zero.** No real vendor is listed because none has been selected or
approved (the bake-off is deferred), and this project's rule is never to
invent prices. A real entry is added only together with the approved model,
verified against the vendor's official pricing page at that time.

Embeddings are billed on input tokens only, which is why this is not
folded into `app.ai.pricing.estimate_cost_usd` (that function returns
`None` unless output tokens are known).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.embeddings.fake import FAKE_MODEL_ID, FAKE_PROVIDER_NAME
from app.embeddings.openai_provider import OPENAI_MODEL_ID, OPENAI_PROVIDER_NAME


@dataclass(frozen=True, slots=True)
class EmbeddingPricing:
    input_usd_per_million_tokens: float


# (provider, model_id) -> price. The fake provider genuinely costs nothing,
# so its entry is an explicit, known zero — distinct from "unknown".
_PRICING: dict[tuple[str, str], EmbeddingPricing] = {
    (FAKE_PROVIDER_NAME, FAKE_MODEL_ID): EmbeddingPricing(input_usd_per_million_tokens=0.0),
    # USD per 1,000,000 input tokens, standard synchronous API, as published on
    # the official pricing and model pages (read 2026-11-02; no page date is
    # shown):
    #   https://developers.openai.com/api/docs/pricing
    #   https://developers.openai.com/api/docs/models/text-embedding-3-large
    # The Batch API discount is deliberately NOT applied: the worker is
    # synchronous. Published list price only; actual billing is the vendor's
    # and account-specific terms may differ.
    (OPENAI_PROVIDER_NAME, OPENAI_MODEL_ID): EmbeddingPricing(input_usd_per_million_tokens=0.13),
}


def lookup_pricing(*, provider: str, model_id: str) -> EmbeddingPricing | None:
    return _PRICING.get((provider, model_id))


def estimate_cost_usd(*, provider: str, model_id: str, input_tokens: int | None) -> float | None:
    """`None` when the model has no known price or usage is unknown."""
    pricing = lookup_pricing(provider=provider, model_id=model_id)
    if pricing is None or input_tokens is None:
        return None
    return input_tokens * pricing.input_usd_per_million_tokens / 1_000_000
