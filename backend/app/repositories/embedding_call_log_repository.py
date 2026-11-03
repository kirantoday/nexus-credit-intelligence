"""Repository for `embedding_call_log` (Milestone 10D.2).

Function-style, flush-not-commit. `aggregate_for_job` is the single source
for per-job spend; nothing duplicates these totals onto the job row.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.types import EmbeddingInputType
from app.domain.embedding_call_log import (
    EmbeddingCallLog,
    EmbeddingCallLogCreate,
    EmbeddingJobUsageSummary,
)
from app.models.embedding_call_log import EmbeddingCallLog as EmbeddingCallLogModel


def _to_domain(row: EmbeddingCallLogModel) -> EmbeddingCallLog:
    return EmbeddingCallLog(
        id=row.id,
        job_id=row.job_id,
        purpose=EmbeddingInputType(row.purpose),
        provider=row.provider,
        model=row.model,
        model_version=row.model_version,
        batch_size=row.batch_size,
        input_tokens=row.input_tokens,
        estimated_cost_usd=(
            float(row.estimated_cost_usd) if row.estimated_cost_usd is not None else None
        ),
        latency_ms=row.latency_ms,
        success=row.success,
        retry_count=row.retry_count,
        error_classification=row.error_classification,
        created_at=row.created_at,
    )


def create_call_log(db: Session, data: EmbeddingCallLogCreate) -> EmbeddingCallLog:
    row = EmbeddingCallLogModel(
        job_id=data.job_id,
        purpose=data.purpose.value,
        provider=data.provider,
        model=data.model,
        model_version=data.model_version,
        batch_size=data.batch_size,
        input_tokens=data.input_tokens,
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


def aggregate_for_job(db: Session, job_id: uuid.UUID) -> EmbeddingJobUsageSummary:
    rows = list(
        db.execute(select(EmbeddingCallLogModel).where(EmbeddingCallLogModel.job_id == job_id))
        .scalars()
        .all()
    )
    # Only successful calls are billed, so only they can make the total
    # unknown; a failed call with no cost recorded does not.
    total_cost: float | None = 0.0
    for row in rows:
        if not row.success:
            continue
        if row.estimated_cost_usd is None:
            total_cost = None
            break
        assert total_cost is not None
        total_cost += float(row.estimated_cost_usd)
    return EmbeddingJobUsageSummary(
        total_calls=len(rows),
        failed_calls=sum(1 for row in rows if not row.success),
        total_input_tokens=sum(row.input_tokens or 0 for row in rows),
        calls_with_unknown_tokens=sum(1 for row in rows if row.input_tokens is None),
        total_estimated_cost_usd=total_cost,
    )
