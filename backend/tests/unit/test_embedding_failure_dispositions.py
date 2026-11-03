"""Failure dispositions through the processor (Milestone 10D.2 scheduling
increment): attempts, backoff, provider-wide scope, operator holds and the
accounting evidence that must survive them. In-memory store, fake provider,
injected clock and jitter; nothing sleeps; no database."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.embeddings.budget import EmbeddingRunBudget
from app.embeddings.errors import (
    EmbeddingAuthError,
    EmbeddingConfigurationError,
    EmbeddingDimensionMismatchError,
    EmbeddingInputError,
    EmbeddingPersistenceError,
    EmbeddingRateLimitError,
    EmbeddingResponseError,
    EmbeddingTransientError,
)
from app.embeddings.fake import FakeEmbeddingProvider
from app.embeddings.processor import JobOutcome, JobResult, ProcessorConfig, process_job
from app.embeddings.scheduling import MAX_AUTOMATIC_DELAY_SECONDS

from .embedding_support import SPEC, InMemoryJobStore, make_chunks, make_job

NOW = datetime(2026, 11, 2, 12, 0, 0, tzinfo=UTC)


def _config(max_attempts: int = 3) -> ProcessorConfig:
    return ProcessorConfig(
        batch_size=2, max_attempts=max_attempts, clock=lambda: NOW, jitter=lambda: 0.0
    )


def _run(
    store: InMemoryJobStore,
    provider: FakeEmbeddingProvider,
    *,
    attempt: int = 1,
    budget: EmbeddingRunBudget | None = None,
    max_attempts: int = 3,
) -> JobResult:
    return process_job(
        make_job(attempt_count=attempt),
        store=store,
        provider=provider,
        spec=SPEC,
        budget=budget or EmbeddingRunBudget(max_tokens=1_000_000),
        config=_config(max_attempts),
    )


def _failing(error: Exception, times: int = 1) -> FakeEmbeddingProvider:
    provider = FakeEmbeddingProvider()
    provider.fail_next(error, times=times)
    return provider


def _attempted(error: Exception, *, billed: bool = True, tokens: int | None = None) -> Exception:
    error.request_attempted = True  # type: ignore[attr-defined]
    error.possibly_billed = billed  # type: ignore[attr-defined]
    error.reported_input_tokens = tokens  # type: ignore[attr-defined]
    return error


# --- transient failures: per-job backoff, bounded -----------------------------------------------


@pytest.mark.parametrize(("attempt", "seconds"), [(1, 30), (2, 60), (3, 120)])
def test_a_transient_failure_delays_only_that_job_with_growing_backoff(
    attempt: int, seconds: int
) -> None:
    store = InMemoryJobStore(chunks=make_chunks(2))
    result = _run(store, _failing(EmbeddingTransientError("net")), attempt=attempt, max_attempts=9)
    assert result.outcome is JobOutcome.REQUEUED and result.abort_run is False
    requeue = store.requeues[0]
    assert requeue["retry_not_before"] == NOW + timedelta(seconds=seconds)
    assert requeue["provider_wide"] is False and requeue["refund_attempt"] is False
    assert result.retry_not_before == requeue["retry_not_before"]


def test_a_persistence_error_is_a_per_job_transient_failure_with_backoff() -> None:
    store = InMemoryJobStore(chunks=make_chunks(2), fail_persist_times=1)
    result = _run(store, FakeEmbeddingProvider())
    assert result.outcome is JobOutcome.REQUEUED
    assert store.requeues[0]["provider_wide"] is False
    assert store.requeues[0]["retry_not_before"] == NOW + timedelta(seconds=30)
    assert EmbeddingPersistenceError.classification == "transient"


def test_the_attempt_cap_ends_a_transient_failure_as_failed_not_requeued() -> None:
    store = InMemoryJobStore(chunks=make_chunks(2))
    result = _run(store, _failing(EmbeddingTransientError("net")), attempt=3, max_attempts=3)
    assert result.outcome is JobOutcome.FAILED
    assert store.requeues == [] and store.holds == []
    assert store.failures[0]["classification"] == "transient"


def test_jitter_only_ever_lengthens_the_delay() -> None:
    config = ProcessorConfig(batch_size=2, max_attempts=3, clock=lambda: NOW, jitter=lambda: 0.999)
    store = InMemoryJobStore(chunks=make_chunks(2))
    process_job(
        make_job(attempt_count=1),
        store=store,
        provider=_failing(EmbeddingTransientError("x")),
        spec=SPEC,
        budget=EmbeddingRunBudget(max_tokens=1_000_000),
        config=config,
    )
    delay = store.requeues[0]["retry_not_before"] - NOW  # type: ignore[operator]
    assert timedelta(seconds=30) < delay <= timedelta(seconds=37.5)


# --- rate limits: provider-wide, never earlier than the vendor, held if too long ---


def test_a_rate_limit_delays_the_provider_queue_and_keeps_the_attempt_consumed() -> None:
    store = InMemoryJobStore(chunks=make_chunks(2))
    error = EmbeddingRateLimitError("429", retry_after_seconds=100)
    result = _run(store, _failing(error))
    assert result.outcome is JobOutcome.REQUEUED and result.abort_run is True
    requeue = store.requeues[0]
    assert requeue["provider_wide"] is True and requeue["refund_attempt"] is False
    assert requeue["retry_not_before"] == NOW + timedelta(seconds=100)


def test_a_rate_limit_without_a_valid_vendor_delay_uses_backoff() -> None:
    store = InMemoryJobStore(chunks=make_chunks(2))
    result = _run(
        store, _failing(EmbeddingRateLimitError("429", retry_after_seconds=None)), attempt=2
    )
    assert result.retry_after_seconds is None
    assert store.requeues[0]["retry_not_before"] == NOW + timedelta(seconds=60)


def test_a_vendor_delay_beyond_the_automatic_limit_holds_the_queue_instead_of_retrying_early() -> (
    None
):
    store = InMemoryJobStore(chunks=make_chunks(2))
    error = EmbeddingRateLimitError("429", retry_after_seconds=MAX_AUTOMATIC_DELAY_SECONDS + 1)
    result = _run(store, _failing(error))
    assert result.outcome is JobOutcome.HELD and result.abort_run is True
    assert result.hold_reason == "retry_after_exceeds_automatic_limit"
    assert result.retry_after_seconds == MAX_AUTOMATIC_DELAY_SECONDS + 1
    hold = store.holds[0]
    assert hold["provider_wide"] is True and hold["refund_attempt"] is False
    assert store.requeues == []  # never scheduled sooner than the vendor allows


def test_the_attempt_cap_ends_even_a_rate_limited_job() -> None:
    store = InMemoryJobStore(chunks=make_chunks(2))
    result = _run(store, _failing(EmbeddingRateLimitError("429", retry_after_seconds=5)), attempt=3)
    assert result.outcome is JobOutcome.FAILED and store.requeues == [] and store.holds == []


# --- holds: credentials, quota, configuration ---


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (EmbeddingAuthError("401 or quota"), "provider_credentials_or_quota"),
        (EmbeddingConfigurationError("404 or redirect"), "provider_configuration"),
    ],
)
def test_credential_quota_and_configuration_failures_hold_the_provider_queue(
    error: Exception, reason: str
) -> None:
    store = InMemoryJobStore(chunks=make_chunks(2))
    result = _run(store, _failing(error), attempt=2)
    assert result.outcome is JobOutcome.HELD and result.abort_run is True
    assert result.hold_reason == reason and result.note == f"held:{reason}"
    hold = store.holds[0]
    assert hold["reason"] == reason and hold["provider_wide"] is True
    assert hold["refund_attempt"] is True  # not the job's fault; evidence stays in the call log
    assert store.requeues == [] and store.failures == []  # never left claimable


def test_a_hold_message_is_content_free() -> None:
    store = InMemoryJobStore(chunks=make_chunks(2))
    _run(store, _failing(EmbeddingAuthError("raw vendor text with SECRET-123")))
    assert "SECRET-123" not in str(store.holds[0])


# --- deterministic errors never create a retry loop ---


@pytest.mark.parametrize(
    "error",
    [
        EmbeddingInputError("too long"),
        EmbeddingResponseError("malformed"),
        EmbeddingDimensionMismatchError("wrong width"),
        ValueError("anything unrecognized"),
    ],
)
def test_deterministic_errors_fail_the_job_with_no_requeue_or_hold(error: Exception) -> None:
    store = InMemoryJobStore(chunks=make_chunks(2))
    result = _run(store, _failing(error), attempt=1)
    assert result.outcome is JobOutcome.FAILED
    assert store.requeues == [] and store.holds == []
    assert store.failures[0]["classification"] == "deterministic"


# --- budget stops are not schedules ---


def test_a_budget_stop_requeues_with_a_refund_and_no_delay() -> None:
    store = InMemoryJobStore(chunks=make_chunks(2))
    result = _run(store, FakeEmbeddingProvider(), budget=EmbeddingRunBudget(max_tokens=1))
    assert result.outcome is JobOutcome.REQUEUED
    requeue = store.requeues[0]
    assert requeue["refund_attempt"] is True
    assert requeue["retry_not_before"] is None and requeue["provider_wide"] is False


# --- accounting evidence survives holds and partial batches ---


def test_a_hold_after_a_successful_batch_keeps_the_earlier_usage_and_rows() -> None:
    store = InMemoryJobStore(chunks=make_chunks(4))
    provider = FakeEmbeddingProvider()
    provider.fail_on_call(2, _attempted(EmbeddingAuthError("401")))
    budget = EmbeddingRunBudget(max_tokens=1_000_000)
    result = _run(store, provider, budget=budget)
    assert result.outcome is JobOutcome.HELD
    assert len(store.embeddings) == 2  # the first batch is persisted and kept
    assert result.tokens_used > 0 and result.tokens_used == store.calls[0].input_tokens
    assert [c.success for c in store.calls] == [True, False]
    assert store.calls[1].input_tokens is None  # unknown usage stays unknown
    assert budget.requests_made == 2  # the failed request is counted once (conservatively)


def test_vendor_reported_usage_from_a_failed_request_is_kept_without_double_counting() -> None:
    store = InMemoryJobStore(chunks=make_chunks(2))
    provider = _failing(_attempted(EmbeddingResponseError("bad shape"), tokens=33))
    budget = EmbeddingRunBudget(max_tokens=1_000_000)
    result = _run(store, provider, budget=budget)
    assert result.outcome is JobOutcome.FAILED
    assert result.tokens_used == 33 and budget.tokens_used == 33 and budget.requests_made == 1
    assert store.calls[0].input_tokens == 33
