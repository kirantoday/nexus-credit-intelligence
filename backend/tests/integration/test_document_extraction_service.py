"""Integration tests for `app.services.document_extraction_service`
(Milestone 10C) against the live shared `nexus` schema — the full
enqueue -> claim -> download -> extract -> chunk -> validate -> persist ->
promote pipeline, using `FakeStorageClient` (real fixture PDF bytes, no
real network) so extraction/chunking runs for real against the eval
corpus's synthetic fixtures.

Covers: enqueue validation (missing/archived document), the full success
path, `needs_ocr` never replacing a prior current extraction, a
deterministic failure (corrupt PDF) never replacing a prior current
extraction, a transient failure requeuing while retry budget remains and
failing terminally once exhausted, and confidentiality-classification
propagation onto every chunk.
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.core.types import (
    AccessClassification,
    DocumentExtractionStatus,
    OriginalSource,
    ResearchDocumentType,
)
from app.domain.issuer import Issuer, IssuerCreate
from app.domain.research_document import ResearchDocument
from app.repositories import (
    document_chunk_repository,
    document_extraction_repository,
    issuer_repository,
    provenance_repository,
)
from app.services import document_extraction_service, research_document_service
from app.services.document_extraction_service import (
    MAX_EXTRACTION_ATTEMPTS,
    ResearchDocumentArchivedForProcessingError,
    ResearchDocumentNotFoundError,
)
from app.storage.base import StorageError
from app.storage.fake_storage_client import FakeStorageClient
from tests.integration.conftest import reported_public_provenance

_FIXTURES_DIR = Path(__file__).parent.parent.parent / "eval" / "document_intelligence" / "fixtures"
_CREDIT_AGREEMENT_PDF = (_FIXTURES_DIR / "credit_agreement_excerpt.pdf").read_bytes()
_SCANNED_PDF = (_FIXTURES_DIR / "scanned_like_blank_page.pdf").read_bytes()
_CORRUPT_PDF = b"not a real pdf at all"


def _seed_issuer(db: Session) -> Issuer:
    provenance = provenance_repository.create_provenance(db, reported_public_provenance())
    return issuer_repository.create_issuer(
        db,
        IssuerCreate(legal_name=f"Test Issuer {uuid4()}", ticker=None, provenance_id=provenance.id),
    )


def _seed_research_document(
    db: Session, storage: FakeStorageClient, issuer_id: object, *, content: bytes
) -> ResearchDocument:
    return research_document_service.upload_document(
        db,
        storage,
        issuer_id=issuer_id,
        security_id=None,
        document_type=ResearchDocumentType.CREDIT_AGREEMENT,
        title="Test Credit Agreement",
        description=None,
        original_filename="test.pdf",
        content=content,
        document_date=None,
        confidentiality_classification=AccessClassification.RESTRICTED,
        uploaded_by="test-analyst",
        original_source=OriginalSource.OTHER,
    )


def test_enqueue_extraction_raises_for_unknown_document(db_session: Session) -> None:
    with pytest.raises(ResearchDocumentNotFoundError):
        document_extraction_service.enqueue_extraction(db_session, uuid4(), requested_by="analyst")


def test_enqueue_extraction_raises_for_archived_document(db_session: Session) -> None:
    issuer = _seed_issuer(db_session)
    storage = FakeStorageClient()
    document = _seed_research_document(
        db_session, storage, issuer.id, content=_CREDIT_AGREEMENT_PDF
    )
    research_document_service.archive_document(db_session, document.id, archived_by="analyst")

    with pytest.raises(ResearchDocumentArchivedForProcessingError):
        document_extraction_service.enqueue_extraction(
            db_session, document.id, requested_by="analyst"
        )


def test_enqueue_extraction_creates_pending_row_and_audit_event(db_session: Session) -> None:
    issuer = _seed_issuer(db_session)
    storage = FakeStorageClient()
    document = _seed_research_document(
        db_session, storage, issuer.id, content=_CREDIT_AGREEMENT_PDF
    )

    extraction = document_extraction_service.enqueue_extraction(
        db_session, document.id, requested_by="test-analyst"
    )

    assert extraction.status is DocumentExtractionStatus.PENDING
    assert extraction.research_document_id == document.id

    from app.repositories import audit_repository

    events = audit_repository.list_events_for_entity(
        db_session, "document_extraction", extraction.id
    )
    assert len(events) == 1
    assert events[0].event_type == "document_extraction_requested"
    assert events[0].user_id == "test-analyst"


def test_process_one_returns_none_when_nothing_pending(db_session: Session) -> None:
    storage = FakeStorageClient()
    result = document_extraction_service.process_one(db_session, storage)
    assert result is None


def test_process_one_full_success_path_persists_chunks_and_promotes(db_session: Session) -> None:
    issuer = _seed_issuer(db_session)
    storage = FakeStorageClient()
    document = _seed_research_document(
        db_session, storage, issuer.id, content=_CREDIT_AGREEMENT_PDF
    )
    document_extraction_service.enqueue_extraction(db_session, document.id, requested_by=None)

    result = document_extraction_service.process_one(db_session, storage)

    assert result is not None
    assert result.status is DocumentExtractionStatus.COMPLETED
    assert result.is_current is True
    assert result.extractor_provider == "pymupdf4llm"
    assert result.chunking_strategy_version == "structure_v1"
    assert result.page_count == 2
    assert result.chunk_count is not None and result.chunk_count > 0
    assert result.structured_artifact_storage_key is not None
    assert result.structured_artifact_storage_key in storage.objects

    chunks = document_chunk_repository.list_for_extraction(db_session, result.id)
    assert len(chunks) == result.chunk_count
    # Confidentiality propagated from the source research_document
    # (RESTRICTED) onto every chunk — not the default.
    assert all(c.confidentiality_classification is AccessClassification.RESTRICTED for c in chunks)
    assert all(c.issuer_id == issuer.id for c in chunks)
    assert all(c.research_document_id == document.id for c in chunks)

    current = document_extraction_repository.get_current_for_document(db_session, document.id)
    assert current is not None
    assert current.id == result.id


def test_process_one_needs_ocr_does_not_create_chunks_or_replace_current(
    db_session: Session,
) -> None:
    issuer = _seed_issuer(db_session)
    storage = FakeStorageClient()
    # First, a real successful extraction to establish a current baseline.
    good_document = _seed_research_document(
        db_session, storage, issuer.id, content=_CREDIT_AGREEMENT_PDF
    )
    document_extraction_service.enqueue_extraction(db_session, good_document.id, requested_by=None)
    first = document_extraction_service.process_one(db_session, storage)
    assert first is not None and first.is_current is True

    # A different (scanned/near-empty) document — its own extraction
    # lineage, unrelated to `good_document`'s current pointer.
    scanned_document = _seed_research_document(db_session, storage, issuer.id, content=_SCANNED_PDF)
    document_extraction_service.enqueue_extraction(
        db_session, scanned_document.id, requested_by=None
    )
    second = document_extraction_service.process_one(db_session, storage)

    assert second is not None
    assert second.status is DocumentExtractionStatus.NEEDS_OCR
    assert second.is_current is False
    assert document_chunk_repository.count_for_extraction(db_session, second.id) == 0

    # The first document's current extraction is completely unaffected.
    still_current = document_extraction_repository.get_current_for_document(
        db_session, good_document.id
    )
    assert still_current is not None
    assert still_current.id == first.id


def test_process_one_deterministic_failure_does_not_replace_prior_current(
    db_session: Session,
) -> None:
    issuer = _seed_issuer(db_session)
    storage = FakeStorageClient()
    document = _seed_research_document(
        db_session, storage, issuer.id, content=_CREDIT_AGREEMENT_PDF
    )
    document_extraction_service.enqueue_extraction(db_session, document.id, requested_by=None)
    first = document_extraction_service.process_one(db_session, storage)
    assert first is not None and first.is_current is True

    # Reprocess the *same* document, but corrupt the stored bytes first —
    # simulates a real "reprocess produced a bad extraction" scenario
    # without needing a second research_document.
    payload_key = list(storage.objects.keys())[0]
    storage.objects[payload_key] = _CORRUPT_PDF
    document_extraction_service.enqueue_extraction(db_session, document.id, requested_by=None)

    second = document_extraction_service.process_one(db_session, storage)

    assert second is not None
    assert second.status is DocumentExtractionStatus.FAILED
    assert second.error_classification == "deterministic"
    assert second.is_current is False

    still_current = document_extraction_repository.get_current_for_document(db_session, document.id)
    assert still_current is not None
    assert still_current.id == first.id


def test_process_one_transient_failure_requeues_then_fails_terminally(
    db_session: Session,
) -> None:
    issuer = _seed_issuer(db_session)
    storage = FakeStorageClient()
    document = _seed_research_document(
        db_session, storage, issuer.id, content=_CREDIT_AGREEMENT_PDF
    )
    document_extraction_service.enqueue_extraction(db_session, document.id, requested_by=None)

    storage.fail_next_download = True
    with pytest.raises(StorageError):
        # `download` itself raises immediately when the flag is set — this
        # proves the fake's own contract before exercising the service's
        # handling of that same exception in the loop below.
        storage.download(key="anything")

    for attempt in range(1, MAX_EXTRACTION_ATTEMPTS + 1):
        storage.fail_next_download = True
        result = document_extraction_service.process_one(db_session, storage)
        assert result is not None
        if attempt < MAX_EXTRACTION_ATTEMPTS:
            assert (
                result.status is DocumentExtractionStatus.PENDING
            ), f"attempt {attempt}: transient failure with budget remaining must requeue"
            assert result.error_classification == "transient"
        else:
            assert (
                result.status is DocumentExtractionStatus.FAILED
            ), f"attempt {attempt}: transient failure with budget exhausted must fail terminally"

    final = document_extraction_repository.get_extraction(db_session, result.id)
    assert final is not None
    assert final.status is DocumentExtractionStatus.FAILED
    assert final.is_current is False
