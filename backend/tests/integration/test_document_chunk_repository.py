"""Integration tests for `app.repositories.document_chunk_repository`
(Milestone 10C) against the live shared `nexus` schema — bulk creation,
listing in ordinal order, and the internal lexical `search_chunks`
capability (plain Postgres full-text search, mirroring Milestone 12A's
existing primitive)."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.types import AccessClassification, DocumentChunkElementType
from app.domain.document_chunk import DocumentChunkCreate
from app.domain.issuer import Issuer, IssuerCreate
from app.domain.research_document import ResearchDocument
from app.repositories import document_chunk_repository, issuer_repository, provenance_repository
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
    from app.core.types import OriginalSource, ResearchDocumentType

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


def _chunk_create(
    *, extraction_id: object, document_id: object, issuer_id: object, index: int, content: str
) -> DocumentChunkCreate:
    return DocumentChunkCreate(
        document_extraction_id=extraction_id,  # type: ignore[arg-type]
        research_document_id=document_id,  # type: ignore[arg-type]
        issuer_id=issuer_id,  # type: ignore[arg-type]
        chunk_index=index,
        element_type=DocumentChunkElementType.TEXT,
        content=content,
        confidentiality_classification=AccessClassification.STANDARD,
    )


def _seed_extraction_id(db: Session, document_id: object) -> object:
    from app.core.types import DocumentExtractionSourceType
    from app.domain.document_extraction import DocumentExtractionCreate
    from app.repositories import document_extraction_repository

    extraction = document_extraction_repository.create_pending(
        db,
        DocumentExtractionCreate(
            source_type=DocumentExtractionSourceType.RESEARCH_DOCUMENT,
            research_document_id=document_id,  # type: ignore[arg-type]
        ),
    )
    return extraction.id


def test_create_chunks_bulk_and_list_in_ordinal_order(db_session: Session) -> None:
    issuer = _seed_issuer(db_session)
    document = _seed_research_document(db_session, issuer.id)
    extraction_id = _seed_extraction_id(db_session, document.id)

    created = document_chunk_repository.create_chunks(
        db_session,
        [
            _chunk_create(
                extraction_id=extraction_id,
                document_id=document.id,
                issuer_id=issuer.id,
                index=i,
                content=f"Chunk number {i} about restricted payments and covenants.",
            )
            for i in range(5)
        ],
    )
    assert len(created) == 5

    listed = document_chunk_repository.list_for_extraction(db_session, extraction_id)
    assert [c.chunk_index for c in listed] == [0, 1, 2, 3, 4]
    assert all(c.confidentiality_classification is AccessClassification.STANDARD for c in listed)
    assert all(c.issuer_id == issuer.id for c in listed)


def test_count_for_extraction(db_session: Session) -> None:
    issuer = _seed_issuer(db_session)
    document = _seed_research_document(db_session, issuer.id)
    extraction_id = _seed_extraction_id(db_session, document.id)
    document_chunk_repository.create_chunks(
        db_session,
        [
            _chunk_create(
                extraction_id=extraction_id,
                document_id=document.id,
                issuer_id=issuer.id,
                index=i,
                content=f"content {i}",
            )
            for i in range(3)
        ],
    )
    assert document_chunk_repository.count_for_extraction(db_session, extraction_id) == 3


def test_search_chunks_finds_matching_phrase(db_session: Session) -> None:
    issuer = _seed_issuer(db_session)
    document = _seed_research_document(db_session, issuer.id)
    extraction_id = _seed_extraction_id(db_session, document.id)
    document_chunk_repository.create_chunks(
        db_session,
        [
            _chunk_create(
                extraction_id=extraction_id,
                document_id=document.id,
                issuer_id=issuer.id,
                index=0,
                content="The Borrower shall not permit any Restricted Payment except as "
                "permitted under the Available Amount basket.",
            ),
            _chunk_create(
                extraction_id=extraction_id,
                document_id=document.id,
                issuer_id=issuer.id,
                index=1,
                content="Revenue of $412.3 million, up 6.2% year-over-year.",
            ),
        ],
    )

    matches = document_chunk_repository.search_chunks(
        db_session, extraction_id, query="restricted payment"
    )
    assert len(matches) == 1
    assert "Restricted Payment" in matches[0].content

    no_matches = document_chunk_repository.search_chunks(
        db_session, extraction_id, query="nonexistent phrase xyz"
    )
    assert no_matches == []


def test_search_chunks_scoped_to_one_extraction_only(db_session: Session) -> None:
    issuer = _seed_issuer(db_session)
    document = _seed_research_document(db_session, issuer.id)
    extraction_a = _seed_extraction_id(db_session, document.id)
    extraction_b = _seed_extraction_id(db_session, document.id)
    document_chunk_repository.create_chunks(
        db_session,
        [
            _chunk_create(
                extraction_id=extraction_a,
                document_id=document.id,
                issuer_id=issuer.id,
                index=0,
                content="covenant language about leverage ratio",
            )
        ],
    )
    document_chunk_repository.create_chunks(
        db_session,
        [
            _chunk_create(
                extraction_id=extraction_b,
                document_id=document.id,
                issuer_id=issuer.id,
                index=0,
                content="covenant language about leverage ratio",
            )
        ],
    )

    matches_a = document_chunk_repository.search_chunks(db_session, extraction_a, query="covenant")
    matches_b = document_chunk_repository.search_chunks(db_session, extraction_b, query="covenant")
    assert len(matches_a) == 1
    assert len(matches_b) == 1
    assert matches_a[0].document_extraction_id == extraction_a
    assert matches_b[0].document_extraction_id == extraction_b
