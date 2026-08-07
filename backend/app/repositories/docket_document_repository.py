"""Repository for `docket_document` (PLAN.md sections 4.5, 15).

See `provenance_repository.py`'s module docstring for this project's
repository conventions (function-style, domain objects only, flush-not-commit).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.types import DocketDocumentAvailability
from app.domain.docket_document import DocketDocument, DocketDocumentCreate
from app.models.docket_document import DocketDocument as DocketDocumentModel


def _to_domain(row: DocketDocumentModel) -> DocketDocument:
    return DocketDocument(
        id=row.id,
        docket_entry_id=row.docket_entry_id,
        courtlistener_document_id=row.courtlistener_document_id,
        availability=DocketDocumentAvailability(row.availability),
        description=row.description,
        page_count=row.page_count,
        is_sealed=row.is_sealed,
        recap_document_url=row.recap_document_url,
        raw_payload_id=row.raw_payload_id,
        uploaded_by=row.uploaded_by,
        uploaded_at=row.uploaded_at,
        provenance_id=row.provenance_id,
        created_at=row.created_at,
    )


def get_document_by_courtlistener_id(
    db: Session, courtlistener_document_id: int
) -> DocketDocument | None:
    stmt = select(DocketDocumentModel).where(
        DocketDocumentModel.courtlistener_document_id == courtlistener_document_id
    )
    row = db.execute(stmt).scalars().first()
    return _to_domain(row) if row is not None else None


def create_document(db: Session, data: DocketDocumentCreate) -> tuple[DocketDocument, bool]:
    """Get-or-create by `courtlistener_document_id`. Returns (document, created)."""
    existing = get_document_by_courtlistener_id(db, data.courtlistener_document_id)
    if existing is not None:
        return existing, False

    row = DocketDocumentModel(
        docket_entry_id=data.docket_entry_id,
        courtlistener_document_id=data.courtlistener_document_id,
        availability=data.availability.value,
        description=data.description,
        page_count=data.page_count,
        is_sealed=data.is_sealed,
        recap_document_url=data.recap_document_url,
        raw_payload_id=data.raw_payload_id,
        uploaded_by=data.uploaded_by,
        uploaded_at=data.uploaded_at,
        provenance_id=data.provenance_id,
    )
    db.add(row)
    db.flush()
    db.refresh(row)
    return _to_domain(row), True


def list_documents_by_entry(db: Session, docket_entry_id: UUID) -> list[DocketDocument]:
    stmt = select(DocketDocumentModel).where(DocketDocumentModel.docket_entry_id == docket_entry_id)
    rows = db.execute(stmt).scalars().all()
    return [_to_domain(row) for row in rows]
