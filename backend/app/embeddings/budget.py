"""Per-run embedding budget (Milestone 10D.2).

Same idea as `app.ai.model_router.AiCallBudget`, scoped to embeddings: one
mutable tracker per worker invocation, checked immediately before every
provider call. A budget stop is **never a job failure** — the processor
requeues the job so a later run with fresh budget resumes it.

Fail-closed rule: if a cost ceiling is configured but the model's price is
unknown, the ceiling cannot be enforced, so the call is refused rather than
allowed to spend unmetered.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class BudgetDecision:
    allowed: bool
    reason: str


@dataclass(slots=True)
class EmbeddingRunBudget:
    max_tokens: int
    max_cost_usd: float | None = None
    max_requests: int | None = None

    tokens_used: int = field(default=0, init=False)
    cost_used_usd: float = field(default=0.0, init=False)
    requests_made: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        if self.max_tokens <= 0:
            raise ValueError("max_tokens must be a positive explicit budget")
        if self.max_cost_usd is not None and self.max_cost_usd < 0:
            raise ValueError("max_cost_usd must not be negative")
        if self.max_requests is not None and self.max_requests <= 0:
            raise ValueError("max_requests must be positive when set")

    def check(self, *, estimated_tokens: int, estimated_cost_usd: float | None) -> BudgetDecision:
        if self.max_requests is not None and self.requests_made >= self.max_requests:
            return BudgetDecision(False, "request_limit_reached")
        if self.tokens_used + estimated_tokens > self.max_tokens:
            return BudgetDecision(False, "token_budget_exhausted")
        if self.max_cost_usd is not None:
            if estimated_cost_usd is None:
                return BudgetDecision(False, "cost_ceiling_unenforceable_price_unknown")
            if self.cost_used_usd + estimated_cost_usd > self.max_cost_usd:
                return BudgetDecision(False, "cost_budget_exhausted")
        return BudgetDecision(True, "ok")

    def record(self, *, tokens: int, cost_usd: float | None) -> None:
        self.requests_made += 1
        self.tokens_used += tokens
        if cost_usd is not None:
            self.cost_used_usd += cost_usd
