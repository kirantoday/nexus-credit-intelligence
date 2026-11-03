"""Embedding job execution logic (Milestone 10D.2, ADR-021).

Pure orchestration of one *already claimed* job against a `JobStore` port:
eligibility -> fingerprint diff -> budgeted, batched provider calls ->
validated, transactional persistence. It contains every behavior the
milestone's correctness depends on (idempotency, safe replacement, bounded
retries, budget stops, ineligible-before-send), and imports nothing beyond
the standard library and sibling pure modules, so it is testable with an
in-memory store and the deterministic fake provider.

`app.services.document_embedding_service.SqlJobStore` is the production
adapter. Unit tests against an in-memory store prove this *logic*; they do
not prove the SQL (the upsert, the claim query, the CHECK constraints) —
that is what the gated integration tests are for.

**Behavior contract** (each point has a test):

- *Unchanged content, repeated runs*: a chunk whose stored fingerprint
  already equals the freshly computed one is skipped — no provider call.
- *Changed title/section/template or model version*: the fingerprint
  differs. Under the same model key the stored row is **replaced in place,
  in one statement, only after the new vector exists and validates**; a
  failure at any earlier point leaves the previous vector untouched. A new
  model version is a different unique key, so its vectors are inserted
  alongside the old ones, which are never deleted here.
- *Partial completion*: each batch is persisted and committed on its own.
  A later failure leaves earlier batches in place, and the retry's
  fingerprint diff naturally skips them.
- *Provider failure*: nothing is persisted for that batch; the failed call
  is recorded in the ledger; the job is requeued if the error is transient
  and attempts remain, otherwise failed.
- *Persistence failure after a successful call*: the spend is recorded in
  the ledger **before** persistence is attempted, so a rollback cannot hide
  cost; the retry re-sends that batch (and pays again, visibly).
- *Eligibility*: checked before any work and again immediately before every
  provider call. Ineligible work is blocked, never failed, never retried.
- *Budget*: checked before every call; exhausting it requeues the job
  without consuming an attempt.
- *Concurrent workers*: the claim guarantees one worker per job in the
  normal case. If a stale-reclaimed job is ever processed twice, the
  persistence upsert (unique key + fingerprint compare) makes the second
  writer's rows idempotent rather than duplicated.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from app.core.types import EmbeddingInputType
from app.embeddings.base import EmbeddingProvider
from app.embeddings.budget import EmbeddingRunBudget
from app.embeddings.dimensions import EmbeddingModelSpec, validate_result
from app.embeddings.errors import (
    EmbeddingAuthError,
    EmbeddingConfigurationError,
    EmbeddingDimensionMismatchError,
    EmbeddingError,
    EmbeddingPersistenceError,
    EmbeddingRateLimitError,
    classify,
    safe_summary,
)
from app.embeddings.fingerprint import build_embedding_input, compute_fingerprint, estimate_tokens
from app.embeddings.pricing import estimate_cost_usd
from app.retrieval.eligibility import EligibilityDecision

_PendingItem = tuple["ChunkToEmbed", str, str]


@dataclass(frozen=True, slots=True)
class JobContext:
    job_id: UUID
    research_document_id: UUID
    document_extraction_id: UUID
    document_title: str
    attempt_count: int


@dataclass(frozen=True, slots=True)
class ChunkToEmbed:
    chunk_id: UUID
    chunk_index: int
    section_path: str | None
    content: str


@dataclass(frozen=True, slots=True)
class PersistItem:
    chunk_id: UUID
    fingerprint: str
    vector: list[float]


@dataclass(frozen=True, slots=True)
class PersistCounts:
    inserted: int
    replaced: int
    unchanged: int


class JobStore(Protocol):
    """Everything the processor needs from persistence. Every method that
    writes commits its own unit of work."""

    def check_eligibility(self, job: JobContext) -> EligibilityDecision: ...

    def list_chunks(self, job: JobContext) -> list[ChunkToEmbed]: ...

    def existing_fingerprints(self, job: JobContext, spec: EmbeddingModelSpec) -> dict[UUID, str]:
        """chunk_id -> stored fingerprint, for this job's chunks under
        `spec`'s (model, version) key."""
        ...

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
    ) -> None: ...

    def persist_batch(
        self, job: JobContext, spec: EmbeddingModelSpec, items: Sequence[PersistItem]
    ) -> PersistCounts: ...

    def mark_completed(self, job: JobContext, *, chunk_total: int) -> None: ...

    def requeue(
        self,
        job: JobContext,
        *,
        error_classification: str | None,
        error_message: str | None,
        note: str,
        refund_attempt: bool,
    ) -> None: ...

    def mark_failed(
        self, job: JobContext, *, error_classification: str, error_message: str
    ) -> None: ...

    def mark_blocked(self, job: JobContext, *, reason: str) -> None: ...


