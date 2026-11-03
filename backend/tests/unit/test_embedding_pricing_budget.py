"""Unit tests for embedding cost estimation and the per-run budget
(`app.embeddings.pricing`, `.budget`, Milestone 10D.2). Unknown price must
stay unknown — never zero — and an unenforceable ceiling must refuse."""

from __future__ import annotations

import pytest

from app.embeddings.budget import EmbeddingRunBudget
from app.embeddings.pricing import estimate_cost_usd, lookup_pricing


def test_known_price_computes_cost_including_a_genuine_zero() -> None:
    assert estimate_cost_usd(provider="fake", model_id="fake-embedding", input_tokens=500) == 0.0


def test_unknown_model_cost_is_none_not_zero() -> None:
    assert lookup_pricing(provider="vendor-x", model_id="model-y") is None
    assert estimate_cost_usd(provider="vendor-x", model_id="model-y", input_tokens=500) is None


def test_unknown_usage_cost_is_none_not_zero() -> None:
    assert estimate_cost_usd(provider="fake", model_id="fake-embedding", input_tokens=None) is None


def test_budget_requires_a_positive_explicit_token_limit() -> None:
    with pytest.raises(ValueError):
        EmbeddingRunBudget(max_tokens=0)
    with pytest.raises(ValueError):
        EmbeddingRunBudget(max_tokens=10, max_cost_usd=-1.0)
    with pytest.raises(ValueError):
        EmbeddingRunBudget(max_tokens=10, max_requests=0)


def test_token_budget_blocks_the_call_that_would_exceed_it() -> None:
    budget = EmbeddingRunBudget(max_tokens=100)
    assert budget.check(estimated_tokens=100, estimated_cost_usd=None).allowed
    budget.record(tokens=60, cost_usd=None)
    decision = budget.check(estimated_tokens=41, estimated_cost_usd=None)
    assert not decision.allowed
    assert decision.reason == "token_budget_exhausted"
    assert budget.check(estimated_tokens=40, estimated_cost_usd=None).allowed


def test_request_limit_blocks_after_n_requests() -> None:
    budget = EmbeddingRunBudget(max_tokens=1000, max_requests=1)
    budget.record(tokens=1, cost_usd=None)
    decision = budget.check(estimated_tokens=1, estimated_cost_usd=None)
    assert (decision.allowed, decision.reason) == (False, "request_limit_reached")


def test_cost_ceiling_is_enforced_when_price_is_known() -> None:
    budget = EmbeddingRunBudget(max_tokens=1000, max_cost_usd=0.10)
    budget.record(tokens=10, cost_usd=0.08)
    assert not budget.check(estimated_tokens=1, estimated_cost_usd=0.05).allowed
    assert budget.check(estimated_tokens=1, estimated_cost_usd=0.02).allowed


def test_cost_ceiling_with_unknown_price_refuses_rather_than_spending_unmetered() -> None:
    budget = EmbeddingRunBudget(max_tokens=1000, max_cost_usd=1.0)
    decision = budget.check(estimated_tokens=1, estimated_cost_usd=None)
    assert (decision.allowed, decision.reason) == (
        False,
        "cost_ceiling_unenforceable_price_unknown",
    )


def test_no_cost_ceiling_means_unknown_price_is_allowed() -> None:
    budget = EmbeddingRunBudget(max_tokens=1000)
    assert budget.check(estimated_tokens=1, estimated_cost_usd=None).allowed
