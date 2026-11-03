"""Unit tests for `app.embeddings.processor` (Milestone 10D.2) against an
in-memory store and the deterministic fake provider.

These prove the *logic* of idempotency, safe replacement, partial
completion, retries, budget stops, ineligibility, and spend recording. They
do not prove PostgreSQL behavior (the upsert SQL, the claim query, CHECK
constraints) — the gated integration tests cover that. No network, no
database, no real provider.
"""

from __future__ import annotations

import pytest

from app.embeddings.budget import EmbeddingRunBudget
from app.embeddings.dimensions import EmbeddingModelSpec
from app.embeddings.errors import (
    EmbeddingAuthError,
    EmbeddingInputError,
    EmbeddingRateLimitError,
    EmbeddingTransientError,
)
from app.embeddings.fake import FakeEmbeddingProvider
from app.embeddings.fingerprint import build_embedding_input, estimate_tokens
from app.embeddings.processor import JobOutcome, JobResult, ProcessorConfig, process_job, run_job
from app.retrieval.eligibility import EligibilityDecision, EligibilityReason

from .embedding_support import (
    ELIGIBLE,
    NOT_APPROVED,
    SPEC,
    InMemoryJobStore,
    make_chunks,
    make_job,
)

CONFIG = ProcessorConfig(batch_size=2, max_attempts=3)


def _budget(tokens: int = 1_000_000) -> EmbeddingRunBudget:
    return EmbeddingRunBudget(max_tokens=tokens)


def _provider(**kwargs: object) -> FakeEmbeddingProvider:
    return FakeEmbeddingProvider(**kwargs)  # type: ignore[arg-type]


def _run(store: InMemoryJobStore, provider: FakeEmbeddingProvider, **kwargs: object) -> JobResult:
    params: dict[str, object] = {
        "job": make_job(),
        "spec": SPEC,
        "budget": _budget(),
        "config": CONFIG,
    }
    params.update(kwargs)
    return process_job(store=store, provider=provider, **params)  # type: ignore[arg-type]


# --- idempotency ---


def test_first_run_embeds_every_chunk_and_completes() -> None:
    store = InMemoryJobStore(chunks=make_chunks(5))
    provider = _provider()
    result = _run(store, provider)
    assert result.outcome is JobOutcome.COMPLETED
    assert (result.embedded, result.replaced, result.unchanged) == (5, 0, 0)
    assert store.rows_for(SPEC) == 5
    assert store.status == "completed"
    assert store.completed_total == 5
    assert provider.texts_sent == 5
    assert provider.call_count == 3  # batches of 2, 2, 1


def test_rerun_with_unchanged_content_makes_no_provider_call_and_no_new_rows() -> None:
    store = InMemoryJobStore(chunks=make_chunks(5))
    _run(store, _provider())
    second_provider = _provider()
    result = _run(store, second_provider)
    assert result.outcome is JobOutcome.COMPLETED
    assert (result.embedded, result.replaced, result.unchanged) == (0, 0, 5)
    assert second_provider.call_count == 0
    assert store.rows_for(SPEC) == 5
    assert all(e.revision == 1 for e in store.embeddings.values())


def test_a_provider_must_not_be_called_when_there_is_nothing_to_embed() -> None:
    store = InMemoryJobStore(chunks=[])
    provider = _provider()
    result = _run(store, provider)
    assert result.outcome is JobOutcome.COMPLETED
    assert provider.call_count == 0


# --- changed inputs ---


def test_changed_document_title_replaces_vectors_in_place() -> None:
    store = InMemoryJobStore(chunks=make_chunks(3))
    _run(store, _provider())
    before = {k: (v.fingerprint, list(v.vector)) for k, v in store.embeddings.items()}

    result = _run(store, _provider(), job=make_job(title="Renamed Credit Agreement"))

    assert (result.embedded, result.replaced, result.unchanged) == (0, 3, 0)
    assert store.rows_for(SPEC) == 3  # replaced, never duplicated
    for key, stored in store.embeddings.items():
        assert stored.revision == 2
        assert stored.fingerprint != before[key][0]
        assert stored.vector != before[key][1]


def test_new_model_version_inserts_alongside_and_never_deletes_the_old_vectors() -> None:
    store = InMemoryJobStore(chunks=make_chunks(3))
    _run(store, _provider())
    old_rows = {k: v.fingerprint for k, v in store.embeddings.items()}

    spec_v2 = EmbeddingModelSpec("fake", "fake-embedding", "fake-2", 1024)
    result = _run(store, _provider(model_version="fake-2"), spec=spec_v2)

    assert (result.embedded, result.replaced) == (3, 0)
    assert store.rows_for(SPEC) == 3
    assert store.rows_for(spec_v2) == 3
    for key, fingerprint in old_rows.items():
        assert store.embeddings[key].fingerprint == fingerprint  # untouched