class JobOutcome(StrEnum):
    COMPLETED = "completed"
    REQUEUED = "requeued"
    FAILED = "failed"
    BLOCKED_INELIGIBLE = "blocked_ineligible"


@dataclass(frozen=True, slots=True)
class ProcessorConfig:
    batch_size: int
    max_attempts: int


@dataclass(frozen=True, slots=True)
class JobResult:
    outcome: JobOutcome
    embedded: int = 0
    replaced: int = 0
    unchanged: int = 0
    tokens_used: int = 0
    note: str | None = None
    # True when continuing to the next job in this run would be pointless or
    # harmful (bad credentials, bad configuration, vendor rate limit).
    abort_run: bool = False
    # The vendor's requested wait after a rate limit, in seconds, when it gave
    # a numeric `Retry-After`. Informational only: the job queue has no
    # "not before" field, so nothing durable enforces this delay.
    retry_after_seconds: float | None = None


def process_job(
    job: JobContext,
    *,
    store: JobStore,
    provider: EmbeddingProvider,
    spec: EmbeddingModelSpec,
    budget: EmbeddingRunBudget,
    config: ProcessorConfig,
) -> JobResult:
    if (provider.provider_name, provider.model_id, provider.model_version, provider.dimension) != (
        spec.provider,
        spec.model_id,
        spec.model_version,
        spec.dimension,
    ):
        store.requeue(
            job,
            error_classification="deterministic",
            error_message="provider identity does not match the job's model spec",
            note="provider_spec_mismatch",
            refund_attempt=True,
        )
        return JobResult(JobOutcome.REQUEUED, note="provider_spec_mismatch", abort_run=True)

    decision = store.check_eligibility(job)
    if not decision.eligible:
        store.mark_blocked(job, reason=decision.reason.value)
        return JobResult(JobOutcome.BLOCKED_INELIGIBLE, note=decision.reason.value)

    chunks = store.list_chunks(job)
    existing = store.existing_fingerprints(job, spec)

    pending: list[tuple[ChunkToEmbed, str, str]] = []
    unchanged = 0
    for chunk in chunks:
        text = build_embedding_input(
            document_title=job.document_title,
            section_path=chunk.section_path,
            content=chunk.content,
        )
        fingerprint = compute_fingerprint(
            embedded_text=text,
            input_type=EmbeddingInputType.DOCUMENT,
            model_id=spec.model_id,
            model_version=spec.model_version,
            dimension=spec.dimension,
        )
        if existing.get(chunk.chunk_id) == fingerprint:
            unchanged += 1
        else:
            pending.append((chunk, text, fingerprint))

    embedded = 0
    replaced = 0
    tokens_used = 0
    batch_size = max(1, min(config.batch_size, provider.max_batch_size))

    for batch in _plan_batches(pending, batch_size=batch_size, provider=provider):
        texts = [text for _chunk, text, _fp in batch]

        estimated_tokens = sum(estimate_tokens(t) for t in texts)
        budget_decision = budget.check(
            estimated_tokens=estimated_tokens,
            estimated_cost_usd=estimate_cost_usd(
                provider=spec.provider, model_id=spec.model_id, input_tokens=estimated_tokens
            ),
        )
        if not budget_decision.allowed:
            store.requeue(
                job,
                error_classification=None,
                error_message=None,
                note=f"budget_stop:{budget_decision.reason}",
                refund_attempt=True,
            )
            return JobResult(
                JobOutcome.REQUEUED,
                embedded=embedded,
                replaced=replaced,
                unchanged=unchanged,
                tokens_used=tokens_used,
                note=f"budget_stop:{budget_decision.reason}",
            )

        # Re-check immediately before text leaves the system: the document
        # may have been archived, reclassified, superseded, or had its
        # approval revoked since the claim (or since the previous batch).
        decision = store.check_eligibility(job)
        if not decision.eligible:
            store.mark_blocked(job, reason=decision.reason.value)
            return JobResult(
                JobOutcome.BLOCKED_INELIGIBLE,
                embedded=embedded,
                replaced=replaced,
                unchanged=unchanged,
                tokens_used=tokens_used,
                note=decision.reason.value,
            )

        started = time.monotonic()
        try:
            result = provider.embed_documents(texts)
        except Exception as exc:  # noqa: BLE001 - classified; message never persisted
            attempted, possibly_billed, reported = _request_exposure(exc)
            reported_cost = estimate_cost_usd(
                provider=spec.provider, model_id=spec.model_id, input_tokens=reported
            )
            # Persisted evidence: tokens are the vendor's own count when a
            # rejected response carried a valid one, otherwise unknown (None).
            # An estimate is never written here as if it were actual usage.
            store.record_call(
                job,
                spec=spec,
                purpose=EmbeddingInputType.DOCUMENT,
                batch_size=len(texts),
                input_tokens=reported,
                estimated_cost_usd=reported_cost,
                latency_ms=_elapsed_ms(started),
                success=False,
                error_classification=classify(exc),
            )
            if attempted:
                # A request was actually issued, so it counts as a request
                # against the run budget. Tokens: the vendor's count if known;
                # else the batch estimate if it may have been billed (a
                # timeout after sending, a dropped connection, any HTTP error,
                # a response rejected locally); else none (never delivered).
                # A local conservative counter, not a provider-enforced cap.
                if reported is not None:
                    budget.record(tokens=reported, cost_usd=reported_cost)
                    tokens_used += reported
                elif possibly_billed:
                    budget.record(
                        tokens=estimated_tokens,
                        cost_usd=estimate_cost_usd(
                            provider=spec.provider,
                            model_id=spec.model_id,
                            input_tokens=estimated_tokens,
                        ),
                    )
                else:
                    budget.record(tokens=0, cost_usd=None)
            return _failure(job, store, config, exc, embedded, replaced, unchanged, tokens_used)
        latency_ms = _elapsed_ms(started)

        used_tokens = result.input_tokens if result.input_tokens is not None else estimated_tokens
        cost = estimate_cost_usd(
            provider=spec.provider, model_id=spec.model_id, input_tokens=result.input_tokens
        )
        # The spend is real whether or not the response is usable or
        # persistence later succeeds, so record it first.
        store.record_call(
            job,
            spec=spec,
            purpose=EmbeddingInputType.DOCUMENT,
            batch_size=len(texts),
            input_tokens=result.input_tokens,
            estimated_cost_usd=cost,
            latency_ms=latency_ms,
            success=True,
            error_classification=None,
        )
        budget.record(tokens=used_tokens, cost_usd=cost)
        tokens_used += used_tokens

        try:
            validate_result(result, spec=spec, expected_vectors=len(texts))
        except EmbeddingDimensionMismatchError as exc:
            return _failure(job, store, config, exc, embedded, replaced, unchanged, tokens_used)

        try:
            counts = store.persist_batch(
                job,
                spec,
                [
                    PersistItem(chunk_id=chunk.chunk_id, fingerprint=fp, vector=vector)
                    for (chunk, _text, fp), vector in zip(batch, result.vectors, strict=True)
                ],
            )
        except Exception:  # noqa: BLE001 - replaced by a content-free transient error
            # The vectors already passed validation, so a storage failure
            # here is infrastructural and worth a bounded retry. The
            # original exception is deliberately dropped: driver messages
            # can echo statement parameters (document text, vectors).
            return _failure(
                job,
                store,
                config,
                EmbeddingPersistenceError("persisting a validated batch failed"),
                embedded,
                replaced,
                unchanged,
                tokens_used,
            )

        embedded += counts.inserted
        replaced += counts.replaced
        unchanged += counts.unchanged

    store.mark_completed(job, chunk_total=len(chunks))
    return JobResult(
        JobOutcome.COMPLETED,
        embedded=embedded,
        replaced=replaced,
        unchanged=unchanged,
        tokens_used=tokens_used,
    )


