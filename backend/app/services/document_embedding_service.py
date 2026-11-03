"""Document embedding orchestration (Milestone 10D.2, ADR-021).

Two entry points with different execution contexts, mirroring
`document_extraction_service`:

`enqueue_embedding` validates and creates a `pending` job. It never calls a
provider and never commits (the caller owns the transaction).

`process_next_job` runs inside the standalone worker script
(`app.scripts.run_document_embedding_worker`), never inside a request. It
claims one job and runs `app.embeddings.processor.run_job` against
`SqlJobStore`, which commits at each unit of work.

This service never touches `document_extraction_service` or the extraction
worker: embedding failure cannot affect extraction status, and extraction
success is the only thing a job's eligibility reads from it.

Logging contract: ids, counts, status, and reason codes only. Never chunk
text, document titles, queries, vectors, or raw vendor/driver messages.
"""

from __future__ import annotations

import logging
import random
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.core.types import (
    AuditEventType,
    DataClassification,
    EmbeddingInputType,
    ProviderName,
    TransformationType,
)
from app.domain.audit import AuditEventCreate
from app.domain.document_chunk_embedding import ChunkEmbeddingUpsert
from app.domain.document_embedding_job import DocumentEmbeddingJob, DocumentEmbeddingJobCreate
from app.domain.embedding_call_log import EmbeddingCallLogCreate
from app.domain.provenance import (
    CalculationCreate,
    CalculationInputCreate,
    ProvenanceCreate,
)
from app.embeddings.base import EmbeddingProvider
from app.embeddings.budget import EmbeddingRunBudget
from app.embeddings.dimensions import EmbeddingModelSpec
from app.embeddings.fingerprint import EMBEDDING_INPUT_TEMPLATE_VERSION, build_embedding_input
from app.embeddings.processor import (
    ChunkToEmbed,
    JobContext,
    JobResult,
    PersistCounts,
    PersistItem,
    ProcessorConfig,
    run_job,
)
from app.embeddings.scheduling import Clock, Jitter, plan_transient_retry, utc_now
from app.repositories import (
    audit_repository,
    document_chunk_embedding_repository,
    document_chunk_repository,
    document_embedding_job_repository,
    document_extraction_repository,
    embedding_call_log_repository,
    provenance_repository,
    public_document_approval_repository,
    research_document_repository,
)
from app.retrieval.eligibility import (
    PUBLIC_ALLOWLIST_SCOPE,
    EligibilityDecision,
    EligibilityReason,
    RetrievalScope,
)

logger = logging.getLogger(__name__)

_ENTITY_TABLE = "document_embedding_job"
_WORKER_RUN_TABLE = "embedding_worker_run"
_CALCULATION_METHOD = "document_chunk_embedding"

# Value the provider's policy acknowledgement must equal, by provider. A
# provider absent from this table has no acknowledgement requirement (`fake`).
_REQUIRED_ACKNOWLEDGEMENT = {"openai": "openai:text-embedding-3-large"}


class DocumentExtractionNotFoundError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class PolicyObservation:
    """What the process *observed*, never what the owner *accepted*.

    - `acknowledgement_observed` is the configured environment string.
    - `acknowledgement_matches_required` is a string comparison, nothing more.
    - `policy_reference_observed` is an identifier or hash of a durable owner
      policy record, copied from configuration; it is **not verified** here.
    - `asserted_actor` is a free-text name given on the command line. There is
      no authentication, so it is recorded as unverified.
    An audit event holding these facts is evidence, not permission.
    """

    provider: str
    model_id: str
    nexus_config_version: str
    dimension: int
    acknowledgement_required: bool
    acknowledgement_observed: str | None
    acknowledgement_matches_required: bool
    policy_reference_observed: str | None
    asserted_actor: str | None


def policy_observation(
    settings: Any, spec: EmbeddingModelSpec, *, asserted_actor: str | None
) -> PolicyObservation:
    required = _REQUIRED_ACKNOWLEDGEMENT.get(spec.provider)
    observed = getattr(settings, "embedding_external_policy_approval", None) or None
    reference = (getattr(settings, "embedding_policy_reference", None) or "").strip() or None
    return PolicyObservation(
        provider=spec.provider,
        model_id=spec.model_id,
        nexus_config_version=spec.model_version,
        dimension=spec.dimension,
        acknowledgement_required=required is not None,
        acknowledgement_observed=observed,
        acknowledgement_matches_required=required is not None and observed == required,
        policy_reference_observed=reference,
        asserted_actor=asserted_actor,
    )