def test_previous_vector_survives_when_the_replacement_call_fails() -> None:
    store = InMemoryJobStore(chunks=make_chunks(3))
    _run(store, _provider())
    snapshot = {k: (v.fingerprint, list(v.vector), v.revision) for k, v in store.embeddings.items()}

    failing = _provider()
    failing.fail_next(EmbeddingTransientError("vendor 503"))
    result = _run(store, failing, job=make_job(title="Renamed", attempt_count=1))

    assert result.outcome is JobOutcome.REQUEUED
    assert {k: (v.fingerprint, v.vector, v.revision) for k, v in store.embeddings.items()} == (
        snapshot
    )


def test_previous_vector_survives_when_persisting_the_replacement_fails() -> None:
    store = InMemoryJobStore(chunks=make_chunks(2))
    _run(store, _provider())
    snapshot = {k: v.fingerprint for k, v in store.embeddings.items()}

    store.fail_persist_times = 1
    result = _run(store, _provider(), job=make_job(title="Renamed"))

    assert result.outcome is JobOutcome.REQUEUED
    assert {k: v.fingerprint for k, v in store.embeddings.items()} == snapshot


# --- partial completion and retry ---


def test_partial_failure_keeps_completed_batches_and_resume_only_does_the_rest() -> None:
    store = InMemoryJobStore(chunks=make_chunks(5))
    provider = _provider()
    provider.fail_on_call(2, EmbeddingTransientError("vendor 503"))  # batches: [2][2][1]

    result = _run(store, provider)

    assert result.outcome is JobOutcome.REQUEUED
    assert store.rows_for(SPEC) == 2  # batch 1 persisted and kept
    assert store.status == "pending"

    resume_provider = _provider()
    resumed = _run(store, resume_provider, job=make_job(attempt_count=2))
    assert resumed.outcome is JobOutcome.COMPLETED
    assert (resumed.embedded, resumed.unchanged) == (3, 2)
    assert resume_provider.texts_sent == 3  # never re-sends what is already embedded
    assert store.rows_for(SPEC) == 5


def test_transient_failure_requeues_while_attempts_remain() -> None:
    store = InMemoryJobStore(chunks=make_chunks(2))
    provider = _provider()
    provider.fail_next(EmbeddingTransientError("vendor 503"))
    result = _run(store, provider, job=make_job(attempt_count=1))
    assert result.outcome is JobOutcome.REQUEUED
    assert store.requeues[0]["classification"] == "transient"
    assert store.requeues[0]["refund_attempt"] is False
    assert store.failures == []


def test_transient_failure_fails_once_attempts_are_exhausted() -> None:
    store = InMemoryJobStore(chunks=make_chunks(2))
    provider = _provider()
    provider.fail_next(EmbeddingTransientError("vendor 503"))
    result = _run(store, provider, job=make_job(attempt_count=CONFIG.max_attempts))
    assert result.outcome is JobOutcome.FAILED
    assert store.status == "failed"
    assert store.failures[0]["classification"] == "transient"


def test_deterministic_failure_is_never_retried() -> None:
    store = InMemoryJobStore(chunks=make_chunks(2))
    provider = _provider()
    provider.fail_next(EmbeddingInputError("input too long"))
    result = _run(store, provider, job=make_job(attempt_count=1))
    assert result.outcome is JobOutcome.FAILED
    assert store.requeues == []
    assert store.failures[0]["classification"] == "deterministic"


def test_unrecognized_exception_is_deterministic_and_its_message_is_never_stored() -> None:
    store = InMemoryJobStore(chunks=make_chunks(2))
    provider = _provider()
    provider.fail_next(ValueError("SECRET-DOCUMENT-TEXT leaked by a vendor SDK"))
    result = _run(store, provider)
    assert result.outcome is JobOutcome.FAILED
    assert store.failures == [
        {"classification": "deterministic", "message": "ValueError (deterministic)"}
    ]
    assert "SECRET" not in repr(store.failures) + repr(result)


def test_persistence_error_message_is_never_stored() -> None:
    store = InMemoryJobStore(chunks=make_chunks(2))
    store.fail_persist_times = 1
    result = _run(store, _provider(), job=make_job(attempt_count=1))
    assert result.outcome is JobOutcome.REQUEUED
    assert "SECRET" not in repr(store.requeues) + repr(result)
    assert store.requeues[0]["message"] == "EmbeddingPersistenceError (transient)"


def test_persistence_failure_is_retried_but_bounded_by_the_attempt_cap() -> None:
    store = InMemoryJobStore(chunks=make_chunks(2))
    store.fail_persist_times = 1
    result = _run(store, _provider(), job=make_job(attempt_count=CONFIG.max_attempts))
    assert result.outcome is JobOutcome.FAILED
    assert store.failures[0]["classification"] == "transient"
    assert "SECRET" not in repr(store.failures)


