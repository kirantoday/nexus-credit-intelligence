"""Repository for `security`, including the Credit Universe listing query.

See `provenance_repository.py`'s module docstring for this project's
repository conventions (function-style, domain objects only, flush-not-commit).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.types import (
    DataClassification,
    InstrumentType,
    ProviderName,
    Seniority,
    TransformationType,
)
from app.domain.security import Security, SecurityCreate
from app.models.issuer import Issuer as IssuerModel
from app.models.provenance import Provenance as ProvenanceModel
from app.models.security import Security as SecurityModel

SortField = Literal[
    "legal_name", "instrument_type", "maturity_date", "amount_outstanding", "coupon"
]
SortDirection = Literal["asc", "desc"]

_SORT_COLUMNS: dict[SortField, Any] = {
    "legal_name": IssuerModel.legal_name,
    "instrument_type": SecurityModel.instrument_type,
    "maturity_date": SecurityModel.maturity_date,
    "amount_outstanding": SecurityModel.amount_outstanding,
    "coupon": SecurityModel.coupon,
}


@dataclass(frozen=True, slots=True)
class SecurityWithIssuer:
    """One Credit Universe row: a security, its issuer, and its provenance —
    joined in one query rather than N+1 lookups, since PLAN.md section 5
    explicitly calls for this screen to scale to thousands of rows."""

    security: Security
    issuer_legal_name: str
    issuer_ticker: str | None
    issuer_sector: str | None
    provenance_provider: ProviderName
    provenance_classification: DataClassification
    provenance_transformation: TransformationType
    provenance_as_of_date: date
    provenance_retrieved_at: datetime


def _to_domain(row: SecurityModel) -> Security:
    return Security(
        id=row.id,
        issuer_id=row.issuer_id,
        instrument_type=InstrumentType(row.instrument_type),
        seniority=Seniority(row.seniority) if row.seniority else None,
        lien_position=row.lien_position,
        secured=row.secured,
        cusip=row.cusip,
        isin=row.isin,
        figi=row.figi,
        description=row.description,
        maturity_date=row.maturity_date,
        coupon=row.coupon,
        amount_outstanding=row.amount_outstanding,
        benchmark=row.benchmark,
        spread=row.spread,
        is_synthetic=row.is_synthetic,
        synthetic_reason=row.synthetic_reason,
        provenance_id=row.provenance_id,
    )


def create_security(db: Session, data: SecurityCreate) -> Security:
    row = SecurityModel(
        issuer_id=data.issuer_id,
        instrument_type=data.instrument_type.value,
        seniority=data.seniority.value if data.seniority else None,
        lien_position=data.lien_position,
        secured=data.secured,
        cusip=data.cusip,
        isin=data.isin,
        figi=data.figi,
        description=data.description,
        maturity_date=data.maturity_date,
        coupon=data.coupon,
        amount_outstanding=data.amount_outstanding,
        benchmark=data.benchmark,
        spread=data.spread,
        is_synthetic=data.is_synthetic,
        synthetic_reason=data.synthetic_reason,
        provenance_id=data.provenance_id,
    )
    db.add(row)
    db.flush()
    db.refresh(row)
    return _to_domain(row)


def get_security(db: Session, security_id: UUID) -> Security | None:
    row = db.get(SecurityModel, security_id)
    return _to_domain(row) if row is not None else None


def list_securities_by_issuer(db: Session, issuer_id: UUID) -> list[Security]:
    stmt = select(SecurityModel).where(SecurityModel.issuer_id == issuer_id)
    rows = db.execute(stmt).scalars().all()
    return [_to_domain(row) for row in rows]


def list_credit_universe(
    db: Session,
    *,
    instrument_type: InstrumentType | None = None,
    is_synthetic: bool | None = None,
    search: str | None = None,
    sort_by: SortField = "legal_name",
    sort_dir: SortDirection = "asc",
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[SecurityWithIssuer], int]:
    """The Credit Universe screen's backing query: securities joined with
    their issuer and provenance, filtered/sorted/paginated server-side
    (PLAN.md section 5) — built to scale to thousands of rows, not just the
    small Milestone 4 seed set. Returns (this page of rows, total matching
    row count).
    """
    base_stmt = (
        select(SecurityModel, IssuerModel, ProvenanceModel)
        .join(IssuerModel, SecurityModel.issuer_id == IssuerModel.id)
        .join(ProvenanceModel, SecurityModel.provenance_id == ProvenanceModel.id)
    )

    if instrument_type is not None:
        base_stmt = base_stmt.where(SecurityModel.instrument_type == instrument_type.value)
    if is_synthetic is not None:
        base_stmt = base_stmt.where(SecurityModel.is_synthetic == is_synthetic)
    if search:
        pattern = f"%{search}%"
        base_stmt = base_stmt.where(
            IssuerModel.legal_name.ilike(pattern) | SecurityModel.description.ilike(pattern)
        )

    total = db.execute(select(func.count()).select_from(base_stmt.subquery())).scalar_one()

    sort_column = _SORT_COLUMNS[sort_by]
    order_column = sort_column.desc() if sort_dir == "desc" else sort_column.asc()
    # nulls_last regardless of direction: honestly-missing data (e.g. no
    # maturity_date on an aggregate bond position) shouldn't dominate either
    # end of a sort just because NULL sorts first/last by default.
    paged_stmt = (
        base_stmt.order_by(order_column.nulls_last())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = db.execute(paged_stmt).all()

    results = [
        SecurityWithIssuer(
            security=_to_domain(security_row),
            issuer_legal_name=issuer_row.legal_name,
            issuer_ticker=issuer_row.ticker,
            issuer_sector=issuer_row.sector,
            provenance_provider=ProviderName(provenance_row.provider),
            provenance_classification=DataClassification(provenance_row.classification),
            provenance_transformation=TransformationType(provenance_row.transformation),
            provenance_as_of_date=provenance_row.as_of_date,
            provenance_retrieved_at=provenance_row.retrieved_at,
        )
        for security_row, issuer_row, provenance_row in rows
    ]
    return results, total
