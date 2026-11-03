"""Shared test doubles for the embedding unit tests (Milestone 10D.2).

`InMemoryJobStore` implements `app.embeddings.processor.JobStore` with
plain dicts, mirroring the *semantics* of the SQL adapter: one embedding
per (chunk, model, version), an upsert that is a no-op when the fingerprint
is unchanged and an in-place replace (revision + 1) when it differs. It
proves the processor's logic. It does **not** prove the SQL, the claim
query, or any CHECK constraint — only the gated integration tests can.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field

from app.core.types import EmbeddingInputType
from app.embeddings.dimensions import EmbeddingModelSpec
from app.embeddings.processor import (
    ChunkToEmbed,
    JobContext,
    PersistCounts,
    PersistItem,
)
from app.retrieval.eligibility import EligibilityDecision, EligibilityReason

ELIGIBLE = EligibilityDecision(True, EligibilityReason.ELIGIBLE)
NOT_APPROVED = EligibilityDecision(False, EligibilityReason.NOT_APPROVED)

SPEC = EmbeddingModelSpec(
    provider="fake", model_id="fake-embedding", model_version="fake-1", dimension=1024
)


@dataclass
class StoredEmbedding:
    fingerprint: str
    vector: list[float]
    revision: int = 1


@dataclass
class LoggedCall:
    purpose: EmbeddingInputType
    batch_size: int
    input_tokens: int | None
    estimated_cost_usd: float | None
    success: bool
    error_classification: str | None


@dataclass
class InMemoryJobStore:
    chunks: list[ChunkToEmbed]
    default_decision: EligibilityDecision = ELIGIBLE
    # When set, `check_eligibility` pops one decision per call (then falls
    # back to `default_decision`), letting a test change eligibility
    # mid-job.
    eligibility_script: list[EligibilityDecision] = field(default_factory=list)
    fail_persist_times: int = 0
    persist_error_text: str = "SECRET-DOCUMENT-TEXT must never be persisted"

    embeddings: dict[tuple[uuid.UUID, str, str], StoredEmbedding] = field(default_factory=dict)
    calls: list[LoggedCall] = field(default_factory=list)
    eligibility_checks: int = 0
    persist_calls: int = 0

    status: str = "processing"
    completed_total: int | None = None
    blocked_reason: str | None = None
    requeues: list[dict[str, object]] = field(default_factory=list)
    failures: list[dict[str, str]] = field(default_factory=list)
    # Test hook: serve a stale view of stored fingerprints to simulate a
    # second worker that read before the first one persisted.
    stale_existing: dict[uuid.UUID, str] | None = None

    def check_eligibility(self, job: JobContext) -> EligibilityDecision:
        self.eligibility_checks += 1
        if self.eligibility_script:
            return self.eligibility_script.pop(0)
        return self.default_decision

    def list_chunks(self, job: JobContext) -> list[ChunkToEmbed]:
        return list(self.chunks)

    def existing_fingerprints(
        self, job: JobContext, spec: EmbeddingModelSpec
    ) -> dict[uuid.UUID, str]:
        if self.stale_existing is not None:
            return dict(self.stale_existing)
        return {
            chunk_id: stored.fingerprint
            for (chunk_id, model, version), stored in self.embeddings.items()
            if model == spec.model_id and version == spec.model_version
        }

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
        self.calls.append(
            LoggedCall(
                purpose, batch_size, input_tokens, estimated_cost_usd, success, error_classification
            )
        )

    def persist_batch(
        self, job: JobContext, spec: EmbeddingModelSpec, items: Sequence[PersistItem]
    ) -> PersistCounts:
        self.persist_calls += 1
        if self.fail_persist_times > 0:
            self.fail_persist_times -= 1
            # Mimics a driver error whose message echoes the statement
            # parameters — the processor must never persist this text.
            raise RuntimeError(self.persist_error_text)
        inserted = replaced = unchanged = 0
        for item in items:
            key = (item.chunk_id, spec.model_id, spec.model_version)
            current = self.embeddings.get(key)
            if current is None:
                self.embeddings[key] = StoredEmbedding(item.fingerprint, list(item.vector))
                inserted += 1
            elif current.fingerprint != item.fingerprint:
                self.embeddings[key] = StoredEmbedding(
                    item.fingerprint, list(item.vector), current.revision + 1
                )
                replaced += 1
            else:
                unchanged += 1
        return PersistCounts(inserted, replaced, unchanged)

    def mark_completed(self, job: JobContext, *, chunk_total: int) -> None:
        self.status = "completed"
        self.completed_total = chunk_total

    def requeue(
        self,
        job: JobContext,
        *,
        error_classification: str | None,
        error_message: str | None,
        note: str,
        refund_attempt: bool,
    ) -> None:
        self.status = "pending"
        self.requeues.append(
            {
                "classification": error_classification,
                "message": error_message,
                "note": note,
                "refund_attempt": refund_attempt,
            }
        )

    def mark_failed(
        self, job: JobContext, *, error_classification: str, error_message: str
    ) -> None:
        self.status = "failed"
        self.failures.append({"classification": error_classification, "message": error_message})

    def mark_blocked(self, job: JobContext, *, reason: str) -> None:
        self.status = "blocked_ineligible"
        self.blocked_reason = reason

    def rows_for(self, spec: EmbeddingModelSpec) -> int:
        return sum(
            1
            for (_cid, model, version) in self.embeddings
            if model == spec.model_id and version == spec.model_version
        )


def make_chunks(count: int = 5) -> list[ChunkToEmbed]:
    return [
        ChunkToEmbed(
            chunk_id=uuid.UUID(int=index + 1),
            chunk_index=index,
            section_path="ARTICLE VI > Section 6.01 Indebtedness" if index % 2 == 0 else None,
            content=f"Synthetic test passage number {index} about negative covenants.",
        )
        for index in range(count)
    ]


def make_job(
    *, title: str = "Synthetic Test Credit Agreement", attempt_count: int = 1
) -> JobContext:
    return JobContext(
        job_id=uuid.UUID(int=999),
        research_document_id=uuid.UUID(int=1000),
        document_extraction_id=uuid.UUID(int=1001),
        document_title=title,
        attempt_count=attempt_count,
    )
