"""Repository for `court_docket_entry` (PLAN.md section 4.5, Milestone 7).

See `provenance_repository.py`'s module docstring for this project's
repository conventions (function-style, domain objects only, flush-not-commit).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
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


def list_entries_by_docket(db: Session, docket_id: UUID) -> list[CourtDocketEntry]:
    stmt = (
        select(CourtDocketEntryModel)
        .where(CourtDocketEntryModel.docket_id == docket_id)
        .order_by(CourtDocketEntryModel.entry_date.asc(), CourtDocketEntryModel.created_at.asc())
    )
    rows = db.execute(stmt).scalars().all()
    return [_to_domain(row) for row in rows]
