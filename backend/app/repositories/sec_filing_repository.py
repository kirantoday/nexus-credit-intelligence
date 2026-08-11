"""Repository for `sec_filing` (PLAN.md section 24.5).

See `provenance_repository.py`'s module docstring for this project's
repository conventions (function-style, domain objects only, flush-not-commit).
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.sec_filing import SecFiling, SecFilingCreate
from app.models.sec_filing import SecFiling as SecFilingModel


def _to_domain(row: SecFilingModel) -> SecFiling:
    return SecFiling(
        id=row.id,
        issuer_id=row.issuer_id,
        accession_no=row.accession_no,
        form_type=row.form_type,
        filing_date=row.filing_date,
        period_of_report=row.period_of_report,
        is_amendment=row.is_amendment,
        primary_document=row.primary_document,
        primary_document_url=row.primary_document_url,
        provenance_id=row.provenance_id,
        created_at=row.created_at,
    )


def get_filing(db: Session, filing_id: UUID) -> SecFiling | None:
    row = db.get(SecFilingModel, filing_id)
    return _to_domain(row) if row is not None else None


def get_filing_by_accession(db: Session, accession_no: str) -> SecFiling | None:
    stmt = select(SecFilingModel).where(SecFilingModel.accession_no == accession_no)
    row = db.execute(stmt).scalars().first()
    return _to_domain(row) if row is not None else None


def create_filing(db: Session, data: SecFilingCreate) -> tuple[SecFiling, bool]:
    """Get-or-create by `accession_no` — the idempotency guard the overnight
    monitor relies on: duplicate accession numbers (a retried run, a filing
    seen again in a later delta window) must never produce a duplicate row.
    Returns (filing, created).
    """
    existing = get_filing_by_accession(db, data.accession_no)
    if existing is not None:
        return existing, False

    row = SecFilingModel(
        issuer_id=data.issuer_id,
        accession_no=data.accession_no,
        form_type=data.form_type,
        filing_date=data.filing_date,
        period_of_report=data.period_of_report,
        is_amendment=data.is_amendment,
        primary_document=data.primary_document,
        primary_document_url=data.primary_document_url,
        provenance_id=data.provenance_id,
    )
    db.add(row)
    db.flush()
    db.refresh(row)
    return _to_domain(row), True


def list_filings_by_issuer(
    db: Session, issuer_id: UUID, *, since: date | None = None
) -> list[SecFiling]:
    stmt = select(SecFilingModel).where(SecFilingModel.issuer_id == issuer_id)
    if since is not None:
        stmt = stmt.where(SecFilingModel.filing_date >= since)
    stmt = stmt.order_by(SecFilingModel.filing_date.desc())
    rows = db.execute(stmt).scalars().all()
    return [_to_domain(row) for row in rows]


def list_filings_since(
    db: Session, *, since: date | None = None, limit: int = 200
) -> list[SecFiling]:
    """Every filing across every issuer since a given date — backs the
    Morning Research Brief's "new filings" list (PLAN.md 24.8)."""
    stmt = select(SecFilingModel)
    if since is not None:
        stmt = stmt.where(SecFilingModel.filing_date >= since)
    stmt = stmt.order_by(SecFilingModel.filing_date.desc()).limit(limit)
    rows = db.execute(stmt).scalars().all()
    return [_to_domain(row) for row in rows]


def count_filings_created_since(db: Session, since: datetime | None) -> int:
    """Counts by `created_at` (when Nexus discovered/persisted the filing),
    not `filing_date` (the real-world event date) — a genuinely different,
    still-valid "how much did the last pipeline run itself discover"
    question. Not used by the Morning Research Brief's `RunDetails` as of
    PLAN.md Milestone 7.5.2's business-day-cycle correction — see
    `count_filings_by_filing_date_between` for the event-date metric that
    replaced it there (a historical backfill filing from January discovered
    today is genuinely new *to Nexus* today, but is not "new" to the
    current research cycle, which is what the Brief actually asks)."""
    stmt = select(func.count()).select_from(SecFilingModel)
    if since is not None:
        stmt = stmt.where(SecFilingModel.created_at >= since)
    return db.execute(stmt).scalar_one()


def count_filings_by_filing_date_between(
    db: Session, start_exclusive: date, end_inclusive: date
) -> int:
    """Counts by `filing_date` (the real-world event date) in
    `(start_exclusive, end_inclusive]` — the Morning Research Brief's
    "New SEC Filings" metric (PLAN.md Milestone 7.5.2's business-day-cycle
    correction), scoped to the current research cycle regardless of which
    pipeline run or mode (`delta` vs. an explicit `backfill` window used to
    correct a watermark gap) actually ingested the row. Never conflated
    with `count_filings_created_since` (discovery-time), which answers a
    different question and is left unchanged for any caller that still
    needs it."""
    stmt = (
        select(func.count())
        .select_from(SecFilingModel)
        .where(
            SecFilingModel.filing_date > start_exclusive,
            SecFilingModel.filing_date <= end_inclusive,
        )
    )
    return db.execute(stmt).scalar_one()
