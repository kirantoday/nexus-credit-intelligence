"""Repository for `court_docket` (PLAN.md section 4.5, Milestone 7).

See `provenance_repository.py`'s module docstring for this project's
repository conventions (function-style, domain objects only, flush-not-commit).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.court_docket import CourtDocket, CourtDocketCreate
from app.models.court_docket import CourtDocket as CourtDocketModel


def _to_domain(row: CourtDocketModel) -> CourtDocket:
    return CourtDocket(
        id=row.id,
        issuer_id=row.issuer_id,
        courtlistener_docket_id=row.courtlistener_docket_id,
        court=row.court,
        docket_number=row.docket_number,
        case_name=row.case_name,
        nature_of_suit=row.nature_of_suit,
        chapter=row.chapter,
        date_filed=row.date_filed,
        provenance_id=row.provenance_id,
        created_at=row.created_at,
    )


def get_docket(db: Session, docket_id: UUID) -> CourtDocket | None:
    row = db.get(CourtDocketModel, docket_id)
    return _to_domain(row) if row is not None else None


def get_docket_by_courtlistener_id(db: Session, courtlistener_docket_id: int) -> CourtDocket | None:
    stmt = select(CourtDocketModel).where(
        CourtDocketModel.courtlistener_docket_id == courtlistener_docket_id
    )
    row = db.execute(stmt).scalars().first()
    return _to_domain(row) if row is not None else None


def create_docket(db: Session, data: CourtDocketCreate) -> tuple[CourtDocket, bool]:
    """Get-or-create by `courtlistener_docket_id` — the idempotency guard a
    re-run of the docket sync relies on. Returns (docket, created)."""
    existing = get_docket_by_courtlistener_id(db, data.courtlistener_docket_id)
    if existing is not None:
        return existing, False

    row = CourtDocketModel(
        issuer_id=data.issuer_id,
        courtlistener_docket_id=data.courtlistener_docket_id,
        court=data.court,
        docket_number=data.docket_number,
        case_name=data.case_name,
        nature_of_suit=data.nature_of_suit,
        chapter=data.chapter,
        date_filed=data.date_filed,
        provenance_id=data.provenance_id,
    )
    db.add(row)
    db.flush()
    db.refresh(row)
    return _to_domain(row), True


def list_dockets_by_issuer(db: Session, issuer_id: UUID) -> list[CourtDocket]:
    stmt = (
        select(CourtDocketModel)
        .where(CourtDocketModel.issuer_id == issuer_id)
        .order_by(CourtDocketModel.date_filed.desc())
    )
    rows = db.execute(stmt).scalars().all()
    return [_to_domain(row) for row in rows]


def list_dockets_linked_to_issuers(db: Session) -> list[CourtDocket]:
    """Every docket with a real, verified issuer link — the sync target set
    for `app.scripts.sync_court_dockets` (PLAN.md 4.5's `issuer_id` is
    nullable; a docket only enters this list once an admin/seed action has
    explicitly linked it to a real issuer)."""
    stmt = select(CourtDocketModel).where(CourtDocketModel.issuer_id.is_not(None))
    rows = db.execute(stmt).scalars().all()
    return [_to_domain(row) for row in rows]
