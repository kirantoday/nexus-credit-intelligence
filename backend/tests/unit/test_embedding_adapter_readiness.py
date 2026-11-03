"""Readiness-review tests for the OpenAI adapter's accounting, retry-delay,
input-boundary and policy boundaries (Milestone 10D.2).

Same rules as `test_openai_embedding_adapter.py`: `httpx.MockTransport` only,
in-memory job store, no database, no provider, no sleeping. The network
tripwire fixture is re-used (imported so pytest applies it here too); its
scope and gaps are described in that module and it is not proof of isolation.
"""

from __future__ import annotations

import dataclasses
import json
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from app.config import Settings
from app.embeddings import openai_provider as op
from app.embeddings.budget import EmbeddingRunBudget
from app.embeddings.errors import (
    EmbeddingAuthError,
    EmbeddingDimensionMismatchError,
    EmbeddingInputError,
    EmbeddingRateLimitError,
    EmbeddingResponseError,
    EmbeddingTransientError,
)
from app.embeddings.factory import OPENAI_POLICY_APPROVAL_VALUE, get_embedding_provider
from app.embeddings.fingerprint import build_embedding_input
from app.embeddings.processor import (
    ChunkToEmbed,
    JobOutcome,
    ProcessorConfig,
    _plan_batches,
    process_job,
)

from .embedding_support import InMemoryJobStore, make_chunks, make_job
from .test_document_embedding_worker import _call, _FakeService
from .test_openai_embedding_adapter import (  # noqa: F401 - _network_tripwire is an autouse fixture
    FAKE_KEY,
    SPEC,
    Recorder,
    _json_response,
    _network_tripwire,
    _ok_body,
    _provider,
    _run,
    _status,
)

PRICE = 0.13 / 1_000_000


def _chunk(index: int, content: str) -> ChunkToEmbed:
    return ChunkToEmbed(
        chunk_id=uuid.UUID(int=5000 + index),
        chunk_index=index,
        section_path=None,
        content=content,
    )


def _usage_ok(per_input: int = 11):
    def responder(request: httpx.Request) -> httpx.Response:
        n = len(json.loads(request.content)["input"])
        tokens = per_input * n
        return _json_response(
            200, _ok_body(n, usage={"prompt_tokens": tokens, "total_tokens": tokens})
        )

    return responder


# --- adapter evidence on errors -------------------------------------------------------


def test_errors_before_any_request_carry_no_exposure_evidence() -> None:
    provider, rec = _provider(_usage_ok())
    for texts in ([""], ["x" * (op.MAX_INPUT_BYTES + 1)], []):
        with pytest.raises(EmbeddingInputError) as info:
            provider.embed_documents(texts)
        assert info.value.request_attempted is False
        assert info.value.possibly_billed is False
        assert info.value.reported_input_tokens is None
    assert rec.count == 0


@pytest.mark.parametrize(
    ("exception", "billed"),
    [
        (httpx.ConnectError("c"), False),
        (httpx.ConnectTimeout("t"), False),
        (httpx.PoolTimeout("p"), False),
        (httpx.ReadTimeout("t"), True),
        (httpx.WriteTimeout("t"), True),
        (httpx.ReadError("r"), True),
        (httpx.RemoteProtocolError("p"), True),
    ],
)
def test_transport_failures_distinguish_not_delivered_from_possibly_processed(
    exception: Exception, billed: bool
) -> None:
    def responder(_r: httpx.Request) -> httpx.Response:
        raise exception

    provider, _rec = _provider(responder)
    with pytest.raises(EmbeddingTransientError) as info:
        provider.embed_documents(["x"])
    assert info.value.request_attempted is True
    assert info.value.possibly_billed is billed
    assert info.value.reported_input_tokens is None


