"""Repository for `financial_fact`.

See `provenance_repository.py`'s module docstring for this project's
repository conventions (function-style, domain objects only, flush-not-commit).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.types import FormType
from app.domain.financial_fact import FinancialFact, FinancialFactCreate
from app.models.financial_fact import FinancialFact as FinancialFactModel


def _to_domain(row: FinancialFactModel) -> FinancialFact:
    return FinancialFact(
        id=row.id,
        issuer_id=row.issuer_id,
        concept=row.concept,
        value=row.value,
        unit=row.unit,
        fiscal_period=row.fiscal_period,
        fiscal_year=row.fiscal_year,
        form_type=FormType(row.form_type),
        filing_date=row.filing_date,
        accession_no=row.accession_no,
        provenance_id=row.provenance_id,
    )


def create_financial_fact(db: Session, data: FinancialFactCreate) -> FinancialFact:
    row = FinancialFactModel(
        issuer_id=data.issuer_id,
        concept=data.concept,
        value=data.value,
        unit=data.unit,
        fiscal_period=data.fiscal_period,
        fiscal_year=data.fiscal_year,
        form_type=data.form_type.value,
        filing_date=data.filing_date,
        accession_no=data.accession_no,
        provenance_id=data.provenance_id,
    )
    db.add(row)
    db.flush()
    db.refresh(row)
    return _to_domain(row)


def get_financial_fact(db: Session, financial_fact_id: UUID) -> FinancialFact | None:
    row = db.get(FinancialFactModel, financial_fact_id)
    return _to_domain(row) if row is not None else None


def list_financial_facts_by_issuer(db: Session, issuer_id: UUID) -> list[FinancialFact]:
    stmt = select(FinancialFactModel).where(FinancialFactModel.issuer_id == issuer_id)
    rows = db.execute(stmt).scalars().all()
    return [_to_domain(row) for row in rows]


def get_by_dedup_key(
    db: Session,
    issuer_id: UUID,
    concept: str,
    accession_no: str,
    fiscal_year: int,
    fiscal_period: str,
) -> FinancialFact | None:
    """Idempotent re-ingestion check matching `ix_financial_fact_dedup`."""
    stmt = select(FinancialFactModel).where(
        FinancialFactModel.issuer_id == issuer_id,
        FinancialFactModel.concept == concept,
        FinancialFactModel.accession_no == accession_no,
        FinancialFactModel.fiscal_year == fiscal_year,
        FinancialFactModel.fiscal_period == fiscal_period,
    )
    row = db.execute(stmt).scalars().first()
    return _to_domain(row) if row is not None else None
