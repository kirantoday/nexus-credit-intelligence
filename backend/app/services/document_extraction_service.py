"""Document Intelligence extraction/chunking orchestration (Milestone 10C).

Two entry points with genuinely different execution contexts:

`enqueue_extraction` runs inside a FastAPI request — it validates, creates
a `pending` row, and returns immediately. It never performs extraction
itself (the milestone's explicit "no inline extraction in the HTTP
request" requirement) and never calls `db.commit()` — `get_db`'s
per-request commit handles that, matching every other service in this
codebase.

`process_one` runs inside the standalone worker script
(`app.scripts.run_document_extraction_worker`), never inside a request —
it calls `db.commit()`/`db.rollback()` itself at clear transaction
boundaries, mirroring `market_discovery_service.run_discovery`'s identical
pattern for the same reason (a script, not a request, owns its own unit
of work).

Pipeline for one claimed extraction: claim -> download source bytes from
Storage -> extract -> detect needs_ocr -> chunk -> validate -> persist
(structured artifact to Storage, chunks to Postgres) -> promote current.
Every step is wrapped in an OpenTelemetry span
(`app.observability.tracing.document_intelligence_span`) carrying
`extraction_id` as the correlation attribute.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.types import (
    AuditEventType,
    DocumentExtractionErrorClass,
    DocumentExtractionSourceType,
)
from app.domain.audit import AuditEventCreate
from app.domain.document_chunk import DocumentChunkCreate
from app.domain.document_extraction import DocumentExtraction, DocumentExtractionCreate
from app.extraction.base import ExtractedPage, ExtractionFailure, ExtractionResult
from app.extraction.chunker import CHUNKING_STRATEGY_VERSION, chunk_extraction
from app.extraction.pymupdf4llm_extractor import PyMuPDF4LLMExtractor
from app.extraction.validation import detect_needs_ocr, validate_chunks
from app.observability.tracing import document_intelligence_span
from app.repositories import (
    audit_repository,
    document_chunk_repository,
    document_extraction_repository,
    raw_provider_payload_repository,
    research_document_repository,
)
from app.storage.base import StorageClient, StorageError

logger = logging.getLogger(__name__)

_ENTITY_TABLE = "document_extraction"

# Bounded retry (2026-08-13 incident: never repeat the unbounded-retry-
# assumption mistake). A transient failure (Storage/network) is retried up
# to this many attempts before being marked terminally `failed`; a
# deterministic failure (corrupt/unsupported PDF, needs_ocr) is never
# retried regardless of this ceiling.
MAX_EXTRACTION_ATTEMPTS = 3

# A `processing` row older than this is presumed to belong to a worker
# that died mid-attempt (container restart/redeploy) — reclaimed by
# `reclaim_stale_jobs`, never left stuck forever.
STALE_PROCESSING_AFTER_SECONDS = 900

_STORAGE_KEY_PREFIX = "document-extractions"


class ResearchDocumentNotFoundError(Exception):
    pass


class ResearchDocumentArchivedForProcessingError(Exception):
    """Archived research documents are read-only for new writes (mirrors
    `research_document_service`'s identical posture for metadata edits) —
    processing creates new `document_extraction`/`document_chunk` rows, so
    it is refused the same way."""

    def __init__(self, document_id: UUID) -> None:
        self.document_id = document_id
        super().__init__(f"research_document {document_id} is archived and cannot be processed")


def _structured_artifact_key(research_document_id: UUID, extraction_id: UUID) -> str:
    return f"{_STORAGE_KEY_PREFIX}/{research_document_id}/{extraction_id}/artifact.json"


def _extraction_result_to_json(result: ExtractionResult) -> bytes:
    payload = {
        "extractor_provider": result.extractor_provider,
        "extractor_version": result.extractor_version,
        "pages": [
            {"page_number": page.page_number, "markdown_text": page.markdown_text}
            for page in result.pages
        ],
    }
    return json.dumps(payload).encode("utf-8")


def _extraction_result_from_json(raw: bytes) -> ExtractionResult:
    """The inverse of `_extraction_result_to_json` — not called anywhere
    in 10C (no re-chunk-from-artifact feature is implemented this
    milestone), kept alongside its encoder so the round-trip is proven
    correct now rather than assumed for whichever 10D+ milestone needs it
    (see the structured-artifact test in
    `tests/unit/test_document_extraction_service.py`)."""
    data = json.loads(raw.decode("utf-8"))
    return ExtractionResult(
        pages=[
            ExtractedPage(page_number=p["page_number"], markdown_text=p["markdown_text"])
            for p in data["pages"]
        ],
        extractor_provider=data["extractor_provider"],
        extractor_version=data["extractor_version"],
    )


def enqueue_extraction(
    db: Session, research_document_id: UUID, *, requested_by: str | None
) -> DocumentExtraction:
    document = research_document_repository.get_document(db, research_document_id)
    if document is None:
        raise ResearchDocumentNotFoundError(f"research_document {research_document_id} not found")
    if document.is_archived:
        raise ResearchDocumentArchivedForProcessingError(research_document_id)

    extraction = document_extraction_repository.create_pending(
        db,
        DocumentExtractionCreate(
            source_type=DocumentExtractionSourceType.RESEARCH_DOCUMENT,
            research_document_id=research_document_id,
        ),
    )
    with document_intelligence_span(
        "document_intelligence.enqueue",
        extraction_id=extraction.id,
        source_type=DocumentExtractionSourceType.RESEARCH_DOCUMENT.value,
    ):
        audit_repository.create_event(
            db,
            AuditEventCreate(
                user_id=requested_by,
                event_type=AuditEventType.DOCUMENT_EXTRACTION_REQUESTED.value,
                entity_table=_ENTITY_TABLE,
                entity_id=extraction.id,
                before_state=None,
                after_state={
                    "research_document_id": str(research_document_id),
                    "status": extraction.status.value,
                },
            ),
        )
    return extraction


def _classify_error(exc: Exception) -> DocumentExtractionErrorClass:
    if isinstance(exc, StorageError):
        return DocumentExtractionErrorClass.TRANSIENT
    if isinstance(exc, ExtractionFailure):
        return DocumentExtractionErrorClass.DETERMINISTIC
    # Unknown failure shape: assume deterministic rather than blindly
    # retrying an unrecognized error forever (2026-08-13 incident's
    # governing lesson, applied here even though the failure mode itself
    # is unrelated).
    return DocumentExtractionErrorClass.DETERMINISTIC


def _fail_or_requeue(
    db: Session, extraction: DocumentExtraction, exc: Exception
) -> DocumentExtraction:
    error_class = _classify_error(exc)
    error_message = f"{type(exc).__name__}: {exc}"
    if (
        error_class is DocumentExtractionErrorClass.TRANSIENT
        and extraction.attempt_count < MAX_EXTRACTION_ATTEMPTS
    ):
        logger.warning(
            "document_extraction %s: transient failure (attempt %d/%d), requeued: %s",
            extraction.id,
            extraction.attempt_count,
            MAX_EXTRACTION_ATTEMPTS,
            error_message,
        )
        result = document_extraction_repository.requeue_pending(
            db, extraction.id, error_message=error_message
        )
    else:
        logger.error(
            "document_extraction %s: terminal failure (%s, attempt %d): %s",
            extraction.id,
            error_class.value,
            extraction.attempt_count,
            error_message,
        )
        result = document_extraction_repository.mark_failed(
            db,
            extraction.id,
            error_classification=error_class.value,
            error_message=error_message,
        )
    db.commit()
    return result


def process_one(db: Session, storage_client: StorageClient) -> DocumentExtraction | None:
    """Claims and fully processes at most one pending extraction. Returns
    `None` if no extraction was pending (the worker's normal, expected
    outcome most invocations)."""
    with document_intelligence_span(
        "document_intelligence.worker_claim", extraction_id=None
    ) as span:
        extraction = document_extraction_repository.claim_next_pending(db)
        if extraction is None:
            span.set_attribute("claimed", False)
            db.commit()
            return None
        span.set_attribute("claimed", True)
        span.set_attribute("extraction_id", str(extraction.id))
        db.commit()

    assert extraction.research_document_id is not None
    research_document_id = extraction.research_document_id

    try:
        document = research_document_repository.get_document(db, research_document_id)
        if document is None:
            raise ExtractionFailure(f"research_document {research_document_id} vanished")
        payload = raw_provider_payload_repository.get_payload(db, document.raw_payload_id)
        if payload is None or payload.storage_object_path is None:
            raise ExtractionFailure(
                f"research_document {research_document_id} has no storage object on file"
            )

        with document_intelligence_span(
            "document_intelligence.storage_download", extraction_id=extraction.id
        ):
            source_bytes = storage_client.download(key=payload.storage_object_path)

        with document_intelligence_span(
            "document_intelligence.extract",
            extraction_id=extraction.id,
            source_type=extraction.source_type.value,
        ) as span:
            result = PyMuPDF4LLMExtractor().extract(source_bytes, content_type="application/pdf")
            span.set_attribute("extractor_provider", result.extractor_provider)
            span.set_attribute("extractor_version", result.extractor_version)
            span.set_attribute("page_count", result.page_count)

        if detect_needs_ocr(result):
            with document_intelligence_span(
                "document_intelligence.validate", extraction_id=extraction.id, needs_ocr=True
            ):
                pass
            completed = document_extraction_repository.mark_needs_ocr(
                db,
                extraction.id,
                extractor_provider=result.extractor_provider,
                extractor_version=result.extractor_version,
                page_count=result.page_count,
            )
            db.commit()
            return completed

        with document_intelligence_span(
            "document_intelligence.chunk",
            extraction_id=extraction.id,
            chunking_strategy_version=CHUNKING_STRATEGY_VERSION,
        ) as span:
            drafts = chunk_extraction(result)
            span.set_attribute("chunk_count", len(drafts))

        with document_intelligence_span(
            "document_intelligence.validate", extraction_id=extraction.id
        ) as span:
            validation = validate_chunks(drafts)
            span.set_attribute("passed", validation.passed)
            if not validation.passed:
                raise ExtractionFailure(f"chunk validation failed: {validation.reason}")

        table_count = sum(1 for d in drafts if d.element_type.value == "table")

        with document_intelligence_span(
            "document_intelligence.persist",
            extraction_id=extraction.id,
            chunk_count=len(drafts),
            table_count=table_count,
        ):
            artifact_key = _structured_artifact_key(research_document_id, extraction.id)
            storage_client.upload(
                key=artifact_key,
                content=_extraction_result_to_json(result),
                content_type="application/json",
            )
            document_chunk_repository.create_chunks(
                db,
                [
                    DocumentChunkCreate(
                        document_extraction_id=extraction.id,
                        research_document_id=research_document_id,
                        issuer_id=document.issuer_id,
                        chunk_index=draft.chunk_index,
                        element_type=draft.element_type,
                        content=draft.content,
                        page_start=draft.page_start,
                        page_end=draft.page_end,
                        section_path=draft.section_path,
                        section_title=draft.section_title,
                        token_count=draft.token_count,
                        confidentiality_classification=document.confidentiality_classification,
                    )
                    for draft in drafts
                ],
            )
            document_extraction_repository.mark_completed(
                db,
                extraction.id,
                extractor_provider=result.extractor_provider,
                extractor_version=result.extractor_version,
                chunking_strategy_version=CHUNKING_STRATEGY_VERSION,
                structured_artifact_storage_key=artifact_key,
                page_count=result.page_count,
                chunk_count=len(drafts),
                table_count=table_count,
            )

        with document_intelligence_span(
            "document_intelligence.promote", extraction_id=extraction.id
        ):
            promoted = document_extraction_repository.promote_current(
                db, extraction.id, research_document_id=research_document_id
            )
        db.commit()
        return promoted

    except Exception as exc:  # noqa: BLE001 - classified and persisted, never silent
        db.rollback()
        # `extraction` (the claim result) is stale after rollback — reload
        # its current row so `_fail_or_requeue` sees the real attempt_count.
        current = document_extraction_repository.get_extraction(db, extraction.id)
        assert current is not None
        return _fail_or_requeue(db, current, exc)


def reclaim_stale_jobs(db: Session) -> list[DocumentExtraction]:
    """Called at the start of every worker invocation, before claiming new
    work — bounded, cheap, and safe to run every time (a normal invocation
    with nothing stale is a no-op query)."""
    stale_after = datetime.now(UTC) - timedelta(seconds=STALE_PROCESSING_AFTER_SECONDS)
    recovered = document_extraction_repository.reclaim_stale_processing(
        db, stale_after=stale_after, max_attempts=MAX_EXTRACTION_ATTEMPTS
    )
    db.commit()
    if recovered:
        logger.warning(
            "reclaim_stale_jobs: recovered %d stale processing extraction(s): %s",
            len(recovered),
            [str(r.id) for r in recovered],
        )
    return recovered