@pytest.mark.parametrize("status", [400, 401, 403, 404, 429, 500, 503])
def test_every_http_status_error_is_treated_as_possibly_billed(status: int) -> None:
    provider, _rec = _provider(_status(status))
    with pytest.raises(Exception) as info:  # noqa: B017 - any mapped error type
        provider.embed_documents(["x"])
    assert info.value.request_attempted is True  # type: ignore[attr-defined]
    assert info.value.possibly_billed is True  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    ("body_change", "error_type"),
    [
        (lambda b: b["data"].pop(), EmbeddingDimensionMismatchError),  # wrong count
        (lambda b: b.update(model="other-model"), EmbeddingDimensionMismatchError),
        (lambda b: b["data"][0].update(embedding=[1.0]), EmbeddingDimensionMismatchError),
        (lambda b: b["data"][0].update(index=1), EmbeddingResponseError),  # duplicate index
        (lambda b: b["data"][0].update(embedding="AAAA"), EmbeddingResponseError),
    ],
)
def test_a_rejected_200_keeps_the_vendors_valid_usage_as_evidence(
    body_change: Any, error_type: type
) -> None:
    body = _ok_body(2, usage={"prompt_tokens": 33, "total_tokens": 33})
    body_change(body)
    provider, rec = _provider(lambda _r: _json_response(200, body))
    with pytest.raises(error_type) as info:
        provider.embed_documents(["a", "b"])
    assert info.value.request_attempted is True  # type: ignore[attr-defined]
    assert info.value.possibly_billed is True  # type: ignore[attr-defined]
    assert info.value.reported_input_tokens == 33  # type: ignore[attr-defined]
    assert rec.count == 1


@pytest.mark.parametrize(
    "usage",
    [
        None,
        "x",
        {},
        {"prompt_tokens": "5", "total_tokens": 5},
        {"prompt_tokens": 5, "total_tokens": 6},
    ],
)
def test_a_rejected_200_with_missing_or_invalid_usage_leaves_tokens_unknown(usage: Any) -> None:
    body = _ok_body(2)
    body["usage"] = usage
    body["data"].pop()
    provider, _rec = _provider(lambda _r: _json_response(200, body))
    with pytest.raises(EmbeddingDimensionMismatchError) as info:
        provider.embed_documents(["a", "b"])
    assert info.value.reported_input_tokens is None
    assert info.value.possibly_billed is True


def test_a_non_json_200_is_possibly_billed_with_unknown_usage() -> None:
    provider, _rec = _provider(lambda _r: httpx.Response(200, content=b"<html>"))
    with pytest.raises(EmbeddingResponseError) as info:
        provider.embed_documents(["a"])
    assert (info.value.request_attempted, info.value.possibly_billed) == (True, True)
    assert info.value.reported_input_tokens is None


# --- outcome / accounting matrix through the processor --------------------------------


def _run_job(store: InMemoryJobStore, provider: Any, budget: EmbeddingRunBudget | None = None):
    budget = budget or EmbeddingRunBudget(max_tokens=1_000_000)
    return _run(store, provider, budget), budget


def test_matrix_pre_request_failure_is_not_an_attempt() -> None:
    oversized = [_chunk(0, "y" * (op.MAX_INPUT_BYTES + 100))]
    provider, rec = _provider(_usage_ok())
    store = InMemoryJobStore(chunks=oversized)
    result, budget = _run_job(store, provider)
    assert result.outcome is JobOutcome.FAILED  # terminal: no retry of a deterministic error
    assert rec.count == 0
    assert budget.requests_made == 0 and budget.tokens_used == 0
    assert store.calls[0].success is False and store.calls[0].input_tokens is None


