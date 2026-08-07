"""Repository for `issuer_enrichment_status` (PLAN.md Milestone 7.5 section 8).

See `provenance_repository.py`'s module docstring for this project's
repository conventions (function-style, domain objects only, flush-not-commit).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.types import EnrichmentStatus, ProviderName
from app.domain.enrichment_status import (
    IssuerEnrichmentStatus,
    IssuerEnrichmentStatusCreate,
    IssuerEnrichmentStatusUpdate,
)
from app.models.issuer_enrichment_status import IssuerEnrichmentStatus as StatusModel


def _to_domain(row: StatusModel) -> IssuerEnrichmentStatus:
    return IssuerEnrichmentStatus(
        id=row.id,
        issuer_id=row.issuer_id,
        provider=ProviderName(row.provider),
        status=EnrichmentStatus(row.status),
        last_attempt_at=row.last_attempt_at,
        last_success_at=row.last_success_at,
        next_retry_at=row.next_retry_at,
        attempt_count=row.attempt_count,
        records_found=row.records_found,
        error_classification=row.error_classification,
        checkpoint=row.checkpoint,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def get_status(
    db: Session, *, issuer_id: UUID, provider: ProviderName
) -> IssuerEnrichmentStatus | None:
    stmt = select(StatusModel).where(
        StatusModel.issuer_id == issuer_id, StatusModel.provider == provider.value
    )
    row = db.execute(stmt).scalars().first()
    return _to_domain(row) if row is not None else None


def list_statuses_for_issuer(db: Session, issuer_id: UUID) -> list[IssuerEnrichmentStatus]:
    stmt = select(StatusModel).where(StatusModel.issuer_id == issuer_id)
    rows = db.execute(stmt).scalars().all()
    return [_to_domain(row) for row in rows]


def get_or_create_pending(
    db: Session, data: IssuerEnrichmentStatusCreate
) -> IssuerEnrichmentStatus:
    """Idempotent by `(issuer_id, provider)` — a second call for the same
    pair returns the existing row unchanged rather than resetting it, so
    calling this to "make sure a row exists before deciding whether to run"
    never clobbers an in-flight or completed status.
    """
    existing = get_status(db, issuer_id=data.issuer_id, provider=data.provider)
    if existing is not None:
        return existing
    row = StatusModel(
        issuer_id=data.issuer_id,
        provider=data.provider.value,
        status=data.status.value,
        last_attempt_at=data.last_attempt_at,
        last_success_at=data.last_success_at,
        next_retry_at=data.next_retry_at,
        attempt_count=data.attempt_count,
        records_found=data.records_found,
        error_classification=data.error_classification,
        checkpoint=data.checkpoint,
    )
    db.add(row)
    db.flush()
    db.refresh(row)
    return _to_domain(row)


def record_attempt_outcome(
    db: Session, *, issuer_id: UUID, provider: ProviderName, update: IssuerEnrichmentStatusUpdate
) -> IssuerEnrichmentStatus:
    """Records the outcome of one enrichment attempt. Creates the row if
    none exists yet (first-ever attempt), otherwise updates it in place —
    `issuer_enrichment_status` always holds current state, never history
    (see `court_docket_link_attempt` for the per-attempt audit trail).
    """
    stmt = select(StatusModel).where(
        StatusModel.issuer_id == issuer_id, StatusModel.provider == provider.value
    )
    row = db.execute(stmt).scalars().first()
    if row is None:
        # `attempt_count`/`records_found` have DB-side `server_default`s
        # that only apply once flushed — set explicitly here so the
        # increment below (`row.attempt_count + 1`) never operates on a
        # Python-side `None` for a brand-new row.
        row = StatusModel(
            issuer_id=issuer_id,
            provider=provider.value,
            status=update.status.value,
            attempt_count=0,
            records_found=0,
        )
        db.add(row)

    row.status = update.status.value
    row.last_attempt_at = update.last_attempt_at
    if update.last_success_at is not None:
        row.last_success_at = update.last_success_at
    row.next_retry_at = update.next_retry_at
    row.attempt_count = row.attempt_count + 1
    if update.records_found is not None:
        row.records_found = update.records_found
    row.error_classification = update.error_classification
    if update.checkpoint is not None:
        row.checkpoint = update.checkpoint
    row.updated_at = datetime.now(tz=update.last_attempt_at.tzinfo)
    db.flush()
    db.refresh(row)
    return _to_domain(row)
