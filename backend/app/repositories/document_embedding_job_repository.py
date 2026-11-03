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

from sqlalchemy import Select, and_, or_, select, update
from sqlalchemy.orm import Session, aliased

from app.core.types import EmbeddingJobStatus
from app.domain.document_embedding_job import DocumentEmbeddingJob, DocumentEmbeddingJobCreate
from app.embeddings.scheduling import ensure_utc
from app.models.document_embedding_job import DocumentEmbeddingJob as JobModel

# `held` counts as active: a held job still owns its (extraction, model,
# version) slot, so re-enqueueing cannot create a second job that would
# bypass the operator hold.
_ACTIVE = (
    EmbeddingJobStatus.PENDING.value,
    EmbeddingJobStatus.PROCESSING.value,
    EmbeddingJobStatus.HELD.value,
)


class JobNotHeldError(Exception):
    """Release was requested for a job that is not currently `held`."""


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
        retry_not_before=row.retry_not_before,
        provider_wide=row.provider_wide,
        hold_reason=row.hold_reason,
        held_at=row.held_at,
        released_at=row.released_at,
        released_by=row.released_by,
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


def _claim_statement(
    *, provider: str, model: str, model_version: str, now: datetime
) -> Select[tuple[JobModel]]:
    """The claim query. It must stay equivalent to
    `app.embeddings.scheduling.claimable_jobs` (the executable specification);
    only the future integration tests can show the database agrees.

    A job is claimable when it is `pending`, belongs to this worker's
    provider/model/version, is due (`retry_not_before` NULL or <= now), and no
    provider-wide job for the same provider/model is held or still delayed.
    `now` is passed in (UTC-aware) rather than read from the database clock so
    the boundary is testable; with the single-worker lock there is one clock.
    """
    now = ensure_utc(now)
    blocker = aliased(JobModel)
    queue_blocked = (
        select(blocker.id)
        .where(
            blocker.embedding_provider == provider,
            blocker.embedding_model == model,
            blocker.provider_wide.is_(True),
            or_(
                blocker.status == EmbeddingJobStatus.HELD.value,
                and_(
                    blocker.status == EmbeddingJobStatus.PENDING.value,
                    blocker.retry_not_before.is_not(None),
                    blocker.retry_not_before > now,
                ),
            ),
        )
        .exists()
    )
    return (
        select(JobModel)
        .where(
            JobModel.status == EmbeddingJobStatus.PENDING.value,
            JobModel.embedding_provider == provider,
            JobModel.embedding_model == model,
            JobModel.embedding_model_version == model_version,
            or_(JobModel.retry_not_before.is_(None), JobModel.retry_not_before <= now),
            ~queue_blocked,
        )
        .order_by(JobModel.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )


def claim_next_pending(
    db: Session,
    *,
    provider: str,
    model: str,
    model_version: str,
    now: datetime | None = None,
) -> DocumentEmbeddingJob | None:
    """Atomically moves the oldest *due* `pending` job for this worker's
    provider/model/version to `processing` and counts the attempt. A job
    behind a provider-wide delay or hold is not returned. The delay fields are
    cleared on claim: a processing job has no pending schedule. Caller commits
    (or rolls back) to release the row lock; no lock is held over a provider
    call."""
    moment = ensure_utc(now) if now is not None else datetime.now(UTC)
    row = (
        db.execute(
            _claim_statement(
                provider=provider, model=model, model_version=model_version, now=moment
            )
        )
        .scalars()
        .first()
    )
    if row is None:
        return None
    row.status = EmbeddingJobStatus.PROCESSING.value
    row.started_at = moment
    row.retry_not_before = None
    row.provider_wide = False
    row.attempt_count += 1
    db.flush()
    db.refresh(row)
    return _to_domain(row)


def reclaim_stale_processing(
    db: Session,
    *,
    stale_after: datetime,
    max_attempts: int,
    retry_not_before: datetime | None = None,
) -> list[DocumentEmbeddingJob]:
    """`processing` rows older than `stale_after` belong to a worker that
    died mid-attempt: reset to `pending` (delayed until `retry_not_before`
    when given), unless the attempt budget is already spent, in which case
    they are failed rather than retried forever. `held` rows are never
    touched (they are not `processing`). The dead worker may already have sent
    a request: re-processing is at-least-once and can be billed twice."""
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
            row.provider_wide = False
            row.retry_not_before = (
                ensure_utc(retry_not_before) if retry_not_before is not None else None
            )
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
    retry_not_before: datetime | None = None,
    provider_wide: bool = False,
) -> DocumentEmbeddingJob:
    """Back to `pending`. `refund_attempt` returns the attempt the claim
    consumed, for stops that are not this job's fault (a budget stop).
    `retry_not_before` (UTC-aware) delays the next claim; `provider_wide`
    extends that delay to the provider/model queue."""
    row = _get_row(db, job_id)
    row.status = EmbeddingJobStatus.PENDING.value
    row.started_at = None
    row.error_classification = error_classification
    row.error_message = error_message
    row.status_note = note
    row.retry_not_before = ensure_utc(retry_not_before) if retry_not_before is not None else None
    row.provider_wide = provider_wide and retry_not_before is not None
    if refund_attempt and row.attempt_count > 0:
        row.attempt_count -= 1
    db.flush()
    db.refresh(row)
    return _to_domain(row)