def _policy_fields(policy: PolicyObservation) -> dict[str, object]:
    """Audit fields only: no key, text, vector, URL or response body."""
    return {
        "provider": policy.provider,
        "embedding_model": policy.model_id,
        "nexus_config_version": policy.nexus_config_version,
        "dimension": policy.dimension,
        "policy_acknowledgement_required": policy.acknowledgement_required,
        "policy_acknowledgement_observed": policy.acknowledgement_observed,
        "policy_acknowledgement_matches_required": policy.acknowledgement_matches_required,
        "policy_acknowledgement_source": "environment_variable",
        "policy_reference_observed": policy.policy_reference_observed,
        "policy_reference_verified": False,
        "owner_acceptance_verified": False,
        "asserted_actor": policy.asserted_actor,
        "identity_verified": False,
    }


class DocumentNotEligibleError(Exception):
    """The (document, extraction) pair is not eligible for external
    embedding. Carries the machine-readable reason, never document
    content."""

    def __init__(self, reason: EligibilityReason) -> None:
        self.reason = reason
        super().__init__(f"document is not eligible for embedding: {reason.value}")


def enqueue_embedding(
    db: Session,
    *,
    document_extraction_id: uuid.UUID,
    spec: EmbeddingModelSpec,
    requested_by: str | None,
    scope: RetrievalScope = PUBLIC_ALLOWLIST_SCOPE,
    policy: PolicyObservation | None = None,
) -> DocumentEmbeddingJob:
    """Eligibility check #1 of 4 (enqueue). Idempotent: if an active job
    already exists for this (extraction, model, version) it is returned
    instead of creating a second one — the partial unique index enforces
    the same rule in the database.

    When `policy` is given, its observed provider/model/version/dimension and
    policy facts are written to the audit event **in the same transaction as
    the job**: if the audit write fails the exception propagates and the
    caller rolls back, so no job is left queued without its audit record."""
    extraction = document_extraction_repository.get_extraction(db, document_extraction_id)
    if extraction is None or extraction.research_document_id is None:
        raise DocumentExtractionNotFoundError(
            f"document_extraction {document_extraction_id} not found"
        )

    facts = public_document_approval_repository.load_eligibility_facts(
        db,
        research_document_id=extraction.research_document_id,
        document_extraction_id=document_extraction_id,
    )
    decision = scope.evaluate(facts)
    if not decision.eligible:
        raise DocumentNotEligibleError(decision.reason)

    existing = document_embedding_job_repository.get_active_job(
        db,
        document_extraction_id=document_extraction_id,
        embedding_model=spec.model_id,
        model_version=spec.model_version,
    )
    if existing is not None:
        return existing

    job = document_embedding_job_repository.create_pending(
        db,
        DocumentEmbeddingJobCreate(
            research_document_id=extraction.research_document_id,
            document_extraction_id=document_extraction_id,
            embedding_provider=spec.provider,
            embedding_model=spec.model_id,
            embedding_model_version=spec.model_version,
            dimension=spec.dimension,
            requested_by=requested_by,
        ),
    )
    audit_repository.create_event(
        db,
        AuditEventCreate(
            user_id=requested_by,
            event_type=AuditEventType.DOCUMENT_EMBEDDING_REQUESTED.value,
            entity_table=_ENTITY_TABLE,
            entity_id=job.id,
            before_state=None,
            after_state={
                "document_extraction_id": str(document_extraction_id),
                "embedding_model": spec.model_id,
                "embedding_model_version": spec.model_version,
                **(_policy_fields(policy) if policy is not None else {}),
            },
        ),
    )
    return job


