"""Repository for `document_extraction` (Milestone 10C).

Function-style, domain objects only, flush-not-commit — see
`provenance_repository.py`'s module docstring for this project's
repository conventions.

`claim_next_pending`/`reclaim_stale_processing` are the only two functions
in this codebase that use `SELECT ... FOR UPDATE SKIP LOCKED` — Postgres's
standard mechanism for safe concurrent job claiming: a second worker
attempting to claim the same row a first worker already holds a row lock
on skips it entirely rather than blocking, so even though 10C's worker
runs one-at-a-time, the claim mechanism itself is safe if a second worker
process ever exists (per the milestone brief's explicit requirement).

`promote_current` demotes any existing current extraction for the same
`research_document_id` *before* promoting the new one, both within the
caller's transaction (flush, not commit) — this ordering, combined with
`ux_document_extraction_one_current_per_document`'s non-deferred partial
unique index, means Postgres never observes two current rows for the same
document at once, not even transiently.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.types import (
    DocumentExtractionErrorClass,
    DocumentExtractionSourceType,
    DocumentExtractionStatus,
)
from app.domain.document_extraction import DocumentExtraction, DocumentExtractionCreate
from app.models.document_extraction import DocumentExtraction as DocumentExtractionModel


def _to_domain(row: DocumentExtractionModel) -> DocumentExtraction:
    return DocumentExtraction(
        id=row.id,
        source_type=DocumentExtractionSourceType(row.source_type),
        research_document_id=row.research_document_id,
        status=DocumentExtractionStatus(row.status),
        extractor_provider=row.extractor_provider,
        extractor_version=row.extractor_version,
        chunking_strategy_version=row.chunking_strategy_version,
        structured_artifact_storage_key=row.structured_artifact_storage_key,
        page_count=row.page_count,
        chunk_count=row.chunk_count,
        table_count=row.table_count,
        attempt_count=row.attempt_count,
        error_classification=row.error_classification,
        error_message=row.error_message,
        started_at=row.started_at,
        completed_at=row.completed_at,
        created_at=row.created_at,
        is_current=row.is_current,
    )


def create_pending(db: Session, data: DocumentExtractionCreate) -> DocumentExtraction:
    row = DocumentExtractionModel(
        source_type=data.source_type.value,
        research_document_id=data.research_document_id,
        status=DocumentExtractionStatus.PENDING.value,
    )
    db.add(row)
    db.flush()
    db.refresh(row)
    return _to_domain(row)


def get_extraction(db: Session, extraction_id: uuid.UUID) -> DocumentExtraction | None:
    row = db.get(DocumentExtractionModel, extraction_id)
    return _to_domain(row) if row is not None else None


def get_current_for_document(
    db: Session, research_document_id: uuid.UUID
) -> DocumentExtraction | None:
    stmt = select(DocumentExtractionModel).where(
        DocumentExtractionModel.research_document_id == research_document_id,
        DocumentExtractionModel.is_current.is_(True),
    )
    row = db.execute(stmt).scalars().first()
    return _to_domain(row) if row is not None else None


def list_for_document(db: Session, research_document_id: uuid.UUID) -> list[DocumentExtraction]:
    stmt = (
        select(DocumentExtractionModel)
        .where(DocumentExtractionModel.research_document_id == research_document_id)
        .order_by(DocumentExtractionModel.created_at.desc())
    )
    rows = db.execute(stmt).scalars().all()
    return [_to_domain(row) for row in rows]


def claim_next_pending(db: Session) -> DocumentExtraction | None:
    """Atomically claims (transitions `pending` -> `processing`) the
    oldest pending extraction, or `None` if none exists. Caller commits
    (or rolls back) to release the row lock — this function only flushes.
    """
    stmt = (
        select(DocumentExtractionModel)
        .where(DocumentExtractionModel.status == DocumentExtractionStatus.PENDING.value)
        .order_by(DocumentExtractionModel.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    row = db.execute(stmt).scalars().first()
    if row is None:
        return None
    row.status = DocumentExtractionStatus.PROCESSING.value
    row.started_at = datetime.now(UTC)
    row.attempt_count += 1
    db.flush()
    db.refresh(row)
    return _to_domain(row)


def reclaim_stale_processing(
    db: Session, *, stale_after: datetime, max_attempts: int
) -> list[DocumentExtraction]:
    """Rows stuck at `processing` since before `stale_after` (a worker
    died mid-attempt) are reset to `pending` for another attempt, unless
    `attempt_count` has already reached `max_attempts` — those are marked
    `failed` instead of retried forever. `FOR UPDATE SKIP LOCKED` for the
    same reason `claim_next_pending` uses it: safe if a second recovery
    pass or worker is ever running concurrently.
    """
    stmt = (
        select(DocumentExtractionModel)
        .where(
            DocumentExtractionModel.status == DocumentExtractionStatus.PROCESSING.value,
            DocumentExtractionModel.started_at < stale_after,
        )
        .with_for_update(skip_locked=True)
    )
    rows = db.execute(stmt).scalars().all()
    recovered: list[DocumentExtractionModel] = []
    for row in rows:
        if row.attempt_count >= max_attempts:
            row.status = DocumentExtractionStatus.FAILED.value
            row.error_classification = "transient"
            row.error_message = (
                f"stale processing job exceeded max_attempts={max_attempts} "
                "(worker likely died mid-attempt); not retried further"
            )
            row.completed_at = datetime.now(UTC)
        else:
            row.status = DocumentExtractionStatus.PENDING.value
            row.started_at = None
        recovered.append(row)
    db.flush()
    for row in recovered:
        db.refresh(row)
    return [_to_domain(row) for row in recovered]


def mark_completed(
    db: Session,
    extraction_id: uuid.UUID,
    *,
    extractor_provider: str,
    extractor_version: str,
    chunking_strategy_version: str,
    structured_artifact_storage_key: str,
    page_count: int,
    chunk_count: int,
    table_count: int,
) -> DocumentExtraction:
    row = db.get(DocumentExtractionModel, extraction_id)
    assert row is not None
    row.status = DocumentExtractionStatus.COMPLETED.value
    row.extractor_provider = extractor_provider
    row.extractor_version = extractor_version
    row.chunking_strategy_version = chunking_strategy_version
    row.structured_artifact_storage_key = structured_artifact_storage_key
    row.page_count = page_count
    row.chunk_count = chunk_count
    row.table_count = table_count
    row.completed_at = datetime.now(UTC)
    row.error_classification = None
    row.error_message = None
    db.flush()
    db.refresh(row)
    return _to_domain(row)


def mark_needs_ocr(
    db: Session,
    extraction_id: uuid.UUID,
    *,
    extractor_provider: str,
    extractor_version: str,
    page_count: int,
) -> DocumentExtraction:
    row = db.get(DocumentExtractionModel, extraction_id)
    assert row is not None
    row.status = DocumentExtractionStatus.NEEDS_OCR.value
    row.extractor_provider = extractor_provider
    row.extractor_version = extractor_version
    row.page_count = page_count
    row.completed_at = datetime.now(UTC)
    row.error_classification = None
    row.error_message = (
        "Nexus detected that this document appears to require OCR "
        "(near-zero extractable text relative to page count). OCR "
        "processing is not enabled yet."
    )
    db.flush()
    db.refresh(row)
    return _to_domain(row)


def requeue_pending(
    db: Session, extraction_id: uuid.UUID, *, error_message: str
) -> DocumentExtraction:
    """A transient failure (Storage/network) with retry budget remaining
    goes back to `pending` — not `failed` — so a future worker invocation
    picks it up again via the normal claim query. `attempt_count` is left
    untouched here (already incremented by `claim_next_pending` for the
    attempt that just failed); the caller compares it against
    `MAX_EXTRACTION_ATTEMPTS` *before* calling this, never blindly."""
    row = db.get(DocumentExtractionModel, extraction_id)
    assert row is not None
    row.status = DocumentExtractionStatus.PENDING.value
    row.started_at = None
    row.error_classification = DocumentExtractionErrorClass.TRANSIENT.value
    row.error_message = error_message
    db.flush()
    db.refresh(row)
    return _to_domain(row)


def mark_failed(
    db: Session,
    extraction_id: uuid.UUID,
    *,
    error_classification: str,
    error_message: str,
) -> DocumentExtraction:
    row = db.get(DocumentExtractionModel, extraction_id)
    assert row is not None
    row.status = DocumentExtractionStatus.FAILED.value
    row.error_classification = error_classification
    row.error_message = error_message
    row.completed_at = datetime.now(UTC)
    db.flush()
    db.refresh(row)
    return _to_domain(row)


def promote_current(
    db: Session, extraction_id: uuid.UUID, *, research_document_id: uuid.UUID
) -> DocumentExtraction:
    """Demotes any existing current extraction for `research_document_id`
    first, then promotes `extraction_id` — both in this flush, so the
    partial unique index never observes two current rows at once. The
    caller (`document_extraction_service`) is responsible for only calling
    this once `extraction_id`'s row is already `status=completed` (the
    `ck_document_extraction_current_requires_completed` CHECK constraint
    enforces this at the database level too, defense-in-depth)."""
    existing_current = (
        db.execute(
            select(DocumentExtractionModel).where(
                DocumentExtractionModel.research_document_id == research_document_id,
                DocumentExtractionModel.is_current.is_(True),
                DocumentExtractionModel.id != extraction_id,
            )
        )
        .scalars()
        .all()
    )
    for row in existing_current:
        row.is_current = False
    db.flush()

    new_current = db.get(DocumentExtractionModel, extraction_id)
    assert new_current is not None
    new_current.is_current = True
    db.flush()
    db.refresh(new_current)
    return _to_domain(new_current)
