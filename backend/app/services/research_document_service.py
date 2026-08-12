"""Research Document upload/list/metadata/archive orchestration (PLAN.md
4.10, 4.12, 15; ADR-007; Milestone 10B).

**Upload consistency strategy (approved architecture)**: Storage write
happens first, the database transaction (`raw_provider_payload` +
`provenance` + `research_document` + `audit_event`, all via the same
`db: Session`) second. If anything in the database transaction raises after
the Storage upload already succeeded, this module makes a synchronous
compensating `storage_client.delete()` call for the just-uploaded object
before re-raising — an orphaned Storage object with no DB row is a smaller,
easier-to-reconcile problem than a DB row pointing at a file that was never
written. A compensating delete that itself fails is logged clearly (not
swallowed) via the standard logger, and the original database error is still
raised — a rare double-failure leaves one orphaned object, an accepted
residual risk per the architecture review (no reconciliation job exists in
10B).

**Provenance**: reuses ADR-007's `admin_upload` channel exactly as
`docket_document` was always meant to (see that ADR's consequences section)
— `provenance.provider = admin_upload`, `original_source` records what the
uploader attests the document actually came from, `classification = public`
(an internally-uploaded research document is not licensed-vendor data,
synthetic demo data, or AI-generated — `public` is the correct existing
`DataClassification` bucket; `confidentiality_classification` on
`research_document` itself, not `provenance.classification`, is what
captures the standard/restricted internal-visibility distinction).

**No PDF extraction happens here or anywhere in Milestone 10B** —
`research_document.extracted_text` is never populated by this module.
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import UTC, date, datetime
from urllib.parse import quote
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.core.types import (
    AccessClassification,
    AuditEventType,
    DataClassification,
    OriginalSource,
    ProviderName,
    ResearchDocumentType,
    TransformationType,
)
from app.domain.audit import AuditEvent, AuditEventCreate
from app.domain.provenance import ProvenanceCreate
from app.domain.raw_provider_payload import RawProviderPayloadCreate
from app.domain.research_document import (
    ResearchDocument,
    ResearchDocumentCreate,
    ResearchDocumentMetadataUpdate,
)
from app.repositories import (
    audit_repository,
    provenance_repository,
    raw_provider_payload_repository,
    research_document_repository,
)
from app.storage.base import StorageClient, StorageError

logger = logging.getLogger(__name__)

_ENTITY_TABLE = "research_document"

# Server-side, authoritative — a client-side check is UX-only, never trusted
# as the security boundary (approved architecture, item 3).
MAX_UPLOAD_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB

# The actual PDF file signature (magic bytes) — validated against real file
# content, never the client-supplied Content-Type header or filename
# extension (approved architecture, item 2).
_PDF_MAGIC_BYTES = b"%PDF-"

# Short-lived: long enough for a browser tab to load/download the file, short
# enough that a leaked link isn't useful for long (approved architecture,
# item 13 — "short-lived signed URLs").
SIGNED_URL_EXPIRES_IN_SECONDS = 300

_UNSAFE_FILENAME_CHARS = re.compile(r'[\x00-\x1f\x7f"/\\:*?<>|]')
_MAX_FILENAME_LENGTH = 255


class InvalidPdfError(Exception):
    """The uploaded content's actual bytes don't start with the PDF file
    signature — raised before any Storage write, so no compensation is
    needed for this failure mode."""


class FileTooLargeError(Exception):
    """The uploaded content exceeds `MAX_UPLOAD_SIZE_BYTES` — raised before
    any Storage write."""

    def __init__(self, size_bytes: int) -> None:
        self.size_bytes = size_bytes
        super().__init__(
            f"file size {size_bytes} bytes exceeds the {MAX_UPLOAD_SIZE_BYTES}-byte limit"
        )


class ResearchDocumentArchivedError(Exception):
    """Raised when a metadata edit is attempted against an archived
    document — archived documents are read-only, matching `research_note`'s
    identical posture."""

    def __init__(self, document_id: UUID) -> None:
        self.document_id = document_id
        super().__init__(f"research_document {document_id} is archived and cannot be edited")


def _validate_pdf(content: bytes) -> None:
    if not content.startswith(_PDF_MAGIC_BYTES):
        raise InvalidPdfError("uploaded content is not a valid PDF (signature mismatch)")


def _validate_size(content: bytes) -> None:
    if len(content) > MAX_UPLOAD_SIZE_BYTES:
        raise FileTooLargeError(len(content))


def sanitize_filename(original_filename: str) -> str:
    """Strips control characters and path/header-unsafe characters from a
    user-supplied filename before it's stored or ever placed in a
    `Content-Disposition` response header. Never used to build the Storage
    object key (that's always a server-generated UUID) — this is purely for
    safe display/download."""
    stripped = _UNSAFE_FILENAME_CHARS.sub("", original_filename).strip()
    if not stripped:
        stripped = "document.pdf"
    return stripped[:_MAX_FILENAME_LENGTH]


def build_storage_key(issuer_id: UUID, document_id: UUID) -> str:
    """Server-generated, never derived from the user's filename — eliminates
    path traversal/collision risk by construction (approved architecture,
    item 13)."""
    return f"research-documents/{issuer_id}/{document_id}/{document_id}.pdf"


def _compensate_storage_upload(
    storage_client: StorageClient, key: str, *, cause: Exception
) -> None:
    try:
        storage_client.delete(key=key)
        logger.warning(
            "research_document upload: database write failed after Storage upload "
            "succeeded; compensating delete of key=%s completed. Original error: %s",
            key,
            cause,
        )
    except StorageError:
        logger.error(
            "research_document upload: database write failed AND the compensating "
            "Storage delete for key=%s also failed — an orphaned Storage object "
            "likely exists and requires manual cleanup. Original database error: %s",
            key,
            cause,
            exc_info=True,
        )


def upload_document(
    db: Session,
    storage_client: StorageClient,
    *,
    issuer_id: UUID,
    security_id: UUID | None,
    document_type: ResearchDocumentType,
    title: str,
    description: str | None,
    original_filename: str,
    content: bytes,
    document_date: date | None,
    confidentiality_classification: AccessClassification,
    uploaded_by: str | None,
    original_source: OriginalSource,
) -> ResearchDocument:
    """Validates, uploads to Storage, then persists identity/provenance/audit
    rows in one database transaction. See module docstring for the
    Storage-first consistency strategy."""
    _validate_pdf(content)
    _validate_size(content)
    sanitized_filename = sanitize_filename(original_filename)

    document_id = uuid4()
    storage_key = build_storage_key(issuer_id, document_id)

    storage_client.upload(key=storage_key, content=content, content_type="application/pdf")

    try:
        now = datetime.now(UTC)
        checksum = hashlib.sha256(content).hexdigest()

        payload = raw_provider_payload_repository.create_payload(
            db,
            RawProviderPayloadCreate(
                provider=ProviderName.ADMIN_UPLOAD,
                source_record_id=str(document_id),
                request_fingerprint=f"research_document:{document_id}",
                storage_object_path=storage_key,
                retrieved_at=now,
                checksum=checksum,
                content_type="application/pdf",
                size_bytes=len(content),
            ),
        )
        provenance = provenance_repository.create_provenance(
            db,
            ProvenanceCreate(
                provider=ProviderName.ADMIN_UPLOAD,
                original_source=original_source,
                source_attested_by=uploaded_by,
                source_attested_at=now,
                source_record_id=str(document_id),
                source_url=None,
                as_of_date=document_date or now.date(),
                retrieved_at=now,
                transformation=TransformationType.REPORTED,
                classification=DataClassification.PUBLIC,
                raw_payload_id=payload.id,
            ),
        )
        raw_provider_payload_repository.link_provenance(db, payload.id, provenance.id)

        document = research_document_repository.create_document(
            db,
            ResearchDocumentCreate(
                id=document_id,
                issuer_id=issuer_id,
                security_id=security_id,
                document_type=document_type,
                title=title,
                description=description,
                original_filename=sanitized_filename,
                raw_payload_id=payload.id,
                document_date=document_date,
                confidentiality_classification=confidentiality_classification,
                uploaded_by=uploaded_by,
                provenance_id=provenance.id,
            ),
        )
        audit_repository.create_event(
            db,
            AuditEventCreate(
                user_id=uploaded_by,
                event_type=AuditEventType.RESEARCH_DOCUMENT_UPLOADED.value,
                entity_table=_ENTITY_TABLE,
                entity_id=document.id,
                before_state=None,
                after_state={
                    "title": document.title,
                    "document_type": document.document_type.value,
                    "issuer_id": str(document.issuer_id),
                    "original_filename": document.original_filename,
                },
            ),
        )
        return document
    except Exception as exc:
        _compensate_storage_upload(storage_client, storage_key, cause=exc)
        raise


def get_document(db: Session, document_id: UUID) -> ResearchDocument | None:
    return research_document_repository.get_document(db, document_id)


def list_documents(
    db: Session,
    *,
    issuer_id: UUID | None = None,
    document_type: ResearchDocumentType | None = None,
    include_archived: bool = False,
) -> list[tuple[ResearchDocument, str, str | None]]:
    return research_document_repository.list_documents(
        db,
        issuer_id=issuer_id,
        document_type=document_type,
        include_archived=include_archived,
    )


def get_download_url(
    db: Session,
    storage_client: StorageClient,
    document_id: UUID,
    *,
    force_download: bool = False,
) -> tuple[ResearchDocument, str] | None:
    """Returns `(document, signed_url)`, or `None` if the document doesn't
    exist. Mints a fresh, short-lived signed URL on every call — never
    caches or returns a permanent link.

    `force_download=False` (the default, "view") returns the plain signed
    URL — no `Content-Disposition` header, so the browser renders the PDF
    inline. `force_download=True` ("download") appends Supabase Storage's
    `download=<filename>` query parameter, which makes Supabase itself emit
    `Content-Disposition: attachment; filename=...` (safely percent-encoded
    by Supabase, not string-built here) — verified live against the real
    bucket before this was written, not assumed from documentation."""
    document = research_document_repository.get_document(db, document_id)
    if document is None:
        return None
    payload = raw_provider_payload_repository.get_payload(db, document.raw_payload_id)
    if payload is None or payload.storage_object_path is None:
        raise StorageError(f"research_document {document_id} has no storage object on file")
    signed_url = storage_client.create_signed_url(
        key=payload.storage_object_path, expires_in_seconds=SIGNED_URL_EXPIRES_IN_SECONDS
    )
    if force_download:
        separator = "&" if "?" in signed_url else "?"
        signed_url = f"{signed_url}{separator}download={quote(document.original_filename)}"
    return document, signed_url


def update_metadata(
    db: Session, document_id: UUID, data: ResearchDocumentMetadataUpdate
) -> ResearchDocument | None:
    existing = research_document_repository.get_document(db, document_id)
    if existing is None:
        return None
    if existing.is_archived:
        raise ResearchDocumentArchivedError(document_id)

    updated = research_document_repository.apply_metadata_update(db, document_id, data)
    assert updated is not None
    audit_repository.create_event(
        db,
        AuditEventCreate(
            user_id=data.edited_by,
            event_type=AuditEventType.RESEARCH_DOCUMENT_METADATA_UPDATED.value,
            entity_table=_ENTITY_TABLE,
            entity_id=document_id,
            before_state={
                "title": existing.title,
                "description": existing.description,
                "document_type": existing.document_type.value,
                "document_date": (
                    existing.document_date.isoformat() if existing.document_date else None
                ),
                "confidentiality_classification": existing.confidentiality_classification.value,
            },
            after_state={
                "title": updated.title,
                "description": updated.description,
                "document_type": updated.document_type.value,
                "document_date": (
                    updated.document_date.isoformat() if updated.document_date else None
                ),
                "confidentiality_classification": updated.confidentiality_classification.value,
            },
        ),
    )
    return updated


def archive_document(
    db: Session, document_id: UUID, *, archived_by: str | None
) -> ResearchDocument | None:
    """Idempotent no-op (returns the already-archived document) if called
    twice. The physical Storage object is never deleted here — archiving is
    the only "removal" path and is metadata-only, preserving the original
    artifact for provenance/audit durability (approved architecture,
    item 7)."""
    existing = research_document_repository.get_document(db, document_id)
    if existing is None:
        return None
    if existing.is_archived:
        return existing

    archived = research_document_repository.archive_document(
        db, document_id, archived_by=archived_by
    )
    audit_repository.create_event(
        db,
        AuditEventCreate(
            user_id=archived_by,
            event_type=AuditEventType.RESEARCH_DOCUMENT_ARCHIVED.value,
            entity_table=_ENTITY_TABLE,
            entity_id=document_id,
            before_state={"is_archived": False},
            after_state={"is_archived": True},
        ),
    )
    return archived


def list_audit_events(db: Session, document_id: UUID) -> list[AuditEvent]:
    return audit_repository.list_events_for_entity(db, _ENTITY_TABLE, document_id)
