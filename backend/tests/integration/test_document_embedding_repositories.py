"""Gated integration tests for the Milestone 10D.2 repositories and
database constraints.

**These did not run as part of the 10D.2 local implementation.** They need
the shared Supabase `nexus` schema with draft migrations 0021/0022 applied
(a separately approved step) and an explicit `NEXUS_ALLOW_EMBEDDING_DB_TESTS=1`
— see `embedding_db_guard`. They are the only tests that can prove the
upsert SQL, the partial unique indexes, the claim query, and the CHECK
constraints; the unit tests deliberately do not claim to.
"""

from __future__ import annotations

import pytest
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.core.types import (
    EmbeddingInputType,
    EmbeddingJobStatus,
    PageReferenceBasis,
)
from app.domain.document_chunk_embedding import ChunkEmbeddingUpsert
from app.domain.document_embedding_job import DocumentEmbeddingJobCreate
from app.domain.embedding_call_log import EmbeddingCallLogCreate
from app.domain.public_document_approval import PublicDocumentApprovalCreate
from app.repositories import (
    document_chunk_embedding_repository,
    document_chunk_repository,
    document_embedding_job_repository,
    document_extraction_repository,
    embedding_call_log_repository,
    provenance_repository,
    public_document_approval_repository,
    research_document_repository,
)
from app.retrieval.eligibility import EligibilityReason, evaluate_eligibility
from tests.integration.conftest import reported_public_provenance
from tests.integration.embedding_db_guard import embedding_db_session  # noqa: F401
from tests.integration.test_document_chunk_repository import (
    _chunk_create,
    _seed_extraction_id,
    _seed_issuer,
    _seed_research_document,
)

_SHA = "e" * 64
_DIM = 1024


def _vector(value: float = 0.01) -> list[float]:
    return [value] * _DIM


def _seed_current_extraction(db: Session, document_id: object) -> object:
    extraction_id = _seed_extraction_id(db, document_id)
    document_extraction_repository.mark_completed(
        db,
        extraction_id,  # type: ignore[arg-type]
        extractor_provider="test",
        extractor_version="1",
        chunking_strategy_version="test",
        structured_artifact_storage_key="test/key",
        page_count=1,
        chunk_count=2,
        table_count=0,
    )
    document_extraction_repository.promote_current(
        db, extraction_id, research_document_id=document_id  # type: ignore[arg-type]
    )
    return extraction_id


def _approval(document_id: object, checksum: str) -> PublicDocumentApprovalCreate:
    return PublicDocumentApprovalCreate(
        research_document_id=document_id,  # type: ignore[arg-type]
        approved_raw_payload_checksum=checksum,
        source_url="https://example.test/original",
        page_reference_basis=PageReferenceBasis.ORIGINAL,
        approval_basis="integration test",
        approved_by="test-operator",
    )


def _payload_checksum(db: Session, document_id: object) -> str:
    from app.repositories import raw_provider_payload_repository

    document = research_document_repository.get_document(db, document_id)  # type: ignore[arg-type]
    assert document is not None
    payload = raw_provider_payload_repository.get_payload(db, document.raw_payload_id)
    assert payload is not None
    return payload.checksum


def test_only_one_active_approval_per_document_and_revocation_allows_a_new_one(
    embedding_db_session: Session,  # noqa: F811
) -> None:
    db = embedding_db_session
    document = _seed_research_document(db, _seed_issuer(db).id)
    first = public_document_approval_repository.create_approval(db, _approval(document.id, _SHA))

    with pytest.raises(IntegrityError), db.begin_nested():
        public_document_approval_repository.create_approval(db, _approval(document.id, _SHA))

    revoked = public_document_approval_repository.revoke_approval(
        db, first.id, revoked_by="test-operator"
    )
    assert revoked is not None and revoked.revoked_at is not None
    assert public_document_approval_repository.get_active_for_document(db, document.id) is None
    second = public_document_approval_repository.create_approval(db, _approval(document.id, _SHA))
    assert second.id != first.id


