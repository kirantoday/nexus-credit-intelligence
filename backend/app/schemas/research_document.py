"""Request/response schemas for the Research Documents API (PLAN.md 4.10,
4.12, 15; ADR-007; Milestone 10B).

Kept as its own layer, independent of `app.domain.research_document` — per
PLAN.md section 3, routes depend on schemas, not domain objects directly.
Upload itself has no JSON request schema (it's `multipart/form-data`,
handled via `Form(...)`/`UploadFile` parameters directly on the route) —
every other action here is a normal JSON request/response.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.types import AccessClassification, ResearchDocumentType
from app.domain.research_document import ResearchDocument, ResearchDocumentMetadataUpdate


class ResearchDocumentMetadataUpdateRequest(BaseModel):
    """All fields optional — `None` means "leave unchanged"."""

    model_config = ConfigDict(frozen=True)

    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = None
    document_type: ResearchDocumentType | None = None
    document_date: date | None = None
    confidentiality_classification: AccessClassification | None = None
    edited_by: str | None = None

    def to_domain(self) -> ResearchDocumentMetadataUpdate:
        return ResearchDocumentMetadataUpdate(
            title=self.title,
            description=self.description,
            document_type=self.document_type,
            document_date=self.document_date,
            confidentiality_classification=self.confidentiality_classification,
            edited_by=self.edited_by,
        )


class ArchiveDocumentRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    archived_by: str | None = None


class ResearchDocumentResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    issuer_id: UUID
    security_id: UUID | None
    document_type: ResearchDocumentType
    title: str
    description: str | None
    original_filename: str
    document_date: date | None
    confidentiality_classification: AccessClassification
    uploaded_by: str | None
    is_archived: bool
    archived_at: datetime | None
    archived_by: str | None
    created_at: datetime
    updated_at: datetime

    @staticmethod
    def from_domain(document: ResearchDocument) -> ResearchDocumentResponse:
        return ResearchDocumentResponse(
            id=document.id,
            issuer_id=document.issuer_id,
            security_id=document.security_id,
            document_type=document.document_type,
            title=document.title,
            description=document.description,
            original_filename=document.original_filename,
            document_date=document.document_date,
            confidentiality_classification=document.confidentiality_classification,
            uploaded_by=document.uploaded_by,
            is_archived=document.is_archived,
            archived_at=document.archived_at,
            archived_by=document.archived_by,
            created_at=document.created_at,
            updated_at=document.updated_at,
        )


class ResearchDocumentSummary(ResearchDocumentResponse):
    """A `ResearchDocumentResponse` plus the issuer display fields both the
    issuer-scoped section and the global workspace need — same pattern as
    `research_notes`' `ResearchNoteSummary`."""

    model_config = ConfigDict(frozen=True)

    issuer_legal_name: str
    issuer_ticker: str | None

    @staticmethod
    def from_domain_with_issuer(
        document: ResearchDocument, issuer_legal_name: str, issuer_ticker: str | None
    ) -> ResearchDocumentSummary:
        base = ResearchDocumentResponse.from_domain(document)
        return ResearchDocumentSummary(
            **base.model_dump(), issuer_legal_name=issuer_legal_name, issuer_ticker=issuer_ticker
        )


class ResearchDocumentListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    documents: list[ResearchDocumentSummary]


class ResearchDocumentDownloadResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    signed_url: str
    expires_in_seconds: int
    original_filename: str
