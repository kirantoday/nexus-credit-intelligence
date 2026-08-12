"""Repository for `research_document` (PLAN.md 4.10; Milestone 10B).

Function-style, domain objects only, flush-not-commit — see
`provenance_repository.py`'s module docstring for this project's repository
conventions. Upload orchestration (Storage write, `raw_provider_payload`/
`provenance`/audit-event wiring, compensating delete on failure) lives in
`app.services.research_document_service`, not here: this module only
persists whatever the service tells it to.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.types import AccessClassification, ResearchDocumentType
from app.domain.research_document import (
    ResearchDocument,
    ResearchDocumentCreate,
    ResearchDocumentMetadataUpdate,
)
from app.models.issuer import Issuer as IssuerModel
from app.models.research_document import ResearchDocument as ResearchDocumentModel


def _to_domain(row: ResearchDocumentModel) -> ResearchDocument:
    return ResearchDocument(
        id=row.id,
        issuer_id=row.issuer_id,
        security_id=row.security_id,
        document_type=ResearchDocumentType(row.document_type),
        title=row.title,
        description=row.description,
        original_filename=row.original_filename,
        raw_payload_id=row.raw_payload_id,
        extracted_text=row.extracted_text,
        document_date=row.document_date,
        confidentiality_classification=AccessClassification(row.confidentiality_classification),
        uploaded_by=row.uploaded_by,
        provenance_id=row.provenance_id,
        is_archived=row.is_archived,
        archived_at=row.archived_at,
        archived_by=row.archived_by,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def create_document(db: Session, data: ResearchDocumentCreate) -> ResearchDocument:
    row = ResearchDocumentModel(
        id=data.id,
        issuer_id=data.issuer_id,
        security_id=data.security_id,
        document_type=data.document_type.value,
        title=data.title,
        description=data.description,
        original_filename=data.original_filename,
        raw_payload_id=data.raw_payload_id,
        document_date=data.document_date,
        confidentiality_classification=data.confidentiality_classification.value,
        uploaded_by=data.uploaded_by,
        provenance_id=data.provenance_id,
    )
    db.add(row)
    db.flush()
    db.refresh(row)
    return _to_domain(row)


def get_document(db: Session, document_id: UUID) -> ResearchDocument | None:
    row = db.get(ResearchDocumentModel, document_id)
    return _to_domain(row) if row is not None else None


def list_documents(
    db: Session,
    *,
    issuer_id: UUID | None = None,
    document_type: ResearchDocumentType | None = None,
    include_archived: bool = False,
) -> list[tuple[ResearchDocument, str, str | None]]:
    """Cross-issuer (or, with `issuer_id`, single-issuer) listing with joined
    issuer display fields (`legal_name`, `ticker`) — backs both the
    issuer-scoped section and the global Research Documents workspace,
    matching `research_repository.list_notes`'s precedent exactly."""
    stmt = select(ResearchDocumentModel, IssuerModel.legal_name, IssuerModel.ticker).join(
        IssuerModel, ResearchDocumentModel.issuer_id == IssuerModel.id
    )
    if issuer_id is not None:
        stmt = stmt.where(ResearchDocumentModel.issuer_id == issuer_id)
    if document_type is not None:
        stmt = stmt.where(ResearchDocumentModel.document_type == document_type.value)
    if not include_archived:
        stmt = stmt.where(ResearchDocumentModel.is_archived.is_(False))
    stmt = stmt.order_by(ResearchDocumentModel.created_at.desc())
    rows = db.execute(stmt).all()
    return [(_to_domain(doc_row), legal_name, ticker) for doc_row, legal_name, ticker in rows]


def apply_metadata_update(
    db: Session, document_id: UUID, data: ResearchDocumentMetadataUpdate
) -> ResearchDocument | None:
    row = db.get(ResearchDocumentModel, document_id)
    if row is None:
        return None
    if data.title is not None:
        row.title = data.title
    if data.description is not None:
        row.description = data.description
    if data.document_type is not None:
        row.document_type = data.document_type.value
    if data.document_date is not None:
        row.document_date = data.document_date
    if data.confidentiality_classification is not None:
        row.confidentiality_classification = data.confidentiality_classification.value
    row.updated_at = datetime.now(UTC)
    db.flush()
    db.refresh(row)
    return _to_domain(row)


def archive_document(
    db: Session, document_id: UUID, *, archived_by: str | None
) -> ResearchDocument | None:
    row = db.get(ResearchDocumentModel, document_id)
    if row is None or row.is_archived:
        return None
    row.is_archived = True
    row.archived_at = datetime.now(UTC)
    row.archived_by = archived_by
    db.flush()
    db.refresh(row)
    return _to_domain(row)