def run_job(
    job: JobContext,
    *,
    store: JobStore,
    provider: EmbeddingProvider,
    spec: EmbeddingModelSpec,
    budget: EmbeddingRunBudget,
    config: ProcessorConfig,
) -> JobResult:
    """`process_job` with a backstop: an exception that escapes it (for
    example a persistence-layer error while checking eligibility) is
    classified and recorded on the job instead of being lost, so a claimed
    job never stays `processing` because of an exception alone. If the
    store is itself unusable the recording step raises and the caller's
    stale-job reclaim recovers the job later."""
    try:
        return process_job(
            job, store=store, provider=provider, spec=spec, budget=budget, config=config
        )
    except Exception as exc:  # noqa: BLE001 - classified; message never persisted
        return _failure(job, store, config, exc, 0, 0, 0, 0)


def _request_exposure(exc: BaseException) -> tuple[bool, bool, int | None]:
    """(request attempted, possibly billed, vendor-reported tokens) for a
    provider failure. Adapters that issued a request say so on the error. A
    transient error from a provider that does not (a test double, a future
    adapter) is treated as an ambiguous attempt; any other error without that
    evidence is treated as a pre-request failure."""
    if isinstance(exc, EmbeddingError) and exc.request_attempted:
        return True, exc.possibly_billed, exc.reported_input_tokens
    if classify(exc) == "transient":
        return True, True, None
    return False, False, None