def hold_job(
    db: Session,
    job_id: uuid.UUID,
    *,
    reason: str,
    provider_wide: bool,
    error_classification: str | None,
    error_message: str | None,
    refund_attempt: bool,
    now: datetime | None = None,
) -> DocumentEmbeddingJob:
    """Operator hold: `held` is never claimable and never touched by stale
    recovery; only `release_held` leaves it. `refund_attempt` is for conditions
    that are not this job's fault (credentials, quota, configuration); each
    request that failed is still in `embedding_call_log`."""
    moment = ensure_utc(now) if now is not None else datetime.now(UTC)
    row = _get_row(db, job_id)
    row.status = EmbeddingJobStatus.HELD.value
    row.started_at = None
    row.retry_not_before = None
    row.provider_wide = provider_wide
    row.hold_reason = reason
    row.held_at = moment
    row.error_classification = error_classification
    row.error_message = error_message
    row.status_note = f"held:{reason}"
    if refund_attempt and row.attempt_count > 0:
        row.attempt_count -= 1
    db.flush()
    db.refresh(row)
    return _to_domain(row)


def release_held(
    db: Session, job_id: uuid.UUID, *, released_by: str, now: datetime | None = None
) -> DocumentEmbeddingJob:
    """Explicit operator release: `held` -> `pending`, claimable at once.
    Sends no request. Lifetime evidence is kept: attempt count, error fields,
    `hold_reason` and `held_at` are not cleared; `released_at`/`released_by`
    record the action (`released_by` is an asserted, unverified name). A
    provider-wide hold stops blocking the queue only when every provider-wide
    held job has been released."""
    moment = ensure_utc(now) if now is not None else datetime.now(UTC)
    row = _get_row(db, job_id)
    if row.status != EmbeddingJobStatus.HELD.value:
        raise JobNotHeldError(f"document_embedding_job {job_id} is not held")
    row.status = EmbeddingJobStatus.PENDING.value
    row.retry_not_before = None
    row.provider_wide = False
    row.released_at = moment
    row.released_by = released_by
    row.status_note = "released_from_hold"
    db.flush()
    db.refresh(row)
    return _to_domain(row)


def list_held(db: Session) -> list[DocumentEmbeddingJob]:
    stmt = (
        select(JobModel)
        .where(JobModel.status == EmbeddingJobStatus.HELD.value)
        .order_by(JobModel.held_at)
    )
    return [_to_domain(row) for row in db.execute(stmt).scalars().all()]


def _clear_schedule(row: JobModel) -> None:
    row.retry_not_before = None
    row.provider_wide = False


def mark_completed(db: Session, job_id: uuid.UUID, *, chunk_total: int) -> DocumentEmbeddingJob:
    row = _get_row(db, job_id)
    _clear_schedule(row)
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
    _clear_schedule(row)
    row.status = EmbeddingJobStatus.FAILED.value
    row.error_classification = error_classification
    row.error_message = error_message
    row.completed_at = datetime.now(UTC)
    db.flush()
    db.refresh(row)
    return _to_domain(row)


def mark_blocked(db: Session, job_id: uuid.UUID, *, reason: str) -> DocumentEmbeddingJob:
    row = _get_row(db, job_id)
    _clear_schedule(row)
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
