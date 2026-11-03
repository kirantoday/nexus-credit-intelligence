"""Repository for `document_embedding_job` (Milestone 10D.2).

Function-style, domain objects only, flush-not-commit. The claim and
stale-reclaim queries use `SELECT ... FOR UPDATE SKIP LOCKED` exactly like
`document_extraction_repository` (the only other users of it in this
codebase), for the same reason: a second worker skips a row the first
already holds rather than blocking or double-processing it.

Error messages stored here are content-free by contract (see
`app.embeddings.errors.safe_summary`); this module never formats an
exception itself.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.types import EmbeddingJobStatus
from app.domain.document_embedding_job import DocumentEmbeddingJob, DocumentEmbeddingJobCreate
from app.models.document_embedding_job import DocumentEmbeddingJob as JobModel

_ACTIVE = (EmbeddingJobStatus.PENDING.value, EmbeddingJobStatus.PROCESSING.value)


def _to_domain(row: JobModel) -> DocumentEmbeddingJob:
    return DocumentEmbeddingJob(
        id=row.id,
        research_document_id=row.research_document_id,
        document_extraction_id=row.document_extraction_id,
        embedding_provider=row.embedding_provider,
        embedding_model=row.embedding_model,
        embedding_model_version=row.embedding_model_version,
        dimension=row.dimension,
        status=EmbeddingJobStatus(row.status),
        attempt_count=row.attempt_count,
        error_classification=row.error_classification,
        error_message=row.error_message,
        status_note=row.status_note,
        chunk_total=row.chunk_total,
        chunks_embedded=row.chunks_embedded,
        chunks_replaced=row.chunks_replaced,
        provenance_id=row.provenance_id,
        requested_by=row.requested_by,
        started_at=row.started_at,
        completed_at=row.completed_at,
        created_at=row.created_at,
    )


def _get_row(db: Session, job_id: uuid.UUID) -> JobModel:
    row = db.get(JobModel, job_id)
    assert row is not None, f"document_embedding_job {job_id} not found"
    return row


def create_pending(db: Session, data: DocumentEmbeddingJobCreate) -> DocumentEmbeddingJob:
    row = JobModel(
        research_document_id=data.research_document_id,
        document_extraction_id=data.document_extraction_id,
        embedding_provider=data.embedding_provider,
        embedding_model=data.embedding_model,
        embedding_model_version=data.embedding_model_version,
        dimension=data.dimension,
        status=EmbeddingJobStatus.PENDING.value,
        requested_by=data.requested_by,
    )
    db.add(row)
    db.flush()
    db.refresh(row)
    return _to_domain(row)


def get_job(db: Session, job_id: uuid.UUID) -> DocumentEmbeddingJob | None:
    row = db.get(JobModel, job_id)
    return _to_domain(row) if row is not None else None


def get_active_job(
    db: Session, *, document_extraction_id: uuid.UUID, embedding_model: str, model_version: str
) -> DocumentEmbeddingJob | None:
    stmt = select(JobModel).where(
        JobModel.document_extraction_id == document_extraction_id,
        JobModel.embedding_model == embedding_model,
        JobModel.embedding_model_version == model_version,
        JobModel.status.in_(_ACTIVE),
    )
    row = db.execute(stmt).scalars().first()
    return _to_domain(row) if row is not None else None


def claim_next_pending(db: Session) -> DocumentEmbeddingJob | None:
    """Atomically moves the oldest `pending` job to `processing` and counts
    the attempt. Caller commits (or rolls back) to release the row lock."""
    stmt = (
        select(JobModel)
        .where(JobModel.status == EmbeddingJobStatus.PENDING.value)
        .order_by(JobModel.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    row = db.execute(stmt).scalars().first()
    if row is None:
        return None
    row.status = EmbeddingJobStatus.PROCESSING.value
    row.started_at = datetime.now(UTC)
    row.attempt_count += 1
    db.flush()
    db.refresh(row)
    return _to_domain(row)


def reclaim_stale_processing(
    db: Session, *, stale_after: datetime, max_attempts: int
) -> list[DocumentEmbeddingJob]:
    """`processing` rows older than `stale_after` belong to a worker that
    died mid-attempt: reset to `pending`, unless the attempt budget is
    already spent, in which case they are failed rather than retried
    forever."""
    stmt = (
        select(JobModel)
        .where(
            JobModel.status == EmbeddingJobStatus.PROCESSING.value,
            JobModel.started_at < stale_after,
        )
        .with_for_update(skip_locked=True)
    )
    rows = list(db.execute(stmt).scalars().all())
    for row in rows:
        if row.attempt_count >= max_attempts:
            row.status = EmbeddingJobStatus.FAILED.value
            row.error_classification = "transient"
            row.error_message = f"stale processing job exceeded max_attempts={max_attempts}"
            row.completed_at = datetime.now(UTC)
        else:
            row.status = EmbeddingJobStatus.PENDING.value
            row.started_at = None
            row.status_note = "reclaimed_stale_processing"
    db.flush()
    for row in rows:
        db.refresh(row)
    return [_to_domain(row) for row in rows]


def requeue_pending(
    db: Session,
    job_id: uuid.UUID,
    *,
    error_classification: str | None,
    error_message: str | None,
    note: str,
    refund_attempt: bool,
) -> DocumentEmbeddingJob:
    """Back to `pending`. `refund_attempt` returns the attempt the claim
    consumed, for stops that are not this job's fault (budget exhausted,
    provider credentials/configuration)."""
    row = _get_row(db, job_id)
    row.status = EmbeddingJobStatus.PENDING.value
    row.started_at = None
    row.error_classification = error_classification
    row.error_message = error_message
    row.status_note = note
    if refund_attempt and row.attempt_count > 0:
        row.attempt_count -= 1
    db.flush()
    db.refresh(row)
    return _to_domain(row)


def mark_completed(db: Session, job_id: uuid.UUID, *, chunk_total: int) -> DocumentEmbeddingJob:
    row = _get_row(db, job_id)
    row.status = EmbeddingJobStatus.COMPLETED.value
    row.chunk_total = chunk_total
    row.error_classification = None
    row.error_message = None
    row.status_note = None
    row.completed_at = datetime.now(UTC)
    db.flush()
    db.refresh(row)
    return _to_domain(row)


def mark_failed(
    db: Session, job_id: uuid.UUID, *, error_classification: str, error_message: str
) -> DocumentEmbeddingJob:
    row = _get_row(db, job_id)
    row.status = EmbeddingJobStatus.FAILED.value
    row.error_classification = error_classification
    row.error_message = error_message
    row.completed_at = datetime.now(UTC)
    db.flush()
    db.refresh(row)
    return _to_domain(row)


def mark_blocked(db: Session, job_id: uuid.UUID, *, reason: str) -> DocumentEmbeddingJob:
    row = _get_row(db, job_id)
    row.status = EmbeddingJobStatus.BLOCKED_INELIGIBLE.value
    row.status_note = reason
    row.completed_at = datetime.now(UTC)
    db.flush()
    db.refresh(row)
    return _to_domain(row)


def add_progress(
    db: Session, job_id: uuid.UUID, *, embedded: int, replaced: int
) -> DocumentEmbeddingJob:
    """Cumulative counters, incremented in the same transaction as the
    batch of embeddings they describe."""
    row = _get_row(db, job_id)
    row.chunks_embedded += embedded
    row.chunks_replaced += replaced
    db.flush()
    db.refresh(row)
    return _to_domain(row)


def set_provenance_if_unset(db: Session, job_id: uuid.UUID, provenance_id: uuid.UUID) -> uuid.UUID:
    """Compare-and-set: the first writer wins and every later caller gets
    the winning id back, so two concurrent batches can never leave one job
    with two provenance records."""
    db.execute(
        update(JobModel)
        .where(JobModel.id == job_id, JobModel.provenance_id.is_(None))
        .values(provenance_id=provenance_id)
    )
    db.flush()
    row = _get_row(db, job_id)
    db.refresh(row)
    assert row.provenance_id is not None
    return row.provenance_id