def _plan_batches(
    pending: Sequence[_PendingItem], *, batch_size: int, provider: EmbeddingProvider
) -> list[list[_PendingItem]]:
    """Splits `pending` into batches of at most `batch_size` inputs and, when
    the provider declares an aggregate size cap (`max_batch_input_size`, in
    the units of its `input_size`), at most that total, so a batch is split
    here instead of being rejected whole by the provider. An input larger
    than the cap on its own still forms a batch of one and is rejected by the
    provider's own check as a terminal input error."""
    size_of = getattr(provider, "input_size", None)
    cap = getattr(provider, "max_batch_input_size", None)
    limit = cap if callable(size_of) and isinstance(cap, int) and cap > 0 else None
    batches: list[list[_PendingItem]] = []
    current: list[_PendingItem] = []
    current_size = 0
    for item in pending:
        size = size_of(item[1]) if limit is not None and callable(size_of) else 0
        over_size = limit is not None and current_size + size > limit
        if current and (len(current) >= batch_size or over_size):
            batches.append(current)
            current, current_size = [], 0
        current.append(item)
        current_size += size
    if current:
        batches.append(current)
    return batches


def _elapsed_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)


def _failure(
    job: JobContext,
    store: JobStore,
    config: ProcessorConfig,
    exc: BaseException,
    embedded: int,
    replaced: int,
    unchanged: int,
    tokens_used: int,
) -> JobResult:
    classification = classify(exc)
    summary = safe_summary(exc)

    # Credentials/configuration problems are not this job's fault and the
    # whole run should stop; do not burn the job's attempts on them.
    if isinstance(exc, EmbeddingAuthError | EmbeddingConfigurationError):
        store.requeue(
            job,
            error_classification=classification,
            error_message=summary,
            note="provider_unavailable",
            refund_attempt=True,
        )
        return JobResult(
            JobOutcome.REQUEUED,
            note="provider_unavailable",
            abort_run=True,
            embedded=embedded,
            replaced=replaced,
            unchanged=unchanged,
            tokens_used=tokens_used,
        )

    if classification == "transient" and job.attempt_count < config.max_attempts:
        store.requeue(
            job,
            error_classification=classification,
            error_message=summary,
            note="transient_failure_requeued",
            refund_attempt=False,
        )
        return JobResult(
            JobOutcome.REQUEUED,
            note="transient_failure_requeued",
            abort_run=isinstance(exc, EmbeddingRateLimitError),
            retry_after_seconds=(
                exc.retry_after_seconds if isinstance(exc, EmbeddingRateLimitError) else None
            ),
            embedded=embedded,
            replaced=replaced,
            unchanged=unchanged,
            tokens_used=tokens_used,
        )

    store.mark_failed(job, error_classification=classification, error_message=summary)
    return JobResult(
        JobOutcome.FAILED,
        note=summary,
        embedded=embedded,
        replaced=replaced,
        unchanged=unchanged,
        tokens_used=tokens_used,
    )
