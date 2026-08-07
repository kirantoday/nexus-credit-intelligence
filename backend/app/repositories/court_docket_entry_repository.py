"""Repository for `court_docket_entry` (PLAN.md section 4.5, Milestone 7).

See `provenance_repository.py`'s module docstring for this project's
repository conventions (function-style, domain objects only, flush-not-commit).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.court_docket_entry import CourtDocketEntry, CourtDocketEntryCreate
from app.models.court_docket_entry import CourtDocketEntry as CourtDocketEntryModel


def _to_domain(row: CourtDocketEntryModel) -> CourtDocketEntry:
    return CourtDocketEntry(
        id=row.id,
        docket_id=row.docket_id,
        courtlistener_entry_id=row.courtlistener_entry_id,
        entry_number=row.entry_number,
        entry_date=row.entry_date,
        description=row.description,
        document_available=row.document_available,
        provenance_id=row.provenance_id,
        created_at=row.created_at,
    )


def get_entry(db: Session, entry_id: UUID) -> CourtDocketEntry | None:
    row = db.get(CourtDocketEntryModel, entry_id)
    return _to_domain(row) if row is not None else None


def get_entry_by_courtlistener_id(
    db: Session, courtlistener_entry_id: int
) -> CourtDocketEntry | None:
    stmt = select(CourtDocketEntryModel).where(
        CourtDocketEntryModel.courtlistener_entry_id == courtlistener_entry_id
    )
    row = db.execute(stmt).scalars().first()
    return _to_domain(row) if row is not None else None


def create_entry(db: Session, data: CourtDocketEntryCreate) -> tuple[CourtDocketEntry, bool]:
    """Get-or-create by `courtlistener_entry_id` — the idempotency guard a
    re-run of the docket sync relies on. Returns (entry, created)."""
    existing = get_entry_by_courtlistener_id(db, data.courtlistener_entry_id)
    if existing is not None:
        return existing, False

    row = CourtDocketEntryModel(
        docket_id=data.docket_id,
        courtlistener_entry_id=data.courtlistener_entry_id,
        entry_number=data.entry_number,
        entry_date=data.entry_date,
        description=data.description,
        document_available=data.document_available,
        provenance_id=data.provenance_id,
    )
    db.add(row)
    db.flush()
    db.refresh(row)
    return _to_domain(row), True


def get_max_courtlistener_entry_id(db: Session, docket_id: UUID) -> int | None:
    """The TD-012 incremental-sync cursor (PLAN.md Milestone 7.5): CourtListener's
    own `id` field (our `courtlistener_entry_id`) is a globally
    monotonically-increasing identifier assigned at entry creation (live-
    verified via a real `OPTIONS` request confirming `id` supports
    `gt`/`gte` filters and `order_by=id`) — a strictly cheaper and more
    exact incremental cursor than a date-based watermark, since it needs no
    overlap margin: `id__gt=<this value>` can never re-fetch or skip an
    entry. `None` means this docket has never been synced (or has zero
    entries), so the caller falls back to the original full-pagination
    walk.
    """
    stmt = select(func.max(CourtDocketEntryModel.courtlistener_entry_id)).where(
        CourtDocketEntryModel.docket_id == docket_id
    )
    return db.execute(stmt).scalar_one_or_none()


def list_entries_by_docket(db: Session, docket_id: UUID) -> list[CourtDocketEntry]:
    stmt = (
        select(CourtDocketEntryModel)
        .where(CourtDocketEntryModel.docket_id == docket_id)
        .order_by(CourtDocketEntryModel.entry_date.asc(), CourtDocketEntryModel.created_at.asc())
    )
    rows = db.execute(stmt).scalars().all()
    return [_to_domain(row) for row in rows]


def count_entries_created_since(db: Session, since: datetime | None) -> int:
    """Counts by `created_at` (when Nexus ingested the entry), not
    `entry_date` (the real-world docket event date) — see
    `sec_filing_repository.count_filings_created_since` for the same
    discovery-time-vs-event-time distinction, applied here for the Morning
    Research Brief's "New Court Events" metric."""
    stmt = select(func.count()).select_from(CourtDocketEntryModel)
    if since is not None:
        stmt = stmt.where(CourtDocketEntryModel.created_at >= since)
    return db.execute(stmt).scalar_one()
