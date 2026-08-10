"""Repository for `ai_call_log` (PLAN.md Milestone 7.5.3).

See `provenance_repository.py`'s module docstring for this project's
repository conventions (function-style, domain objects only, flush-not-commit).
`aggregate_for_discovery_run` is the sole source for run-level AI usage
reporting — nothing duplicates these counts onto `market_discovery_run`
itself, so there is exactly one place that can drift from the truth.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.types import AiOperation, AiRoute
from app.domain.ai_call_log import AiCallLog, AiCallLogCreate, AiRunUsageSummary
from app.models.ai_call_log import AiCallLog as AiCallLogModel


def _to_domain(row: AiCallLogModel) -> AiCallLog:
    return AiCallLog(
        id=row.id,
        discovery_run_id=row.discovery_run_id,
        filing_monitor_run_id=row.filing_monitor_run_id,
        issuer_id=row.issuer_id,
        bundle_key=row.bundle_key,
        operation=AiOperation(row.operation),
        route=AiRoute(row.route),
        model=row.model,
        routing_reason=row.routing_reason,
        input_tokens=row.input_tokens,
        output_tokens=row.output_tokens,
        estimated_cost_usd=(
            float(row.estimated_cost_usd) if row.estimated_cost_usd is not None else None
        ),
        latency_ms=row.latency_ms,
        success=row.success,
        retry_count=row.retry_count,
        error_classification=row.error_classification,
        created_at=row.created_at,
    )


def create_call_log(db: Session, data: AiCallLogCreate) -> AiCallLog:
    row = AiCallLogModel(
        discovery_run_id=data.discovery_run_id,
        filing_monitor_run_id=data.filing_monitor_run_id,
        issuer_id=data.issuer_id,
        bundle_key=data.bundle_key,
        operation=data.operation.value,
        route=data.route.value,
        model=data.model,
        routing_reason=data.routing_reason,
        input_tokens=data.input_tokens,
        output_tokens=data.output_tokens,
        estimated_cost_usd=data.estimated_cost_usd,
        latency_ms=data.latency_ms,
        success=data.success,
        retry_count=data.retry_count,
        error_classification=data.error_classification,
    )
    db.add(row)
    db.flush()
    db.refresh(row)
    return _to_domain(row)


def _aggregate(rows: list[AiCallLogModel]) -> AiRunUsageSummary:
    cost_by_model: dict[str, float] = {}
    cost_by_operation: dict[str, float] = {}
    calls_by_model: dict[str, int] = {}
    calls_by_operation: dict[str, int] = {}
    total_input = 0
    total_output = 0
    total_cost = 0.0
    haiku_calls = 0
    sonnet_calls = 0
    failed_calls = 0
    total_retries = 0

    for row in rows:
        calls_by_model[row.model] = calls_by_model.get(row.model, 0) + 1
        calls_by_operation[row.operation] = calls_by_operation.get(row.operation, 0) + 1
        cost = float(row.estimated_cost_usd) if row.estimated_cost_usd is not None else 0.0
        cost_by_model[row.model] = cost_by_model.get(row.model, 0.0) + cost
        cost_by_operation[row.operation] = cost_by_operation.get(row.operation, 0.0) + cost
        total_cost += cost
        total_input += row.input_tokens or 0
        total_output += row.output_tokens or 0
        total_retries += row.retry_count
        if row.route == AiRoute.HAIKU.value:
            haiku_calls += 1
        elif row.route == AiRoute.SONNET.value:
            sonnet_calls += 1
        if not row.success:
            failed_calls += 1

    return AiRunUsageSummary(
        total_calls=len(rows),
        haiku_calls=haiku_calls,
        sonnet_calls=sonnet_calls,
        failed_calls=failed_calls,
        total_retries=total_retries,
        total_input_tokens=total_input,
        total_output_tokens=total_output,
        total_estimated_cost_usd=total_cost,
        cost_by_model=cost_by_model,
        cost_by_operation=cost_by_operation,
        calls_by_model=calls_by_model,
        calls_by_operation=calls_by_operation,
    )


def aggregate_for_discovery_run(db: Session, discovery_run_id: UUID) -> AiRunUsageSummary:
    rows = (
        db.execute(
            select(AiCallLogModel).where(AiCallLogModel.discovery_run_id == discovery_run_id)
        )
        .scalars()
        .all()
    )
    return _aggregate(list(rows))


def aggregate_for_filing_monitor_run(db: Session, filing_monitor_run_id: UUID) -> AiRunUsageSummary:
    rows = (
        db.execute(
            select(AiCallLogModel).where(
                AiCallLogModel.filing_monitor_run_id == filing_monitor_run_id
            )
        )
        .scalars()
        .all()
    )
    return _aggregate(list(rows))