def test_spend_is_recorded_before_persistence_so_a_rollback_cannot_hide_cost() -> None:
    store = InMemoryJobStore(chunks=make_chunks(2))
    store.fail_persist_times = 1
    _run(store, _provider(), job=make_job(attempt_count=1))
    assert len(store.calls) == 1
    assert store.calls[0].success is True
    assert store.calls[0].input_tokens is not None
    assert store.rows_for(SPEC) == 0

    # The retry re-sends the batch and the ledger shows both calls.
    _run(store, _provider(), job=make_job(attempt_count=2))
    assert len(store.calls) == 2
    assert store.rows_for(SPEC) == 2


def test_failed_provider_calls_are_logged_with_unknown_tokens_and_cost() -> None:
    store = InMemoryJobStore(chunks=make_chunks(2))
    provider = _provider()
    provider.fail_next(EmbeddingTransientError("x"))
    _run(store, provider, job=make_job(attempt_count=1))
    call = store.calls[0]
    assert (call.success, call.input_tokens, call.estimated_cost_usd) == (False, None, None)
    assert call.error_classification == "transient"


def test_unknown_token_usage_is_logged_as_none_but_still_budgeted() -> None:
    store = InMemoryJobStore(chunks=make_chunks(2))
    budget = _budget()
    _run(store, _provider(report_usage=False), budget=budget)
    assert store.calls[0].input_tokens is None
    assert store.calls[0].estimated_cost_usd is None  # unknown, not zero
    assert budget.tokens_used > 0  # estimated, so the budget still bites


# --- provider output validation ---


@pytest.mark.parametrize(
    "overrides",
    [
        {"returned_dimension": 512},
        {"returned_model_version": "some-other-version"},
        {"drop_last_vector": True},
    ],
)
def test_incompatible_provider_response_is_rejected_and_nothing_is_persisted(
    overrides: dict[str, object],
) -> None:
    store = InMemoryJobStore(chunks=make_chunks(2))
    result = _run(store, _provider(**overrides))
    assert result.outcome is JobOutcome.FAILED
    assert store.rows_for(SPEC) == 0
    assert store.persist_calls == 0
    assert store.failures[0]["classification"] == "deterministic"
    assert len(store.calls) == 1  # the spend was still recorded


def test_provider_identity_must_match_the_job_spec_before_any_work() -> None:
    store = InMemoryJobStore(chunks=make_chunks(2))
    mismatched = _provider(model_version="fake-9")
    result = _run(store, mismatched)
    # A configuration problem is held for an operator, not left claimable.
    assert result.outcome is JobOutcome.HELD
    assert result.abort_run is True
    assert result.note == "provider_spec_mismatch"
    assert store.holds[0]["reason"] == "provider_spec_mismatch" and store.requeues == []
    assert mismatched.call_count == 0
    assert store.eligibility_checks == 0


# --- eligibility ---


def test_ineligible_document_blocks_the_job_with_no_provider_call() -> None:
    store = InMemoryJobStore(chunks=make_chunks(3), default_decision=NOT_APPROVED)
    provider = _provider()
    result = _run(store, provider)
    assert result.outcome is JobOutcome.BLOCKED_INELIGIBLE
    assert provider.call_count == 0
    assert store.status == "blocked_ineligible"
    assert store.blocked_reason == EligibilityReason.NOT_APPROVED.value
    assert store.requeues == [] and store.failures == []


def test_eligibility_is_rechecked_immediately_before_every_provider_call() -> None:
    # start check, before batch 1, before batch 2 (denied), ...
    store = InMemoryJobStore(
        chunks=make_chunks(4),
        eligibility_script=[
            ELIGIBLE,
            ELIGIBLE,
            EligibilityDecision(False, EligibilityReason.ARCHIVED),
        ],
    )
    provider = _provider()
    result = _run(store, provider)
    assert result.outcome is JobOutcome.BLOCKED_INELIGIBLE
    assert result.note == "archived"
    assert provider.call_count == 1  # only the batch sent while still eligible
    assert store.eligibility_checks == 3


def test_a_delayed_job_for_a_revoked_document_never_reaches_the_provider() -> None:
    # The job was enqueued while eligible, but approval was revoked before
    # the worker picked it up.
    store = InMemoryJobStore(chunks=make_chunks(2), default_decision=NOT_APPROVED)
    provider = _provider()
    assert _run(store, provider, job=make_job(attempt_count=1)).outcome is (
        JobOutcome.BLOCKED_INELIGIBLE
    )
    assert provider.call_count == 0


# --- budget ---