def record_worker_started(
    db: Session,
    *,
    run_id: uuid.UUID,
    policy: PolicyObservation,
    limits: dict[str, object],
) -> None:
    """Audit event written **and committed** before any provider request.
    `commit()` returning means the row is durable; if it raises, the caller
    must make no provider call. Records observations only (see
    `PolicyObservation`)."""
    try:
        audit_repository.create_event(
            db,
            AuditEventCreate(
                user_id=policy.asserted_actor,
                event_type=AuditEventType.EMBEDDING_WORKER_STARTED.value,
                entity_table=_WORKER_RUN_TABLE,
                entity_id=None,
                before_state=None,
                after_state={"run_id": str(run_id), "limits": limits, **_policy_fields(policy)},
            ),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise


def release_held_job(db: Session, *, job_id: uuid.UUID, released_by: str) -> DocumentEmbeddingJob:
    """Explicit operator release of a held job. Sends no request. The audit
    event is written in the same transaction as the release; the caller
    commits. `released_by` is an asserted, unverified name."""
    held = document_embedding_job_repository.get_job(db, job_id)
    job = document_embedding_job_repository.release_held(db, job_id, released_by=released_by)
    audit_repository.create_event(
        db,
        AuditEventCreate(
            user_id=released_by,
            event_type=AuditEventType.EMBEDDING_JOB_RELEASED.value,
            entity_table=_ENTITY_TABLE,
            entity_id=job.id,
            before_state={"status": "held", "hold_reason": held.hold_reason if held else None},
            after_state={
                "status": job.status.value,
                "provider": job.embedding_provider,
                "embedding_model": job.embedding_model,
                "attempt_count": job.attempt_count,
                "asserted_actor": released_by,
                "identity_verified": False,
            },
        ),
    )
    return job


def reclaim_stale_jobs(
    db: Session,
    *,
    stale_after_seconds: int,
    max_attempts: int,
    clock: Clock = utc_now,
    jitter: Jitter = random.random,
) -> list[DocumentEmbeddingJob]:
    """Called at the start of every worker invocation, by the holder of the
    exclusive worker lock. A normal run with nothing stale is a cheap no-op.

    A `processing` row older than the threshold belongs to a dead worker. It
    returns to `pending` **after a backoff delay** (never immediately) unless
    its attempts are spent. `held` jobs are not `processing` and are never
    touched. The dead worker may already have sent a request, so recovery is
    at-least-once: the same batch can be sent, and billed, twice."""
    now = clock()
    stale_after = now - timedelta(seconds=stale_after_seconds)
    delay = plan_transient_retry(1, now=now, jitter=jitter)
    recovered = document_embedding_job_repository.reclaim_stale_processing(
        db, stale_after=stale_after, max_attempts=max_attempts, retry_not_before=delay.not_before
    )
    db.commit()
    if recovered:
        logger.warning(
            "reclaim_stale_jobs: recovered %d stale processing embedding job(s): %s",
            len(recovered),
            [str(job.id) for job in recovered],
        )
    return recovered


def count_chunks_needing_embedding(
    db: Session, *, document_extraction_id: uuid.UUID, document_title: str, spec: EmbeddingModelSpec
) -> int:
    """How many chunks of this extraction have no stored vector, or a
    stored vector whose fingerprint no longer matches what would be sent
    today (for example after a title edit). Needs no provider call. A
    positive count is what a stale-embedding reconcile would act on."""
    from app.embeddings.fingerprint import compute_fingerprint

    stored = document_chunk_embedding_repository.get_fingerprints_for_extraction(
        db,
        document_extraction_id=document_extraction_id,
        model=spec.model_id,
        version=spec.model_version,
    )
    needing = 0
    for chunk in document_chunk_repository.list_for_extraction(db, document_extraction_id):
        fingerprint = compute_fingerprint(
            embedded_text=build_embedding_input(
                document_title=document_title,
                section_path=chunk.section_path,
                content=chunk.content,
            ),
            input_type=EmbeddingInputType.DOCUMENT,
            model_id=spec.model_id,
            model_version=spec.model_version,
            dimension=spec.dimension,
        )
        if stored.get(chunk.id) != fingerprint:
            needing += 1
    return needing


class SqlJobStore:
    """Production `JobStore`: Postgres via the repositories. Every write
    commits its own unit of work; any failure inside one rolls back that
    unit and re-raises for the processor to classify."""

    def __init__(self, db: Session, *, scope: RetrievalScope = PUBLIC_ALLOWLIST_SCOPE) -> None:
        self._db = db
        self._scope = scope

    def check_eligibility(self, job: JobContext) -> EligibilityDecision:
        facts = public_document_approval_repository.load_eligibility_facts(
            self._db,
            research_document_id=job.research_document_id,
            document_extraction_id=job.document_extraction_id,
        )
        return self._scope.evaluate(facts)

    def list_chunks(self, job: JobContext) -> list[ChunkToEmbed]:
        return [
            ChunkToEmbed(
                chunk_id=chunk.id,
                chunk_index=chunk.chunk_index,
                section_path=chunk.section_path,
                content=chunk.content,
            )
            for chunk in document_chunk_repository.list_for_extraction(
                self._db, job.document_extraction_id
            )
        ]

    def existing_fingerprints(
        self, job: JobContext, spec: EmbeddingModelSpec
    ) -> dict[uuid.UUID, str]:
        return document_chunk_embedding_repository.get_fingerprints_for_extraction(
            self._db,
            document_extraction_id=job.document_extraction_id,
            model=spec.model_id,
            version=spec.model_version,
        )

    def record_call(
        self,
        job: JobContext,
        *,
        spec: EmbeddingModelSpec,
        purpose: EmbeddingInputType,
        batch_size: int,
        input_tokens: int | None,
        estimated_cost_usd: float | None,
        latency_ms: int,
        success: bool,
        error_classification: str | None,
    ) -> None:
        try:
            embedding_call_log_repository.create_call_log(
                self._db,
                EmbeddingCallLogCreate(
                    job_id=job.job_id,
                    purpose=purpose,
                    provider=spec.provider,
                    model=spec.model_id,
                    model_version=spec.model_version,
                    batch_size=batch_size,
                    input_tokens=input_tokens,
                    estimated_cost_usd=estimated_cost_usd,
                    latency_ms=latency_ms,
                    success=success,
                    retry_count=max(0, job.attempt_count - 1),
                    error_classification=error_classification,
                ),
            )
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise

    def persist_batch(
        self, job: JobContext, spec: EmbeddingModelSpec, items: Sequence[PersistItem]
    ) -> PersistCounts:
        try:
            provenance_id = self._ensure_job_provenance(job, spec)
            counts = document_chunk_embedding_repository.upsert_batch(
                self._db,
                job_id=job.job_id,
                provenance_id=provenance_id,
                model=spec.model_id,
                version=spec.model_version,
                dimension=spec.dimension,
                items=[
                    ChunkEmbeddingUpsert(
                        chunk_id=item.chunk_id,
                        content_fingerprint=item.fingerprint,
                        vector=item.vector,
                    )
                    for item in items
                ],
            )
            document_embedding_job_repository.add_progress(
                self._db, job.job_id, embedded=counts.inserted, replaced=counts.replaced
            )
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise
        return PersistCounts(
            inserted=counts.inserted, replaced=counts.replaced, unchanged=counts.unchanged
        )

    def mark_completed(self, job: JobContext, *, chunk_total: int) -> None:
        self._db.rollback()
        document_embedding_job_repository.mark_completed(
            self._db, job.job_id, chunk_total=chunk_total
        )
        self._db.commit()

    def requeue(
        self,
        job: JobContext,
        *,
        error_classification: str | None,
        error_message: str | None,
        note: str,
        refund_attempt: bool,
        retry_not_before: datetime | None = None,
        provider_wide: bool = False,
    ) -> None:
        self._db.rollback()
        document_embedding_job_repository.requeue_pending(
            self._db,
            job.job_id,
            error_classification=error_classification,
            error_message=error_message,
            note=note,
            refund_attempt=refund_attempt,
            retry_not_before=retry_not_before,
            provider_wide=provider_wide,
        )
        self._db.commit()

    def hold(
        self,
        job: JobContext,
        *,
        reason: str,
        provider_wide: bool,
        error_classification: str | None,
        error_message: str | None,
        refund_attempt: bool,
    ) -> None:
        """The hold and its audit event commit together. Reason code only:
        no provider response text is stored or audited."""
        self._db.rollback()
        try:
            held = document_embedding_job_repository.hold_job(
                self._db,
                job.job_id,
                reason=reason,
                provider_wide=provider_wide,
                error_classification=error_classification,
                error_message=error_message,
                refund_attempt=refund_attempt,
            )
            audit_repository.create_event(
                self._db,
                AuditEventCreate(
                    user_id=None,
                    event_type=AuditEventType.EMBEDDING_JOB_HELD.value,
                    entity_table=_ENTITY_TABLE,
                    entity_id=held.id,
                    before_state=None,
                    after_state={
                        "status": held.status.value,
                        "hold_reason": reason,
                        "provider_wide": provider_wide,
                        "provider": held.embedding_provider,
                        "embedding_model": held.embedding_model,
                        "attempt_count": held.attempt_count,
                    },
                ),
            )
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise

    def mark_failed(
        self, job: JobContext, *, error_classification: str, error_message: str
    ) -> None:
        self._db.rollback()
        document_embedding_job_repository.mark_failed(
            self._db,
            job.job_id,
            error_classification=error_classification,
            error_message=error_message,
        )
        self._db.commit()

    def mark_blocked(self, job: JobContext, *, reason: str) -> None:
        self._db.rollback()
        document_embedding_job_repository.mark_blocked(self._db, job.job_id, reason=reason)
        self._db.commit()

    def _ensure_job_provenance(self, job: JobContext, spec: EmbeddingModelSpec) -> uuid.UUID:
        """One `provenance` record per job (ADR-021), using the same
        calculated/AI-generated shape `alert_synthesis_service` uses for
        AI-derived artifacts: the calculation's input is the source
        document's own provenance. Created lazily with the first persisted
        batch so every embedding row can reference it; set by
        compare-and-set so concurrent batches converge on one id (a lost
        race leaves one orphaned, harmless, append-only provenance row)."""
        current = document_embedding_job_repository.get_job(self._db, job.job_id)
        assert current is not None
        if current.provenance_id is not None:
            return current.provenance_id

        document = research_document_repository.get_document(self._db, job.research_document_id)
        assert document is not None
        calculation = provenance_repository.create_calculation(
            self._db,
            CalculationCreate(
                method=_CALCULATION_METHOD,
                formula_note=(
                    f"Vector embeddings of document chunks computed by provider "
                    f"'{spec.provider}', model '{spec.model_id}' version "
                    f"'{spec.model_version}' ({spec.dimension} dimensions), input template "
                    f"'{EMBEDDING_INPUT_TEMPLATE_VERSION}'. Derived data: not a reported fact."
                ),
            ),
            inputs=[
                CalculationInputCreate(
                    provenance_id=document.provenance_id,
                    input_role="source_document",
                    sequence_number=0,
                )
            ],
        )
        now = datetime.now(UTC)
        provenance = provenance_repository.create_provenance(
            self._db,
            ProvenanceCreate(
                provider=ProviderName.AI_GENERATED,
                source_record_id=str(job.job_id),
                source_url=None,
                as_of_date=now.date(),
                retrieved_at=now,
                transformation=TransformationType.CALCULATED,
                classification=DataClassification.AI_EXTRACTED,
                calculation_id=calculation.id,
            ),
        )
        return document_embedding_job_repository.set_provenance_if_unset(
            self._db, job.job_id, provenance.id
        )


def process_next_job(
    db: Session,
    *,
    provider: EmbeddingProvider,
    spec: EmbeddingModelSpec,
    budget: EmbeddingRunBudget,
    config: ProcessorConfig,
    scope: RetrievalScope = PUBLIC_ALLOWLIST_SCOPE,
) -> JobResult | None:
    """Claims and fully processes at most one *due* pending job for this
    worker's provider/model/version. `None` means nothing was claimable: no
    pending job, every pending job is delayed, or a provider-wide delay or hold
    applies (the normal, expected outcome most invocations)."""
    claimed = document_embedding_job_repository.claim_next_pending(
        db,
        provider=spec.provider,
        model=spec.model_id,
        model_version=spec.model_version,
        now=config.clock(),
    )
    if claimed is None:
        db.commit()
        return None
    db.commit()

    document = research_document_repository.get_document(db, claimed.research_document_id)
    store = SqlJobStore(db, scope=scope)
    context = JobContext(
        job_id=claimed.id,
        research_document_id=claimed.research_document_id,
        document_extraction_id=claimed.document_extraction_id,
        # A document that vanished is handled by the eligibility check
        # inside the processor (DOCUMENT_NOT_FOUND -> blocked), not here.
        document_title=document.title if document is not None else "",
        attempt_count=claimed.attempt_count,
    )
    result = run_job(
        context, store=store, provider=provider, spec=spec, budget=budget, config=config
    )
    logger.info(
        "embedding job %s: outcome=%s embedded=%d replaced=%d unchanged=%d tokens=%d note=%s",
        claimed.id,
        result.outcome.value,
        result.embedded,
        result.replaced,
        result.unchanged,
        result.tokens_used,
        result.note,
    )
    return result
