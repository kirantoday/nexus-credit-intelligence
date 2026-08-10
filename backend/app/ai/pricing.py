"""Explicitly maintained Anthropic model pricing (PLAN.md Milestone 7.5.3).

Cost is estimated, not billed truth — Anthropic's actual invoice is
authoritative. This table must be kept current by hand against
https://www.anthropic.com/pricing whenever a model id changes or Anthropic
revises rates; nothing here is fetched live. An unknown model id returns
`None` rather than a guessed number, so a stale table degrades to "cost
unknown" instead of a silently wrong dollar figure.

Rates are USD per token (not per million) to keep `estimate_cost_usd`'s
arithmetic a plain multiply — the constants below are written as
`X_PER_MILLION / 1_000_000` so the source-of-truth number (dollars per
million tokens, how Anthropic itself publishes pricing) stays the obviously
readable one.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ModelPricing:
    input_usd_per_million_tokens: float
    output_usd_per_million_tokens: float


# Standard (<=200K context) tier rates, USD per million tokens. Verify
# against Anthropic's pricing page before trusting this for real invoicing
# reconciliation — this is a cost *estimate* for run-level budgeting, not a
# billing system.
_MODEL_PRICING: dict[str, ModelPricing] = {
    "claude-haiku-4-5-20251001": ModelPricing(
        input_usd_per_million_tokens=1.00, output_usd_per_million_tokens=5.00
    ),
    "claude-haiku-4-5": ModelPricing(
        input_usd_per_million_tokens=1.00, output_usd_per_million_tokens=5.00
    ),
    "claude-sonnet-5": ModelPricing(
        input_usd_per_million_tokens=3.00, output_usd_per_million_tokens=15.00
    ),
}


def estimate_cost_usd(
    *, model: str, input_tokens: int | None, output_tokens: int | None
) -> float | None:
    """`None` when the model isn't in the pricing table or either token
    count is unknown — callers must not treat that as zero cost."""
    pricing = _MODEL_PRICING.get(model)
    if pricing is None or input_tokens is None or output_tokens is None:
        return None
    return (
        input_tokens * pricing.input_usd_per_million_tokens / 1_000_000
        + output_tokens * pricing.output_usd_per_million_tokens / 1_000_000
    )
