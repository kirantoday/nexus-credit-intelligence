"""Canonical domain objects for `ai_call_log` (PLAN.md Milestone 7.5.3).

One row per real Anthropic API request — never per skipped/deterministic
decision (see `app.ai.model_router`'s docstring for why skips aren't
logged here). This is the sole source of truth for "how many AI calls did
this run make, on which model, at what cost" — `app.repositories.ai_call_log_repository`
aggregates it per `market_discovery_run`/`filing_monitor_run` for the
run-level usage summary PLAN.md Milestone 7.5.3 requires.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.core.types import AiOperation, AiRoute


class AiCallLogCreate(BaseModel):
    """Everything needed to record one completed (successful or failed)
    Anthropic API request."""

    model_config = ConfigDict(frozen=True)

    discovery_run_id: UUID | None = None
    filing_monitor_run_id: UUID | None = None
    issuer_id: UUID | None = None
    bundle_key: str | None = None
    operation: AiOperation
    route: AiRoute
    model: str
    routing_reason: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost_usd: float | None = None
    latency_ms: int | None = None
    success: bool
    retry_count: int = 0
    error_classification: str | None = None


class AiCallLog(AiCallLogCreate):
    """A persisted `ai_call_log` row."""

    id: UUID
    created_at: datetime


class AiRunUsageSummary(BaseModel):
    """Run-level AI usage aggregation (PLAN.md Milestone 7.5.3) — computed
    from `ai_call_log` at report time, never stored redundantly on the run
    row itself."""

    model_config = ConfigDict(frozen=True)

    total_calls: int
    haiku_calls: int
    sonnet_calls: int
    failed_calls: int
    total_retries: int
    total_input_tokens: int
    total_output_tokens: int
    total_estimated_cost_usd: float
    cost_by_model: dict[str, float]
    cost_by_operation: dict[str, float]
    calls_by_model: dict[str, int]
    calls_by_operation: dict[str, int]