def test_budget_stop_requeues_without_consuming_an_attempt_and_without_a_call() -> None:
    store = InMemoryJobStore(chunks=make_chunks(3))
    provider = _provider()
    result = _run(store, provider, budget=_budget(tokens=1))
    assert result.outcome is JobOutcome.REQUEUED
    assert result.note == "budget_stop:token_budget_exhausted"
    assert provider.call_count == 0
    assert store.requeues[0]["refund_attempt"] is True
    assert store.failures == []
    assert store.status == "pending"


def test_budget_exhausted_mid_job_keeps_finished_batches_and_a_fresh_budget_resumes() -> None:
    chunks = make_chunks(4)
    store = InMemoryJobStore(chunks=chunks)
    first_batch_tokens = sum(
        estimate_tokens(
            build_embedding_input(
                document_title=make_job().document_title,
                section_path=c.section_path,
                content=c.content,
            )
        )
        for c in chunks[:2]
    )
    # Room for the first batch of two, but not for a second one.
    first = _run(store, _provider(), budget=_budget(tokens=first_batch_tokens + 1))
    assert first.outcome is JobOutcome.REQUEUED
    assert first.note == "budget_stop:token_budget_exhausted"
    assert store.rows_for(SPEC) == 2

    second = _run(store, _provider(), budget=_budget(), job=make_job(attempt_count=1))
    assert second.outcome is JobOutcome.COMPLETED
    assert store.rows_for(SPEC) == 4
    assert second.unchanged == 2


def test_cost_ceiling_with_an_unpriced_model_refuses_before_any_call() -> None:
    unpriced = EmbeddingModelSpec("fake", "unpriced-model", "v1", 1024)
    store = InMemoryJobStore(chunks=make_chunks(2))
    provider = _provider(model_id="unpriced-model", model_version="v1")
    result = _run(
        store,
        provider,
        spec=unpriced,
        budget=EmbeddingRunBudget(max_tokens=1_000_000, max_cost_usd=1.0),
    )
    assert result.outcome is JobOutcome.REQUEUED
    assert result.note == "budget_stop:cost_ceiling_unenforceable_price_unknown"
    assert provider.call_count == 0


# --- provider-wide failures ---


def test_auth_error_holds_the_job_with_the_attempt_refunded_and_aborts_the_run() -> None:
    # Superseded behavior: this used to requeue the job as claimable `pending`.
    store = InMemoryJobStore(chunks=make_chunks(2))
    provider = _provider()
    provider.fail_next(EmbeddingAuthError("bad key"))
    result = _run(store, provider, job=make_job(attempt_count=3))
    assert result.outcome is JobOutcome.HELD
    assert result.abort_run is True
    assert result.note == "held:provider_credentials_or_quota"
    assert store.holds[0]["refund_attempt"] is True and store.holds[0]["provider_wide"] is True
    assert store.requeues == [] and store.failures == []


def test_rate_limit_requeues_and_aborts_the_run_without_failing_the_job() -> None:
    store = InMemoryJobStore(chunks=make_chunks(2))
    provider = _provider()
    provider.fail_next(EmbeddingRateLimitError("429", retry_after_seconds=30))
    result = _run(store, provider, job=make_job(attempt_count=1))
    assert result.outcome is JobOutcome.REQUEUED
    assert result.abort_run is True
    assert result.note == "transient_failure_requeued"
    assert store.failures == []


# --- concurrency semantics ---


def test_two_writers_with_a_stale_view_converge_on_one_row_per_chunk() -> None:
    """Models a stale-reclaimed job processed twice: the second worker read
    the fingerprints before the first persisted, so it re-embeds everything.
    The upsert contract must leave exactly one unchanged row per chunk."""
    store = InMemoryJobStore(chunks=make_chunks(4))
    _run(store, _provider())

    store.stale_existing = {}  # the second worker believes nothing is embedded yet
    second = _run(store, _provider())

    assert second.outcome is JobOutcome.COMPLETED
    assert (second.embedded, second.replaced, second.unchanged) == (0, 0, 4)
    assert store.rows_for(SPEC) == 4
    assert all(e.revision == 1 for e in store.embeddings.values())


# --- backstop ---


def test_run_job_records_an_exception_that_escapes_the_processor() -> None:
    class _ExplodingStore(InMemoryJobStore):
        def check_eligibility(self, job):  # type: ignore[no-untyped-def]
            raise RuntimeError("SECRET-DOCUMENT-TEXT in a database error")

    store = _ExplodingStore(chunks=make_chunks(2))
    result = run_job(
        make_job(attempt_count=CONFIG.max_attempts),
        store=store,
        provider=_provider(),
        spec=SPEC,
        budget=_budget(),
        config=CONFIG,
    )
    assert result.outcome is JobOutcome.FAILED
    assert "SECRET" not in repr(store.failures) + repr(result)
