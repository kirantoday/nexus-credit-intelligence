"""Research Documents API routes (PLAN.md 4.10, 4.12, 15; ADR-007;
Milestone 10B).

Thin per PLAN.md section 3: delegates to `research_document_service`, no
business logic or ORM/Storage access here. Upload is the one endpoint that
isn't plain JSON — `multipart/form-data`, since it carries an actual file.

Every uploaded file's actual byte size is checked *before* `UploadFile.read()`
loads it into memory (`file.file.seek`/`tell` against the already-parsed
spooled temp file) — a client claiming a small file but sending a large one
is rejected without ever buffering the oversized content in this process.
Note: Starlette's own multipart parser has already spooled the full request
body (to memory up to a threshold, then to disk) before this route function
runs at all — an ASGI/proxy-level max-body-size limit (Railway/nginx) is the
correct place for a true streaming-abort defense against a very large
request body, and is documented as residual hardening this milestone does
not implement (see the architecture review's Security Risks section).
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.core.types import AccessClassification, OriginalSource, ResearchDocumentType
from app.db.session import get_db
from app.schemas.research_document import (
    ArchiveDocumentRequest,
    ResearchDocumentDownloadResponse,
    ResearchDocumentListResponse,
    ResearchDocumentMetadataUpdateRequest,
    ResearchDocumentResponse,
    ResearchDocumentSummary,
)
from app.services import research_document_service
from app.services.research_document_service import (
    MAX_UPLOAD_SIZE_BYTES,
    FileTooLargeError,
    InvalidPdfError,
    ResearchDocumentArchivedError,
)
from app.storage.base import StorageError
from app.storage.factory import StorageConfigurationError, get_storage_client
from app.storage.supabase_storage_client import SupabaseStorageClient

router = APIRouter(prefix="/api/research-documents", tags=["research-documents"])


def _get_storage_client(
    settings: Annotated[Settings, Depends(get_settings)],
) -> Iterator[SupabaseStorageClient]:
    try:
        client = get_storage_client(settings)
    except StorageConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    try:
        yield client
    finally:
        client.close()


@router.get("", response_model=ResearchDocumentListResponse)
def list_documents(
    db: Annotated[Session, Depends(get_db)],
    issuer_id: UUID | None = None,
    document_type: ResearchDocumentType | None = None,
    include_archived: bool = False,
) -> ResearchDocumentListResponse:
    """`issuer_id` is optional — omitted, this backs the global Research
    Documents workspace; supplied, it backs the Issuer Detail section."""
    documents = research_document_service.list_documents(
        db, issuer_id=issuer_id, document_type=document_type, include_archived=include_archived
    )
    return ResearchDocumentListResponse(
        documents=[
            ResearchDocumentSummary.from_domain_with_issuer(document, legal_name, ticker)
            for document, legal_name, ticker in documents
        ]
    )


@router.post("", response_model=ResearchDocumentResponse, status_code=status.HTTP_201_CREATED)
def upload_document(
    db: Annotated[Session, Depends(get_db)],
    storage_client: Annotated[SupabaseStorageClient, Depends(_get_storage_client)],
    file: Annotated[UploadFile, File()],
    issuer_id: Annotated[UUID, Form()],
    document_type: Annotated[ResearchDocumentType, Form()],
    title: Annotated[str, Form(min_length=1, max_length=300)],
    security_id: Annotated[UUID | None, Form()] = None,
    description: Annotated[str | None, Form()] = None,
    document_date: Annotated[date | None, Form()] = None,
    confidentiality_classification: Annotated[
        AccessClassification, Form()
    ] = AccessClassification.STANDARD,
    uploaded_by: Annotated[str | None, Form()] = None,
    original_source: Annotated[OriginalSource, Form()] = OriginalSource.OTHER,
) -> ResearchDocumentResponse:
    # Check the already-parsed, spooled file's actual size before reading it
    # into a Python bytes buffer — see module docstring.
    file.file.seek(0, 2)
    actual_size = file.file.tell()
    file.file.seek(0)
    if actual_size > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"file size {actual_size} bytes exceeds the {MAX_UPLOAD_SIZE_BYTES}-byte limit",
        )

    content = file.file.read()
    original_filename = file.filename or "document.pdf"

    try:
        document = research_document_service.upload_document(
            db,
            storage_client,
            issuer_id=issuer_id,
            security_id=security_id,
            document_type=document_type,
            title=title,
            description=description,
            original_filename=original_filename,
            content=content,
            document_date=document_date,
            confidentiality_classification=confidentiality_classification,
            uploaded_by=uploaded_by,
            original_source=original_source,
        )
    except InvalidPdfError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except FileTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc)
        ) from exc
    except StorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Storage upload failed: {exc}"
        ) from exc

    return ResearchDocumentResponse.from_domain(document)


@router.get("/{document_id}", response_model=ResearchDocumentResponse)
def get_document(
    document_id: UUID, db: Annotated[Session, Depends(get_db)]
) -> ResearchDocumentResponse:
    document = research_document_service.get_document(db, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Research document not found")
    return ResearchDocumentResponse.from_domain(document)


@router.get("/{document_id}/download", response_model=ResearchDocumentDownloadResponse)
def get_download_url(
    document_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    storage_client: Annotated[SupabaseStorageClient, Depends(_get_storage_client)],
    download: bool = False,
) -> ResearchDocumentDownloadResponse:
    """`download=false` (default) returns a signed URL for inline viewing
    (native browser PDF preview, no `Content-Disposition`); `download=true`
    returns one that forces a Save-As with the document's original
    filename."""
    try:
        result = research_document_service.get_download_url(
            db, storage_client, document_id, force_download=download
        )
    except StorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Signed URL creation failed: {exc}"
        ) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Research document not found")
    document, signed_url = result
    return ResearchDocumentDownloadResponse(
        signed_url=signed_url,
        expires_in_seconds=research_document_service.SIGNED_URL_EXPIRES_IN_SECONDS,
        original_filename=document.original_filename,
    )


@router.patch("/{document_id}", response_model=ResearchDocumentResponse)
def update_document_metadata(
    document_id: UUID,
    body: ResearchDocumentMetadataUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
) -> ResearchDocumentResponse:
    try:
        document = research_document_service.update_metadata(db, document_id, body.to_domain())
    except ResearchDocumentArchivedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Archived documents cannot be edited"
        ) from exc
    if document is None:
        raise HTTPException(status_code=404, detail="Research document not found")
    return ResearchDocumentResponse.from_domain(document)


@router.post("/{document_id}/archive", response_model=ResearchDocumentResponse)
def archive_document(
    document_id: UUID, body: ArchiveDocumentRequest, db: Annotated[Session, Depends(get_db)]
) -> ResearchDocumentResponse:
    document = research_document_service.archive_document(
        db, document_id, archived_by=body.archived_by
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Research document not found")
    return ResearchDocumentResponse.from_domain(document)
