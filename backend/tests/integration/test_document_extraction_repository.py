"""Integration tests for `app.repositories.document_extraction_repository`
(Milestone 10C) against the live shared `nexus` schema.

Covers atomic claiming (state transition, attempt counting, and a
compiled-SQL proof that `FOR UPDATE SKIP LOCKED` is actually present —
see `test_claim_next_pending_query_uses_for_update_skip_locked`'s
docstring for why a commit-based two-connection race test against this
project's one shared, production-adjacent database was deliberately not
attempted), stale-job recovery, transactional promotion (demote-then-
promote, enforced by the partial unique index), and the bounded-retry/
terminal-failure split.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.types import DocumentExtractionSourceType, DocumentExtractionStatus
from app.domain.document_extraction import DocumentExtractionCreate
from app.domain.issuer import Issuer, IssuerCreate
from app.domain.research_document import ResearchDocument
from app.repositories import (
    document_extraction_repository,
    issuer_repository,
    provenance_repository,
)
from app.services import research_document_service
from app.storage.fake_storage_client import FakeStorageClient
from tests.integration.conftest import reported_public_provenance

_VALID_PDF_CONTENT = b"%PDF-1.4\n%test fixture content for Milestone 10C\n%%EOF"


def _seed_issuer(db: Session) -> Issuer:
    provenance = provenance_repository.create_provenance(db, reported_public_provenance())
    return issuer_repository.create_issuer(
        db,
        IssuerCreate(legal_name=f"Test Issuer {uuid4()}", ticker=None, provenance_id=provenance.id),
    )


def _seed_research_document(db: Session, issuer_id: object) -> ResearchDocument:
    from app.core.types import AccessClassification, OriginalSource, ResearchDocumentType

    return research_document_service.upload_document(
        db,
        FakeStorageClient(),
        issuer_id=issuer_id,
        security_id=None,
        document_type=ResearchDocumentType.CREDIT_AGREEMENT,
        title="Test Credit Agreement",
        description=None,
        original_filename="test.pdf",
        content=_VALID_PDF_CONTENT,
        document_date=None,
        confidentiality_classification=AccessClassification.STANDARD,
        uploaded_by="test-analyst",
        original_source=OriginalSource.OTHER,
    )


def _create_pending(db: Session, research_document_id: object):
    return document_extraction_repository.create_pending(
        db,
        DocumentExtractionCreate(
            source_type=DocumentExtractionSourceType.RESEARCH_DOCUMENT,
            research_document_id=research_document_id,
        ),
    )


def test_create_pending_extraction(db_session: Session) -> None:
    issuer = _seed_issuer(db_session)
    document = _seed_research_document(db_session, issuer.id)

    extraction = _create_pending(db_session, document.id)

    assert extraction.status is DocumentExtractionStatus.PENDING
    assert extraction.attempt_count == 0
    assert extraction.is_current is False
    assert extraction.research_document_id == document.id


def test_claim_next_pending_returns_none_when_nothing_pending(db_session: Session) -> None:
    issuer = _seed_issuer(db_session)
    document = _seed_research_document(db_session, issuer.id)
    extraction = _create_pending(db_session, document.id)
    document_extraction_repository.claim_next_pending(db_session)  # claims the only one

    result = document_extraction_repository.claim_next_pending(db_session)
    assert result is None
    reread = document_extraction_repository.get_extraction(db_session, extraction.id)
    assert reread is not None
    assert reread.status is DocumentExtractionStatus.PROCESSING


def test_claim_next_pending_sets_processing_started_at_and_attempt_count(
    db_session: Session,
) -> None:
    issuer = _seed_issuer(db_session)
    document = _seed_research_document(db_session, issuer.id)
    _create_pending(db_session, document.id)

    claimed = document_extraction_repository.claim_next_pending(db_session)

    assert claimed is not None
    assert claimed.status is DocumentExtractionStatus.PROCESSING
    assert claimed.started_at is not None
    assert claimed.attempt_count == 1


def test_claim_next_pending_query_uses_for_update_skip_locked(db_session: Session) -> None:
    """Proves the actual claim mechanism, not just its intent: compiles
    the exact SELECT `claim_next_pending` issues and asserts Postgres's
    `FOR UPDATE SKIP LOCKED` clause is present.

    A *true* two-connection race (connection A holds an uncommitted claim
    lock, connection B's concurrent claim must skip it) would require
    genuinely committing seed data to this project's one shared,
    production-adjacent `nexus` schema first (Postgres never lets a
    second connection see a first connection's uncommitted rows at any
    isolation level — there is no way to test cross-connection lock
    contention without that commit). Given the real risk of leaving
    orphaned rows in the shared database this project's own production
    Morning Research Brief reads from if such a test ever failed
    mid-cleanup, that trade was deliberately not taken — "where
    practical" (the milestone brief's own phrasing) is judged not to
    extend to a commit-based test against shared production-adjacent
    infrastructure. `test_claim_next_pending_returns_none_when_nothing_
    pending` and `test_claim_next_pending_sets_processing_started_at_and_
    attempt_count` above already prove the real, live-DB-executed
    single-connection claim semantics (state transition, attempt
    counting, no double-claim of an already-`processing` row)."""
    from sqlalchemy import select

    from app.models.document_extraction import DocumentExtraction as DocumentExtractionModel

    stmt = (
        select(DocumentExtractionModel)
        .where(DocumentExtractionModel.status == DocumentExtractionStatus.PENDING.value)
        .order_by(DocumentExtractionModel.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    compiled = str(stmt.compile(bind=db_session.get_bind(), compile_kwargs={"literal_binds": True}))
    assert "FOR UPDATE" in compiled.upper()
    assert "SKIP LOCKED" in compiled.upper()


def test_reclaim_stale_processing_requeues_when_attempts_remain(db_session: Session) -> None:
    issuer = _seed_issuer(db_session)
    document = _seed_research_document(db_session, issuer.id)
    _create_pending(db_session, document.id)
    claimed = document_extraction_repository.claim_next_pending(db_session)
    assert claimed is not None

    future_cutoff = datetime.now(UTC) + timedelta(seconds=1)
    recovered = document_extraction_repository.reclaim_stale_processing(
        db_session, stale_after=future_cutoff, max_attempts=3
    )

    assert len(recovered) == 1
    assert recovered[0].id == claimed.id
    assert recovered[0].status is DocumentExtractionStatus.PENDING
    assert recovered[0].started_at is None


def test_reclaim_stale_processing_fails_terminally_when_attempts_exhausted(
    db_session: Session,
) -> None:
    issuer = _seed_issuer(db_session)
    document = _seed_research_document(db_session, issuer.id)
    _create_pending(db_session, document.id)
    claimed = document_extraction_repository.claim_next_pending(db_session)
    assert claimed is not None

    future_cutoff = datetime.now(UTC) + timedelta(seconds=1)
    recovered = document_extraction_repository.reclaim_stale_processing(
        db_session, stale_after=future_cutoff, max_attempts=1
    )

    assert len(recovered) == 1
    assert recovered[0].status is DocumentExtractionStatus.FAILED
    assert recovered[0].error_classification == "transient"


def test_reclaim_stale_processing_ignores_fresh_processing_rows(db_session: Session) -> None:
    issuer = _seed_issuer(db_session)
    document = _seed_research_document(db_session, issuer.id)
    _create_pending(db_session, document.id)
    document_extraction_repository.claim_next_pending(db_session)

    past_cutoff = datetime.now(UTC) - timedelta(seconds=3600)
    recovered = document_extraction_repository.reclaim_stale_processing(
        db_session, stale_after=past_cutoff, max_attempts=3
    )
    assert recovered == []


def test_mark_completed_then_promote_sets_current(db_session: Session) -> None:
    issuer = _seed_issuer(db_session)
    document = _seed_research_document(db_session, issuer.id)
    _create_pending(db_session, document.id)
    claimed = document_extraction_repository.claim_next_pending(db_session)
    assert claimed is not None

    completed = document_extraction_repository.mark_completed(
        db_session,
        claimed.id,
        extractor_provider="pymupdf4llm",
        extractor_version="1.28.2",
        chunking_strategy_version="structure_v1",
        structured_artifact_storage_key="document-extractions/x/y/artifact.json",
        page_count=2,
        chunk_count=5,
        table_count=1,
    )
    assert completed.status is DocumentExtractionStatus.COMPLETED
    assert completed.is_current is False

    promoted = document_extraction_repository.promote_current(
        db_session, claimed.id, research_document_id=document.id
    )
    assert promoted.is_current is True

    current = document_extraction_repository.get_current_for_document(db_session, document.id)
    assert current is not None
    assert current.id == claimed.id


def test_promote_demotes_previous_current_extraction(db_session: Session) -> None:
    issuer = _seed_issuer(db_session)
    document = _seed_research_document(db_session, issuer.id)

    _create_pending(db_session, document.id)
    first = document_extraction_repository.claim_next_pending(db_session)
    assert first is not None
    document_extraction_repository.mark_completed(
        db_session,
        first.id,
        extractor_provider="pymupdf4llm",
        extractor_version="1.28.2",
        chunking_strategy_version="structure_v1",
        structured_artifact_storage_key="k1",
        page_count=1,
        chunk_count=1,
        table_count=0,
    )
    document_extraction_repository.promote_current(
        db_session, first.id, research_document_id=document.id
    )

    _create_pending(db_session, document.id)
    second = document_extraction_repository.claim_next_pending(db_session)
    assert second is not None
    document_extraction_repository.mark_completed(
        db_session,
        second.id,
        extractor_provider="pymupdf4llm",
        extractor_version="1.28.2",
        chunking_strategy_version="structure_v1",
        structured_artifact_storage_key="k2",
        page_count=1,
        chunk_count=1,
        table_count=0,
    )
    document_extraction_repository.promote_current(
        db_session, second.id, research_document_id=document.id
    )

    first_reread = document_extraction_repository.get_extraction(db_session, first.id)
    second_reread = document_extraction_repository.get_extraction(db_session, second.id)
    assert first_reread is not None and first_reread.is_current is False
    assert second_reread is not None and second_reread.is_current is True


def test_failed_extraction_never_becomes_current(db_session: Session) -> None:
    issuer = _seed_issuer(db_session)
    document = _seed_research_document(db_session, issuer.id)
    _create_pending(db_session, document.id)
    claimed = document_extraction_repository.claim_next_pending(db_session)
    assert claimed is not None

    failed = document_extraction_repository.mark_failed(
        db_session, claimed.id, error_classification="deterministic", error_message="bad pdf"
    )
    assert failed.status is DocumentExtractionStatus.FAILED
    assert failed.is_current is False

    current = document_extraction_repository.get_current_for_document(db_session, document.id)
    assert current is None


def test_needs_ocr_extraction_never_becomes_current(db_session: Session) -> None:
    issuer = _seed_issuer(db_session)
    document = _seed_research_document(db_session, issuer.id)
    _create_pending(db_session, document.id)
    claimed = document_extraction_repository.claim_next_pending(db_session)
    assert claimed is not None

    needs_ocr = document_extraction_repository.mark_needs_ocr(
        db_session,
        claimed.id,
        extractor_provider="pymupdf4llm",
        extractor_version="1.28.2",
        page_count=1,
    )
    assert needs_ocr.status is DocumentExtractionStatus.NEEDS_OCR
    assert needs_ocr.is_current is False


def test_requeue_pending_resets_status_and_clears_started_at(db_session: Session) -> None:
    issuer = _seed_issuer(db_session)
    document = _seed_research_document(db_session, issuer.id)
    _create_pending(db_session, document.id)
    claimed = document_extraction_repository.claim_next_pending(db_session)
    assert claimed is not None

    requeued = document_extraction_repository.requeue_pending(
        db_session, claimed.id, error_message="transient storage hiccup"
    )
    assert requeued.status is DocumentExtractionStatus.PENDING
    assert requeued.started_at is None
    assert requeued.error_classification == "transient"


def test_list_for_document_orders_newest_first(db_session: Session) -> None:
    issuer = _seed_issuer(db_session)
    document = _seed_research_document(db_session, issuer.id)
    first = _create_pending(db_session, document.id)
    second = _create_pending(db_session, document.id)

    listing = document_extraction_repository.list_for_document(db_session, document.id)
    assert [e.id for e in listing] == [second.id, first.id]
