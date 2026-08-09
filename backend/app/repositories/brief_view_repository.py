"""Repository for `morning_brief_view` (PLAN.md Milestone 7.5.2 correction).

See `provenance_repository.py`'s module docstring for this project's
repository conventions (function-style, domain objects only, flush-not-commit).
The minimum-gap "don't record a new view too soon" policy lives in
`app.services.morning_brief_service`, not here — this repository only ever
does exactly what it's told (insert a row, or read the latest one).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.brief_view import BriefView
from app.models.brief_view import BriefView as BriefViewModel


def _to_domain(row: BriefViewModel) -> BriefView:
    return BriefView(id=row.id, viewed_at=row.viewed_at, created_at=row.created_at)


def record_view(db: Session) -> BriefView:
    row = BriefViewModel()
    db.add(row)
    db.flush()
    db.refresh(row)
    return _to_domain(row)


def get_latest_view(db: Session) -> BriefView | None:
    stmt = select(BriefViewModel).order_by(BriefViewModel.viewed_at.desc()).limit(1)
    row = db.execute(stmt).scalars().first()
    return _to_domain(row) if row is not None else None
