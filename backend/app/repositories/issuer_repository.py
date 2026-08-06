"""Repository for `issuer`.

See `provenance_repository.py`'s module docstring for this project's
repository conventions (function-style, domain objects only, flush-not-commit).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.issuer import Issuer, IssuerCreate
from app.models.issuer import Issuer as IssuerModel


def _to_domain(row: IssuerModel) -> Issuer:
    return Issuer(
        id=row.id,
        legal_name=row.legal_name,
        cik=row.cik,
        lei=row.lei,
        ticker=row.ticker,
        sic=row.sic,
        sector=row.sector,
        is_synthetic=row.is_synthetic,
        synthetic_reason=row.synthetic_reason,
        provenance_id=row.provenance_id,
    )


def create_issuer(db: Session, data: IssuerCreate) -> Issuer:
    row = IssuerModel(
        legal_name=data.legal_name,
        cik=data.cik,
        lei=data.lei,
        ticker=data.ticker,
        sic=data.sic,
        sector=data.sector,
        is_synthetic=data.is_synthetic,
        synthetic_reason=data.synthetic_reason,
        provenance_id=data.provenance_id,
    )
    db.add(row)
    db.flush()
    db.refresh(row)
    return _to_domain(row)


def get_issuer(db: Session, issuer_id: UUID) -> Issuer | None:
    row = db.get(IssuerModel, issuer_id)
    return _to_domain(row) if row is not None else None


def get_issuer_by_cik(db: Session, cik: str) -> Issuer | None:
    """Idempotent re-ingestion check: has this real-world issuer already been created."""
    stmt = select(IssuerModel).where(IssuerModel.cik == cik)
    row = db.execute(stmt).scalars().first()
    return _to_domain(row) if row is not None else None


def get_issuer_by_legal_name(db: Session, legal_name: str) -> Issuer | None:
    """Idempotent re-seed check for synthetic issuers, which have no `cik`.

    `legal_name` has no uniqueness constraint at the schema level (two real
    issuers could coincidentally share a name), so this is a convenience
    lookup for the synthetic generator's own fixed, known-unique demo names —
    not a general-purpose "find the issuer named X" API.
    """
    stmt = select(IssuerModel).where(IssuerModel.legal_name == legal_name)
    row = db.execute(stmt).scalars().first()
    return _to_domain(row) if row is not None else None