def test_matrix_connection_never_established_counts_a_request_but_no_tokens() -> None:
    def responder(_r: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    provider, rec = _provider(responder)
    store = InMemoryJobStore(chunks=make_chunks(2))
    result, budget = _run_job(store, provider)
    assert result.outcome is JobOutcome.REQUEUED and rec.count == 1
    assert budget.requests_made == 1 and budget.tokens_used == 0
    assert budget.cost_used_usd == 0.0
    assert store.calls[0].input_tokens is None and store.calls[0].estimated_cost_usd is None


def test_matrix_timeout_after_sending_counts_the_estimate_but_persists_unknown() -> None:
    def responder(_r: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow")

    provider, rec = _provider(responder)
    store = InMemoryJobStore(chunks=make_chunks(2))
    result, budget = _run_job(store, provider)
    assert result.outcome is JobOutcome.REQUEUED and rec.count == 1
    assert budget.requests_made == 1 and budget.tokens_used > 0
    assert store.calls[0].input_tokens is None and store.calls[0].estimated_cost_usd is None
    assert result.tokens_used == 0  # an estimate is never reported as confirmed usage


def test_matrix_provider_error_status_counts_the_estimate_and_is_not_retried_inline() -> None:
    provider, rec = _provider(_status(500))
    store = InMemoryJobStore(chunks=make_chunks(2))
    result, budget = _run_job(store, provider)
    assert result.outcome is JobOutcome.REQUEUED and rec.count == 1
    assert budget.requests_made == 1 and budget.tokens_used > 0
    assert store.calls[0].input_tokens is None


def test_matrix_valid_response_uses_actual_usage_once() -> None:
    provider, rec = _provider(_usage_ok(11))
    store = InMemoryJobStore(chunks=make_chunks(2))
    result, budget = _run_job(store, provider)
    assert result.outcome is JobOutcome.COMPLETED
    assert rec.count == 1 and budget.requests_made == 1
    assert budget.tokens_used == 22 and result.tokens_used == 22  # not 44, not total+prompt
    assert store.calls[0].input_tokens == 22
    assert store.calls[0].estimated_cost_usd == pytest.approx(22 * PRICE)


def test_matrix_locally_rejected_response_uses_the_vendors_valid_usage() -> None:
    body = _ok_body(2, usage={"prompt_tokens": 33, "total_tokens": 33})
    body["data"].pop()  # wrong count: unusable, yet the vendor reported usage
    provider, rec = _provider(lambda _r: _json_response(200, body))
    store = InMemoryJobStore(chunks=make_chunks(2))
    result, budget = _run_job(store, provider)
    assert result.outcome is JobOutcome.FAILED  # deterministic: not retried
    assert rec.count == 1 and budget.requests_made == 1
    assert budget.tokens_used == 33 and result.tokens_used == 33
    assert store.calls[0].success is False and store.calls[0].input_tokens == 33
    assert store.calls[0].estimated_cost_usd == pytest.approx(33 * PRICE)
    assert store.embeddings == {}  # nothing unusable was stored


def test_matrix_locally_rejected_response_without_usage_counts_the_estimate_only() -> None:
    body = _ok_body(2)
    del body["usage"]
    body["data"].pop()
    provider, rec = _provider(lambda _r: _json_response(200, body))
    store = InMemoryJobStore(chunks=make_chunks(2))
    result, budget = _run_job(store, provider)
    assert result.outcome is JobOutcome.FAILED and rec.count == 1
    assert budget.requests_made == 1 and budget.tokens_used > 0
    assert store.calls[0].input_tokens is None and store.calls[0].estimated_cost_usd is None


def test_matrix_requests_are_never_double_counted_across_layers() -> None:
    cases = [
        _usage_ok(),
        _status(500),
        _status(401),
        _status(400),
        lambda _r: _json_response(200, {"data": "bad", "model": op.OPENAI_MODEL_ID}),
    ]
    for responder in cases:
        provider, rec = _provider(responder)
        _result, budget = _run_job(InMemoryJobStore(chunks=make_chunks(2)), provider)
        assert budget.requests_made == rec.count == 1


def test_partial_run_preserves_earlier_usage_when_a_later_batch_is_rejected_before_sending() -> (
    None
):
    chunks = [_chunk(0, "a short passage"), _chunk(1, "another"), _chunk(2, "z" * 9_000)]
    provider, rec = _provider(_usage_ok(11))
    store = InMemoryJobStore(chunks=chunks)
    result, budget = _run_job(store, provider)
    assert result.outcome is JobOutcome.FAILED
    assert rec.count == 1  # only the first batch was ever sent
    assert result.tokens_used == 22 and budget.tokens_used == 22 and budget.requests_made == 1
    assert len(store.embeddings) == 2  # the successful batch stays persisted
    assert [c.success for c in store.calls] == [True, False]
    assert store.calls[0].input_tokens == 22 and store.calls[1].input_tokens is None


def test_partial_run_preserves_earlier_usage_when_a_later_request_fails_ambiguously() -> None:
    state = {"n": 0}

    def responder(request: httpx.Request) -> httpx.Response:
        state["n"] += 1
        if state["n"] == 2:
            raise httpx.ReadTimeout("slow")
        n = len(json.loads(request.content)["input"])
        return _json_response(
            200, _ok_body(n, usage={"prompt_tokens": 7 * n, "total_tokens": 7 * n})
        )

    provider, rec = _provider(responder)
    store = InMemoryJobStore(chunks=make_chunks(4))
    result, budget = _run_job(store, provider)
    assert result.outcome is JobOutcome.REQUEUED and rec.count == 2
    assert result.tokens_used == 14  # confirmed usage only: the first batch
    assert budget.requests_made == 2 and budget.tokens_used > 14  # + the estimate for batch 2
    assert len(store.embeddings) == 2


# --- retry delays: trace through result, worker and attempt cap ---------------------------


def test_retry_after_is_carried_on_the_result_but_the_requeue_is_not_delayed() -> None:
    body = {"error": {"code": "rate_limit_exceeded"}}
    provider, rec = _provider(_status(429, body, {"Retry-After": "9"}))
    store = InMemoryJobStore(chunks=make_chunks(2))
    result, _budget = _run_job(store, provider)
    assert result.outcome is JobOutcome.REQUEUED
    assert result.abort_run is True and result.retry_after_seconds == 9.0
    assert rec.count == 1
    # The requeue passes no "not before" time: nothing durable expresses the
    # delay, so another invocation may claim the job immediately (see report).
    assert store.requeues[0]["refund_attempt"] is False
    assert set(store.requeues[0]) == {"classification", "message", "note", "refund_attempt"}


@pytest.mark.parametrize("header", [None, "soon", "-1", "Wed, 21 Oct 2026 07:28:00 GMT"])
def test_missing_invalid_or_date_form_retry_after_yields_no_delay(header: str | None) -> None:
    headers = {"Retry-After": header} if header is not None else None
    provider, _rec = _provider(_status(429, {"error": {"code": "slow_down"}}, headers))
    result, _budget = _run_job(InMemoryJobStore(chunks=make_chunks(2)), provider)
    assert result.outcome is JobOutcome.REQUEUED and result.retry_after_seconds is None


def test_quota_and_auth_failures_have_no_retry_delay_and_refund_the_attempt() -> None:
    for responder in (
        _status(429, {"error": {"code": "insufficient_quota"}}, {"Retry-After": "30"}),
        _status(401),
    ):
        provider, rec = _provider(responder)
        store = InMemoryJobStore(chunks=make_chunks(2))
        result, _budget = _run_job(store, provider)
        assert result.retry_after_seconds is None and result.abort_run is True
        assert store.requeues[0]["refund_attempt"] is True and rec.count == 1


def test_a_deterministic_response_error_is_never_retried() -> None:
    provider, rec = _provider(lambda _r: _json_response(200, {"model": "nope", "data": []}))
    store = InMemoryJobStore(chunks=make_chunks(2))
    result, _budget = _run_job(store, provider)
    assert result.outcome is JobOutcome.FAILED and store.requeues == []
    assert rec.count == 1 and store.failures[0]["classification"] == "deterministic"


def test_rate_limited_attempts_are_capped_and_each_consumes_an_attempt() -> None:
    provider, rec = _provider(_status(429, {"error": {"code": "rate_limit_exceeded"}}))
    store = InMemoryJobStore(chunks=make_chunks(2))
    outcomes = []
    for attempt in (1, 2, 3):
        outcomes.append(
            process_job(
                make_job(attempt_count=attempt),
                store=store,
                provider=provider,
                spec=SPEC,
                budget=EmbeddingRunBudget(max_tokens=1_000_000),
                config=ProcessorConfig(batch_size=2, max_attempts=3),
            ).outcome
        )
    assert outcomes == [JobOutcome.REQUEUED, JobOutcome.REQUEUED, JobOutcome.FAILED]
    assert rec.count == 3  # one HTTP request per attempt, then terminal
    assert all(r["refund_attempt"] is False for r in store.requeues)


def test_worker_reports_the_requested_delay_without_claiming_it_is_enforced(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from app.embeddings.processor import JobResult

    service = _FakeService(
        results=[
            JobResult(
                JobOutcome.REQUEUED,
                note="transient_failure_requeued",
                abort_run=True,
                retry_after_seconds=9.0,
            )
        ]
    )
    assert _call(["--max-tokens", "100"], service=service) == 0
    out = capsys.readouterr().out
    assert "9s" in out and "does not enforce" in out
    assert service.process_calls == 1  # a rate limit ends the run


# --- input boundaries ---------------------------------------------------------------


def _accepts(text: str) -> bool:
    provider, rec = _provider(lambda _r: _json_response(200, _ok_body(1)))
    try:
        provider.embed_query(text)
    except EmbeddingInputError:
        assert rec.count == 0  # rejected before any HTTP work
        return False
    return True


def test_the_size_limit_is_measured_in_utf8_bytes_not_characters() -> None:
    assert _accepts("a" * op.MAX_INPUT_BYTES)
    assert not _accepts("a" * (op.MAX_INPUT_BYTES + 1))
    two_byte = "é"  # 2 bytes
    assert _accepts(two_byte * (op.MAX_INPUT_BYTES // 2))
    assert not _accepts(two_byte * (op.MAX_INPUT_BYTES // 2 + 1))  # 4,001 chars but 8,002 bytes
    three_byte = "语"  # 3 bytes
    assert _accepts(three_byte * (op.MAX_INPUT_BYTES // 3))
    assert not _accepts(three_byte * (op.MAX_INPUT_BYTES // 3 + 1))
    four_byte = "\U0001f600"
    assert _accepts(four_byte * (op.MAX_INPUT_BYTES // 4))
    assert not _accepts(four_byte * (op.MAX_INPUT_BYTES // 4 + 1))


def test_unencodable_and_blank_text_is_rejected_before_any_request() -> None:
    assert not _accepts("\ud800 lone surrogate")
    assert not _accepts("   \t\n")
    assert not _accepts("")


def test_the_document_header_counts_toward_the_limit() -> None:
    content = "c" * (op.MAX_INPUT_BYTES - 200)
    short_title = build_embedding_input(document_title="T", section_path=None, content=content)
    long_title = build_embedding_input(
        document_title="T" * 400, section_path="S" * 400, content=content
    )
    assert _accepts(short_title)
    assert not _accepts(long_title)


def test_aggregate_batch_cap_is_enforced_by_the_adapter_and_planned_by_the_processor() -> None:
    per_input = op.MAX_INPUT_BYTES
    needed = op.MAX_TOTAL_INPUT_BYTES // per_input + 1
    provider, rec = _provider(_usage_ok(), max_batch_size=op.MAX_INPUTS_PER_REQUEST)
    with pytest.raises(EmbeddingInputError, match="total"):
        provider.embed_documents(["x" * per_input] * needed)
    assert rec.count == 0

    # The processor splits the same work into batches that each fit.
    pending = [(_chunk(i, "x" * per_input), "x" * per_input, "fp") for i in range(needed)]
    batches = _plan_batches(pending, batch_size=op.MAX_INPUTS_PER_REQUEST, provider=provider)
    assert len(batches) == 2 and sum(len(b) for b in batches) == needed
    for batch in batches:
        assert sum(provider.input_size(item[1]) for item in batch) <= op.MAX_TOTAL_INPUT_BYTES


def test_batch_planning_rules() -> None:
    stub = SimpleNamespace(input_size=lambda text: len(text), max_batch_input_size=10)
    items = [(_chunk(i, "x"), text, "fp") for i, text in enumerate(["aaaa", "bbbb", "cccc", "d"])]
    sizes = [[len(i[1]) for i in b] for b in _plan_batches(items, batch_size=64, provider=stub)]
    assert sizes == [[4, 4], [4, 1]]  # split on the size cap
    counts = [len(b) for b in _plan_batches(items, batch_size=3, provider=SimpleNamespace())]
    assert counts == [3, 1]  # no size hooks: count limit only
    big = [(_chunk(0, "x"), "x" * 50, "fp"), (_chunk(1, "x"), "y", "fp")]
    batches = _plan_batches(big, batch_size=64, provider=stub)
    assert [len(b) for b in batches] == [1, 1]  # an oversized input stands alone
    assert _plan_batches([], batch_size=4, provider=stub) == []


def test_oversized_work_never_reaches_the_provider_and_is_never_truncated() -> None:
    chunks = [_chunk(0, "w" * (op.MAX_INPUT_BYTES + 1))]
    provider, rec = _provider(_usage_ok())
    result, budget = _run_job(InMemoryJobStore(chunks=chunks), provider)
    assert result.outcome is JobOutcome.FAILED and rec.count == 0 and budget.requests_made == 0


# --- policy and configuration safeguards -----------------------------------------------


class _Cfg(SimpleNamespace):
    pass


def _cfg(**overrides: Any) -> Any:
    values: dict[str, Any] = {
        "environment": "production",
        "embeddings_enabled": True,
        "embedding_provider": "openai",
        "embedding_model_id": "text-embedding-3-large",
        "embedding_model_version": "alias-test",
        "embedding_dimension": 1024,
        "embedding_batch_size": 16,
        "embedding_api_key": FAKE_KEY,
        "embedding_request_timeout_seconds": 30.0,
        "embedding_external_policy_approval": OPENAI_POLICY_APPROVAL_VALUE,
        "openai_api_key": "sk-LLM-KEY-MUST-NEVER-BE-USED",
    }
    values.update(overrides)
    return _Cfg(**values)


@pytest.mark.parametrize(
    "ack",
    [
        " openai:text-embedding-3-large",
        "openai:text-embedding-3-large ",
        "OPENAI:text-embedding-3-large",
        "openai:text-embedding-3-large,voyage:voyage-4",
        "true",
        "1",
        "",
    ],
)
def test_the_acknowledgement_is_an_exact_match_not_a_truthy_flag(ack: str) -> None:
    from app.embeddings.errors import EmbeddingConfigurationError

    with pytest.raises(EmbeddingConfigurationError, match="policy"):
        get_embedding_provider(_cfg(embedding_external_policy_approval=ack))


def test_an_openai_acknowledgement_grants_nothing_to_another_vendor() -> None:
    from app.embeddings.errors import EmbeddingConfigurationError

    with pytest.raises(EmbeddingConfigurationError, match="not an approved"):
        get_embedding_provider(_cfg(embedding_provider="voyage"))


def test_blank_embedding_numbers_in_the_environment_do_not_break_startup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (
        "EMBEDDING_DIMENSION",
        "EMBEDDING_BATCH_SIZE",
        "EMBEDDING_JOB_MAX_ATTEMPTS",
        "EMBEDDING_STALE_PROCESSING_AFTER_SECONDS",
        "EMBEDDING_REQUEST_TIMEOUT_SECONDS",
    ):
        monkeypatch.setenv(name, "")
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.embedding_dimension is None
    assert settings.embedding_batch_size == 64
    assert settings.embedding_job_max_attempts == 3
    assert settings.embedding_stale_processing_after_seconds == 900
    assert settings.embedding_request_timeout_seconds == 30.0
    assert settings.embeddings_enabled is False


def test_a_real_value_still_overrides_the_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EMBEDDING_DIMENSION", "1024")
    monkeypatch.setenv("EMBEDDING_REQUEST_TIMEOUT_SECONDS", "12.5")
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.embedding_dimension == 1024
    assert settings.embedding_request_timeout_seconds == 12.5


def test_the_shipped_env_example_loads_and_keeps_embeddings_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.embeddings.errors import EmbeddingConfigurationError

    for name in list(__import__("os").environ):
        if name.startswith("EMBEDDING") or name == "EMBEDDINGS_ENABLED":
            monkeypatch.delenv(name, raising=False)
    example = Path(__file__).resolve().parents[3] / ".env.example"
    assert example.is_file()
    settings = Settings(_env_file=str(example))  # type: ignore[call-arg]
    assert settings.embeddings_enabled is False
    assert settings.embedding_external_policy_approval in (None, "")
    with pytest.raises(EmbeddingConfigurationError, match="disabled"):
        get_embedding_provider(settings)


def test_error_text_stays_secret_and_content_free_with_the_new_evidence_fields() -> None:
    secret = "SECRET-DOCUMENT-TEXT-424242"
    body = {"error": {"message": secret + FAKE_KEY, "code": "x"}}
    provider, _rec = _provider(_status(500, body))
    with pytest.raises(EmbeddingTransientError) as info:
        provider.embed_documents([secret])
    rendered = f"{info.value!s} {info.value!r} {dataclasses.asdict(SPEC)}"
    assert secret not in rendered and FAKE_KEY not in rendered
    assert isinstance(info.value.possibly_billed, bool)
    assert info.value.reported_input_tokens is None


def test_rate_limit_error_type_is_still_distinct_from_quota_errors() -> None:
    plain, _r1 = _provider(_status(429, {"error": {"code": "rate_limit_exceeded"}}))
    with pytest.raises(EmbeddingRateLimitError):
        plain.embed_documents(["x"])
    quota, _r2 = _provider(_status(429, {"error": {"code": "credit_balance_exhausted"}}))
    with pytest.raises(EmbeddingAuthError) as info:
        quota.embed_documents(["x"])
    assert not isinstance(info.value, EmbeddingRateLimitError)
