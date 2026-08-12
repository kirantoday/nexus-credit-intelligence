"""Integration tests for `app/repositories/research_document_repository.py`
(PLAN.md 4.10; Milestone 10B) against the live shared `nexus` schema.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.types import (
    AccessClassification,
    DataClassification,
    OriginalSource,
    ProviderName,
    ResearchDocumentType,
    TransformationType,
)
from app.domain.issuer import Issuer, IssuerCreate
from app.domain.provenance import ProvenanceCreate
from app.domain.raw_provider_payload import RawProviderPayloadCreate
from app.domain.research_document import ResearchDocumentCreate, ResearchDocumentMetadataUpdate
from app.repositories import (
    issuer_repository,
    provenance_repository,
    raw_provider_payload_repository,
    research_document_repository,
)
from tests.integration.conftest import reported_public_provenance


def _seed_issuer(db: Session, *, legal_name: str = "Trinseo PLC (Test)") -> Issuer:
    provenance = provenance_repository.create_provenance(db, reported_public_provenance())
    return issuer_repository.create_issuer(
        db, IssuerCreate(legal_name=legal_name, ticker=None, provenance_id=provenance.id)
    )


def _seed_document_create(
    db: Session, issuer_id: object, **overrides: object
) -> ResearchDocumentCreate:
    now = datetime.now(UTC)
    payload = raw_provider_payload_repository.create_payload(
        db,
        RawProviderPayloadCreate(
            provider=ProviderName.ADMIN_UPLOAD,
            source_record_id="test-doc-1",
            request_fingerprint="research_document:test-doc-1",
            storage_object_path="research-documents/test/test.pdf",
            retrieved_at=now,
            checksum="deadbeef",
            content_type="application/pdf",
            size_bytes=1234,
        ),
    )
    provenance = provenance_repository.create_provenance(
        db,
        ProvenanceCreate(
            provider=ProviderName.ADMIN_UPLOAD,
            original_source=OriginalSource.OTHER,
            source_attested_by="demo-analyst",
            source_attested_at=now,
            source_record_id="test-doc-1",
            as_of_date=date.today(),
            retrieved_at=now,
            transformation=TransformationType.REPORTED,
            classification=DataClassification.PUBLIC,
            raw_payload_id=payload.id,
        ),
    )
    raw_provider_payload_repository.link_provenance(db, payload.id, provenance.id)

    defaults: dict[str, object] = dict(
        id=uuid4(),
        issuer_id=issuer_id,
        document_type=ResearchDocumentType.CREDIT_AGREEMENT,
        title="Test Credit Agreement",
        original_filename="credit-agreement.pdf",
        raw_payload_id=payload.id,
        confidentiality_classification=AccessClassification.STANDARD,
        uploaded_by="demo-analyst",
        provenance_id=provenance.id,
    )
    defaults.update(overrides)
    return ResearchDocumentCreate(**defaults)  # type: ignore[arg-type]


def test_create_and_get_document(db_session: Session) -> None:
    issuer = _seed_issuer(db_session)
    data = _seed_document_create(db_session, issuer.id)
    document = research_document_repository.create_document(db_session, data)

    fetched = research_document_repository.get_document(db_session, document.id)
    assert fetched is not None
    assert fetched.title == "Test Credit Agreement"
    assert fetched.document_type is ResearchDocumentType.CREDIT_AGREEMENT
    assert fetched.is_archived is False
    assert fetched.extracted_text is None


def test_list_documents_filters_by_issuer_and_returns_issuer_display_fields(
    db_session: Session,
) -> None:
    issuer_a = _seed_issuer(db_session, legal_name="Issuer A (Test)")
    issuer_b = _seed_issuer(db_session, legal_name="Issuer B (Test)")
    research_document_repository.create_document(
        db_session, _seed_document_create(db_session, issuer_a.id, title="Doc A")
    )
    research_document_repository.create_document(
        db_session, _seed_document_create(db_session, issuer_b.id, title="Doc B")
    )

    results = research_document_repository.list_documents(db_session, issuer_id=issuer_a.id)
    assert len(results) == 1
    document, legal_name, _ticker = results[0]
    assert document.title == "Doc A"
    assert legal_name == "Issuer A (Test)"


def test_list_documents_filters_by_document_type(db_session: Session) -> None:
    issuer = _seed_issuer(db_session)
    research_document_repository.create_document(
        db_session,
        _seed_document_create(
            db_session,
            issuer.id,
            title="Agreement",
            document_type=ResearchDocumentType.CREDIT_AGREEMENT,
        ),
    )
    research_document_repository.create_document(
        db_session,
        _seed_document_create(
            db_session,
            issuer.id,
            title="Memo",
            document_type=ResearchDocumentType.INTERNAL_RESEARCH_MEMO,
        ),
    )

    results = research_document_repository.list_documents(
        db_session, issuer_id=issuer.id, document_type=ResearchDocumentType.INTERNAL_RESEARCH_MEMO
    )
    assert len(results) == 1
    assert results[0][0].title == "Memo"


def test_list_documents_excludes_archived_by_default(db_session: Session) -> None:
    issuer = _seed_issuer(db_session)
    document = research_document_repository.create_document(
        db_session, _seed_document_create(db_session, issuer.id)
    )
    research_document_repository.archive_document(db_session, document.id, archived_by="tester")

    assert research_document_repository.list_documents(db_session, issuer_id=issuer.id) == []
    included = research_document_repository.list_documents(
        db_session, issuer_id=issuer.id, include_archived=True
    )
    assert len(included) == 1


def test_apply_metadata_update_changes_only_supplied_fields(db_session: Session) -> None:
    issuer = _seed_issuer(db_session)
    document = research_document_repository.create_document(
        db_session, _seed_document_create(db_session, issuer.id, description="original description")
    )

    updated = research_document_repository.apply_metadata_update(
        db_session, document.id, ResearchDocumentMetadataUpdate(title="Renamed Agreement")
    )
    assert updated is not None
    assert updated.title == "Renamed Agreement"
    assert updated.description == "original description"


def test_archive_document_is_idempotent_at_repository_level(db_session: Session) -> None:
    issuer = _seed_issuer(db_session)
    document = research_document_repository.create_document(
        db_session, _seed_document_create(db_session, issuer.id)
    )

    first = research_document_repository.archive_document(db_session, document.id, archived_by="a")
    assert first is not None
    assert first.is_archived is True

    second = research_document_repository.archive_document(db_session, document.id, archived_by="b")
    assert second is None