def test_eligibility_facts_follow_live_state_through_every_denial(
    embedding_db_session: Session,  # noqa: F811
) -> None:
    db = embedding_db_session
    document = _seed_research_document(db, _seed_issuer(db).id)
    extraction_id = _seed_current_extraction(db, document.id)

    def reason() -> EligibilityReason:
        facts = public_document_approval_repository.load_eligibility_facts(
            db,
            research_document_id=document.id,
            document_extraction_id=extraction_id,  # type: ignore[arg-type]
        )
        return evaluate_eligibility(facts).reason

    assert reason() is EligibilityReason.NOT_APPROVED  # 'standard' alone is not enough

    approval = public_document_approval_repository.create_approval(
        db, _approval(document.id, _payload_checksum(db, document.id))
    )
    assert reason() is EligibilityReason.ELIGIBLE

    from app.core.types import AccessClassification
    from app.domain.research_document import ResearchDocumentMetadataUpdate

    research_document_repository.apply_metadata_update(
        db,
        document.id,
        ResearchDocumentMetadataUpdate(
            confidentiality_classification=AccessClassification.RESTRICTED
        ),
    )
    assert reason() is EligibilityReason.NOT_STANDARD_CLASSIFICATION  # reclassified after approval
    research_document_repository.apply_metadata_update(
        db,
        document.id,
        ResearchDocumentMetadataUpdate(
            confidentiality_classification=AccessClassification.STANDARD
        ),
    )
    assert reason() is EligibilityReason.ELIGIBLE

    newer = _seed_current_extraction(db, document.id)  # supersedes the first extraction
    assert newer != extraction_id
    assert reason() is EligibilityReason.EXTRACTION_NOT_CURRENT

    research_document_repository.archive_document(db, document.id, archived_by="test")
    assert reason() is EligibilityReason.ARCHIVED

    public_document_approval_repository.revoke_approval(db, approval.id, revoked_by="test")
    assert reason() is EligibilityReason.NOT_APPROVED


def test_job_uniqueness_is_per_active_target_and_history_is_kept(
    embedding_db_session: Session,  # noqa: F811
) -> None:
    db = embedding_db_session
    document = _seed_research_document(db, _seed_issuer(db).id)
    extraction_id = _seed_current_extraction(db, document.id)
    create = DocumentEmbeddingJobCreate(
        research_document_id=document.id,
        document_extraction_id=extraction_id,  # type: ignore[arg-type]
        embedding_provider="fake",
        embedding_model="fake-embedding",
        embedding_model_version="fake-1",
        dimension=_DIM,
    )
    first = document_embedding_job_repository.create_pending(db, create)

    with pytest.raises(IntegrityError), db.begin_nested():
        document_embedding_job_repository.create_pending(db, create)

    document_embedding_job_repository.mark_completed(db, first.id, chunk_total=0)
    again = document_embedding_job_repository.create_pending(db, create)  # allowed after finishing
    assert again.id != first.id


def test_claim_increments_attempts_and_a_refunded_requeue_gives_it_back(
    embedding_db_session: Session,  # noqa: F811
) -> None:
    db = embedding_db_session
    document = _seed_research_document(db, _seed_issuer(db).id)
    extraction_id = _seed_current_extraction(db, document.id)
    job = document_embedding_job_repository.create_pending(
        db,
        DocumentEmbeddingJobCreate(
            research_document_id=document.id,
            document_extraction_id=extraction_id,  # type: ignore[arg-type]
            embedding_provider="fake",
            embedding_model="fake-embedding",
            embedding_model_version="fake-1",
            dimension=_DIM,
        ),
    )
    claimed = document_embedding_job_repository.claim_next_pending(db)
    assert claimed is not None and claimed.status is EmbeddingJobStatus.PROCESSING
    assert claimed.attempt_count == 1

    requeued = document_embedding_job_repository.requeue_pending(
        db,
        job.id,
        error_classification=None,
        error_message=None,
        note="budget_stop:token_budget_exhausted",
        refund_attempt=True,
    )
    assert requeued.status is EmbeddingJobStatus.PENDING and requeued.attempt_count == 0


