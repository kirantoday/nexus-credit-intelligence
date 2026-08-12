"""Integration tests for `app/services/research_document_service.py`
(PLAN.md 4.10, 4.12, 15; ADR-007; Milestone 10B) against the live shared
`nexus` schema, using `FakeStorageClient` so no test touches real Supabase
Storage.

Covers: upload writes `raw_provider_payload` + `provenance` +
`research_document` + a `research_document_uploaded` audit event, with real
`admin_upload`/`original_source` provenance; invalid PDF content and
oversized files are rejected before any Storage write; a database failure
*after* a successful Storage upload triggers the compensating delete
(the approved Storage-first/DB-second consistency strategy); metadata
updates write before/after audit state and are blocked on archived
documents; archiving is idempotent, writes exactly one audit event, and
never deletes the physical Storage object; signed URLs are minted fresh
per call.
"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.types import AccessClassification, OriginalSource, ResearchDocumentType
from app.domain.issuer import Issuer, IssuerCreate
from app.domain.research_document import ResearchDocumentMetadataUpdate
from app.repositories import issuer_repository, provenance_repository
from app.services import research_document_service
from app.services.research_document_service import (
    MAX_UPLOAD_SIZE_BYTES,
    FileTooLargeError,
    InvalidPdfError,
    ResearchDocumentArchivedError,
    build_storage_key,
)
from app.storage.fake_storage_client import FakeStorageClient
from tests.integration.conftest import reported_public_provenance

_VALID_PDF_CONTENT = b"%PDF-1.4\n%test fixture content for Milestone 10B\n%%EOF"


def _seed_issuer(db: Session, *, legal_name: str = "Trinseo PLC (Test)") -> Issuer:
    provenance = provenance_repository.create_provenance(db, reported_public_provenance())
    return issuer_repository.create_issuer(
        db, IssuerCreate(legal_name=legal_name, ticker=None, provenance_id=provenance.id)
    )


def _upload(db: Session, storage: FakeStorageClient, issuer_id: object, **overrides: object):
    defaults: dict[str, object] = dict(
        issuer_id=issuer_id,
        security_id=None,
        document_type=ResearchDocumentType.CREDIT_AGREEMENT,
        title="Test Credit Agreement",
        description="A test upload",
        original_filename="Credit Agreement.pdf",
        content=_VALID_PDF_CONTENT,
        document_date=date(2026, 6, 1),
        confidentiality_classification=AccessClassification.STANDARD,
        uploaded_by="demo-analyst",
        original_source=OriginalSource.ISSUER_SITE,
    )
    defaults.update(overrides)
    return research_document_service.upload_document(db, storage, **defaults)  # type: ignore[arg-type]


def test_upload_writes_document_and_audit_event(db_session: Session) -> None:
    issuer = _seed_issuer(db_session)
    storage = FakeStorageClient()

    document = _upload(db_session, storage, issuer.id)

    assert document.title == "Test Credit Agreement"
    assert document.original_filename == "Credit Agreement.pdf"
    assert document.confidentiality_classification is AccessClassification.STANDARD
    assert document.extracted_text is None
    assert document.is_archived is False

    expected_key = build_storage_key(issuer.id, document.id)
    assert expected_key in storage.objects
    assert storage.objects[expected_key] == _VALID_PDF_CONTENT

    events = research_document_service.list_audit_events(db_session, document.id)
    assert len(events) == 1
    assert events[0].event_type == "research_document_uploaded"
    assert events[0].user_id == "demo-analyst"

    provenance = provenance_repository.get_provenance(db_session, document.provenance_id)
    assert provenance is not None
    assert provenance.provider.value == "admin_upload"
    assert provenance.original_source == OriginalSource.ISSUER_SITE


def test_upload_rejects_invalid_pdf_before_any_storage_write(db_session: Session) -> None:
    issuer = _seed_issuer(db_session)
    storage = FakeStorageClient()

    with pytest.raises(InvalidPdfError):
        _upload(db_session, storage, issuer.id, content=b"not a real pdf")

    assert storage.objects == {}


def test_upload_rejects_oversized_file_before_any_storage_write(db_session: Session) -> None:
    issuer = _seed_issuer(db_session)
    storage = FakeStorageClient()
    oversized = b"%PDF-" + b"0" * MAX_UPLOAD_SIZE_BYTES

    with pytest.raises(FileTooLargeError):
        _upload(db_session, storage, issuer.id, content=oversized)

    assert storage.objects == {}


def test_upload_compensates_storage_when_database_write_fails(db_session: Session) -> None:
    """A database-level failure (here: a foreign key violation from a
    nonexistent security_id) occurring *after* the Storage upload already
    succeeded must trigger a compensating delete of the just-uploaded
    object — the approved Storage-first/DB-second consistency strategy."""
    issuer = _seed_issuer(db_session)
    storage = FakeStorageClient()
    nonexistent_security_id = uuid4()

    with pytest.raises(IntegrityError):
        _upload(db_session, storage, issuer.id, security_id=nonexistent_security_id)

    # The object was uploaded, then removed by the compensating delete —
    # never left orphaned in Storage.
    assert storage.objects == {}
    assert len(storage.deleted_keys) == 1


def test_update_metadata_writes_before_after_audit_state(db_session: Session) -> None:
    issuer = _seed_issuer(db_session)
    storage = FakeStorageClient()
    document = _upload(db_session, storage, issuer.id)

    updated = research_document_service.update_metadata(
        db_session,
        document.id,
        ResearchDocumentMetadataUpdate(title="Amended Credit Agreement", edited_by="analyst-2"),
    )
    assert updated is not None
    assert updated.title == "Amended Credit Agreement"

    events = research_document_service.list_audit_events(db_session, document.id)
    update_event = next(e for e in events if e.event_type == "research_document_metadata_updated")
    assert update_event.before_state is not None
    assert update_event.before_state["title"] == "Test Credit Agreement"
    assert update_event.after_state is not None
    assert update_event.after_state["title"] == "Amended Credit Agreement"


def test_update_metadata_on_archived_document_raises(db_session: Session) -> None:
    issuer = _seed_issuer(db_session)
    storage = FakeStorageClient()
    document = _upload(db_session, storage, issuer.id)
    research_document_service.archive_document(db_session, document.id, archived_by="tester")

    with pytest.raises(ResearchDocumentArchivedError):
        research_document_service.update_metadata(
            db_session, document.id, ResearchDocumentMetadataUpdate(title="Should not apply")
        )


def test_archive_is_idempotent_and_writes_exactly_one_audit_event(db_session: Session) -> None:
    issuer = _seed_issuer(db_session)
    storage = FakeStorageClient()
    document = _upload(db_session, storage, issuer.id)
    key = build_storage_key(issuer.id, document.id)

    first = research_document_service.archive_document(db_session, document.id, archived_by="a")
    second = research_document_service.archive_document(db_session, document.id, archived_by="b")

    assert first is not None
    assert first.is_archived is True
    assert second is not None
    assert second.archived_by == "a"  # unchanged by the second, idempotent call

    events = research_document_service.list_audit_events(db_session, document.id)
    archive_events = [e for e in events if e.event_type == "research_document_archived"]
    assert len(archive_events) == 1

    # The physical Storage object is never deleted by archiving.
    assert key in storage.objects


def test_get_download_url_mints_a_fresh_signed_url(db_session: Session) -> None:
    issuer = _seed_issuer(db_session)
    storage = FakeStorageClient()
    document = _upload(db_session, storage, issuer.id)

    result = research_document_service.get_download_url(db_session, storage, document.id)
    assert result is not None
    fetched_document, signed_url = result
    assert fetched_document.id == document.id
    assert signed_url.startswith("https://fake-storage.test/")


def test_get_download_url_returns_none_for_missing_document(db_session: Session) -> None:
    storage = FakeStorageClient()
    assert research_document_service.get_download_url(db_session, storage, uuid4()) is None


def test_get_download_url_force_download_appends_filename_param(db_session: Session) -> None:
    issuer = _seed_issuer(db_session)
    storage = FakeStorageClient()
    document = _upload(db_session, storage, issuer.id, original_filename="Credit Agreement.pdf")

    result = research_document_service.get_download_url(
        db_session, storage, document.id, force_download=True
    )
    assert result is not None
    _fetched_document, signed_url = result
    assert "download=Credit%20Agreement.pdf" in signed_url
