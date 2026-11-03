"""Repository for `public_document_approval` and the eligibility facts the
allowlist decision is made from (Milestone 10D.2).

Function-style, domain objects only, flush-not-commit — see
`provenance_repository.py` for this project's repository conventions.

`load_eligibility_facts` reads the **authoritative parent rows fresh on
every call** (document, stored-file checksum, extraction, active approval)
and returns plain facts for `app.retrieval.eligibility.evaluate_eligibility`
to decide on. It never consults a chunk's copied
`confidentiality_classification`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.types import PageReferenceBasis
from app.domain.public_document_approval import PublicDocumentApproval, PublicDocumentApprovalCreate
from app.models.document_extraction import DocumentExtraction as DocumentExtractionModel
from app.models.public_document_approval import PublicDocumentApproval as ApprovalModel
from app.models.raw_provider_payload import RawProviderPayload as RawProviderPayloadModel
from app.models.research_document import ResearchDocument as ResearchDocumentModel
from app.retrieval.eligibility import EligibilityFacts


def _to_domain(row: ApprovalModel) -> PublicDocumentApproval:
    return PublicDocumentApproval(
        id=row.id,
        research_document_id=row.research_document_id,
        approved_raw_payload_checksum=row.approved_raw_payload_checksum,
        source_url=row.source_url,
        source_sha256=row.source_sha256,
        converter_name=row.converter_name,
        converter_version=row.converter_version,
        page_reference_basis=PageReferenceBasis(row.page_reference_basis),
        approval_basis=row.approval_basis,
        approved_by=row.approved_by,
        approved_at=row.approved_at,
        revoked_at=row.revoked_at,
        revoked_by=row.revoked_by,
    )


def create_approval(db: Session, data: PublicDocumentApprovalCreate) -> PublicDocumentApproval:
    row = ApprovalModel(
        research_document_id=data.research_document_id,
        approved_raw_payload_checksum=data.approved_raw_payload_checksum,
        source_url=data.source_url,
        source_sha256=data.source_sha256,
        converter_name=data.converter_name,
        converter_version=data.converter_version,
        page_reference_basis=data.page_reference_basis.value,
        approval_basis=data.approval_basis,
        approved_by=data.approved_by,
    )
    db.add(row)
    db.flush()
    db.refresh(row)
    return _to_domain(row)


def get_active_for_document(
    db: Session, research_document_id: uuid.UUID
) -> PublicDocumentApproval | None:
    stmt = select(ApprovalModel).where(
        ApprovalModel.research_document_id == research_document_id,
        ApprovalModel.revoked_at.is_(None),
    )
    row = db.execute(stmt).scalars().first()
    return _to_domain(row) if row is not None else None


def revoke_approval(
    db: Session, approval_id: uuid.UUID, *, revoked_by: str
) -> PublicDocumentApproval | None:
    """Idempotent: revoking an already-revoked approval returns it
    unchanged. Revocation is the only way an approval ends — rows are never
    deleted, so the audit trail survives."""
    row = db.get(ApprovalModel, approval_id)
    if row is None:
        return None
    if row.revoked_at is None:
        row.revoked_at = datetime.now(UTC)
        row.revoked_by = revoked_by
        db.flush()
        db.refresh(row)
    return _to_domain(row)


def load_eligibility_facts(
    db: Session, *, research_document_id: uuid.UUID, document_extraction_id: uuid.UUID
) -> EligibilityFacts:
    document_row = db.execute(
        select(
            ResearchDocumentModel.is_archived,
            ResearchDocumentModel.confidentiality_classification,
            RawProviderPayloadModel.checksum,
        )
        .join(
            RawProviderPayloadModel,
            ResearchDocumentModel.raw_payload_id == RawProviderPayloadModel.id,
        )
        .where(ResearchDocumentModel.id == research_document_id)
    ).first()

    extraction_row = db.execute(
        select(
            DocumentExtractionModel.research_document_id,
            DocumentExtractionModel.is_current,
            DocumentExtractionModel.status,
        ).where(DocumentExtractionModel.id == document_extraction_id)
    ).first()

    approval_checksum = db.execute(
        select(ApprovalModel.approved_raw_payload_checksum).where(
            ApprovalModel.research_document_id == research_document_id,
            ApprovalModel.revoked_at.is_(None),
        )
    ).scalar_one_or_none()

    return EligibilityFacts(
        document_found=document_row is not None,
        is_archived=bool(document_row.is_archived) if document_row is not None else False,
        confidentiality_classification=(
            document_row.confidentiality_classification if document_row is not None else None
        ),
        payload_checksum=document_row.checksum if document_row is not None else None,
        active_approval_checksum=approval_checksum,
        extraction_found=extraction_row is not None,
        extraction_belongs_to_document=(
            extraction_row is not None
            and extraction_row.research_document_id == research_document_id
        ),
        extraction_is_current=(
            bool(extraction_row.is_current) if extraction_row is not None else False
        ),
        extraction_status=extraction_row.status if extraction_row is not None else None,
    )