def test_upsert_is_idempotent_replaces_in_place_and_rejects_a_wrong_width_vector(
    embedding_db_session: Session,  # noqa: F811
) -> None:
    db = embedding_db_session
    document = _seed_research_document(db, _seed_issuer(db).id)
    extraction_id = _seed_current_extraction(db, document.id)
    chunks = document_chunk_repository.create_chunks(
        db,
        [
            _chunk_create(
                extraction_id=extraction_id,
                document_id=document.id,
                issuer_id=document.issuer_id,
                index=i,
                content=f"synthetic passage {i}",
            )
            for i in range(2)
        ],
    )
    job = document_embedding_job_repository.create_pending(
        db,
        DocumentEmbeddingJobCreate(
            research_document_id=document.id,
            document_extraction_id=extraction_id,  # type: ignore[arg-type]
            embedding_provider="fake",
            embedding_model="fake-embedding",
            embedding_model_version="fake-1",
            dimension=_DIM,
        ),
    )
    provenance = provenance_repository.create_provenance(db, reported_public_provenance())

    def upsert(fingerprint: str, value: float = 0.01) -> tuple[int, int, int]:
        return tuple(  # type: ignore[return-value]
            document_chunk_embedding_repository.upsert_batch(
                db,
                job_id=job.id,
                provenance_id=provenance.id,
                model="fake-embedding",
                version="fake-1",
                dimension=_DIM,
                items=[
                    ChunkEmbeddingUpsert(
                        chunk_id=c.id, content_fingerprint=fingerprint, vector=_vector(value)
                    )
                    for c in chunks
                ],
            )
        )

    assert upsert("1" * 64) == (2, 0, 0)  # inserted
    assert upsert("1" * 64) == (0, 0, 2)  # identical rerun: no-op
    assert upsert("2" * 64, 0.02) == (0, 2, 0)  # changed fingerprint: replaced in place

    stored = document_chunk_embedding_repository.get_fingerprints_for_extraction(
        db,
        document_extraction_id=extraction_id,  # type: ignore[arg-type]
        model="fake-embedding",
        version="fake-1",
    )
    assert set(stored.values()) == {"2" * 64} and len(stored) == 2

    with pytest.raises(DBAPIError), db.begin_nested():
        document_chunk_embedding_repository.upsert_batch(
            db,
            job_id=job.id,
            provenance_id=provenance.id,
            model="other-model",
            version="v1",
            dimension=_DIM,
            items=[
                ChunkEmbeddingUpsert(
                    chunk_id=chunks[0].id, content_fingerprint="3" * 64, vector=[0.1, 0.2, 0.3]
                )
            ],
        )


def test_call_log_total_cost_is_unknown_when_any_successful_call_has_unknown_cost(
    embedding_db_session: Session,  # noqa: F811
) -> None:
    db = embedding_db_session

    document = _seed_research_document(db, _seed_issuer(db).id)
    extraction_id = _seed_current_extraction(db, document.id)
    job = document_embedding_job_repository.create_pending(
        db,
        DocumentEmbeddingJobCreate(
            research_document_id=document.id,
            document_extraction_id=extraction_id,  # type: ignore[arg-type]
            embedding_provider="fake",
            embedding_model="fake-embedding",
            embedding_model_version="fake-1",
            dimension=_DIM,
        ),
    )
    for success, cost, tokens in ((True, 0.01, 10), (False, None, None)):
        embedding_call_log_repository.create_call_log(
            db,
            EmbeddingCallLogCreate(
                job_id=job.id,
                purpose=EmbeddingInputType.DOCUMENT,
                provider="fake",
                model="fake-embedding",
                batch_size=2,
                input_tokens=tokens,
                estimated_cost_usd=cost,
                success=success,
            ),
        )
    known = embedding_call_log_repository.aggregate_for_job(db, job.id)
    assert known.total_calls == 2 and known.failed_calls == 1
    assert known.total_estimated_cost_usd == pytest.approx(0.01)  # failed call doesn't blank it

    embedding_call_log_repository.create_call_log(
        db,
        EmbeddingCallLogCreate(
            job_id=job.id,
            purpose=EmbeddingInputType.DOCUMENT,
            provider="fake",
            model="fake-embedding",
            batch_size=2,
            input_tokens=None,
            estimated_cost_usd=None,
            success=True,
        ),
    )
    unknown = embedding_call_log_repository.aggregate_for_job(db, job.id)
    assert unknown.total_estimated_cost_usd is None
    assert unknown.calls_with_unknown_tokens == 2
