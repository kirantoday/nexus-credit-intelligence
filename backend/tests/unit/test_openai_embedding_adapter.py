"""Mocked tests for the OpenAI embedding adapter (Milestone 10D.2).

Everything here runs against `httpx.MockTransport`; no request leaves the
process, no key exists, no database is touched, and no provider is called.

Network guard (module-wide, autouse): socket `connect`/`connect_ex`,
`socket.create_connection`, `socket.getaddrinfo` and the real
`httpx.HTTPTransport.handle_request` are replaced with functions that raise.
Scope and gaps: it catches Python-level connection attempts made *in this
test process* through those entry points. It does not cover UDP `sendto`,
other processes, native code that opens sockets directly, or a caller that
captured the originals before the patch. It is a tripwire that makes an
accidental real request fail loudly, not proof of network isolation.

The key used below is a fake string. Test inputs are synthetic text.
"""

from __future__ import annotations

import json
import math
import socket
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from app.config import Settings
from app.embeddings import openai_provider as op
from app.embeddings.budget import EmbeddingRunBudget
from app.embeddings.dimensions import EMBEDDING_COLUMN_DIMENSION, EmbeddingModelSpec
from app.embeddings.errors import (
    EmbeddingAuthError,
    EmbeddingConfigurationError,
    EmbeddingDimensionMismatchError,
    EmbeddingInputError,
    EmbeddingRateLimitError,
    EmbeddingResponseError,
    EmbeddingTransientError,
    safe_summary,
)
from app.embeddings.factory import OPENAI_POLICY_APPROVAL_VALUE, get_embedding_provider
from app.embeddings.openai_provider import OpenAIEmbeddingProvider
from app.embeddings.pricing import estimate_cost_usd, lookup_pricing
from app.embeddings.processor import JobOutcome, ProcessorConfig, process_job
from app.retrieval.eligibility import (
    EligibilityFacts,
    EligibilityReason,
    evaluate_eligibility,
)

from .embedding_support import InMemoryJobStore, make_chunks, make_job

FAKE_KEY = "sk-test-NOT-A-REAL-KEY-0000"
SECRET_TEXT = "SECRET-DOCUMENT-TEXT-98765"
DIM = EMBEDDING_COLUMN_DIMENSION
SPEC = EmbeddingModelSpec(
    provider=op.OPENAI_PROVIDER_NAME,
    model_id=op.OPENAI_MODEL_ID,
    model_version="alias-test",
    dimension=DIM,
)


# --- network tripwire ---------------------------------------------------------------


def _blocked(*_args: object, **_kwargs: object) -> Any:
    raise RuntimeError("network access attempted during a unit test")


@pytest.fixture(autouse=True)
def _network_tripwire(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(socket.socket, "connect", _blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)
    monkeypatch.setattr(socket, "getaddrinfo", _blocked)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", _blocked)


def test_tripwire_blocks_a_direct_connection_attempt() -> None:
    with pytest.raises(RuntimeError, match="network access attempted"):
        socket.create_connection(("127.0.0.1", 9))


# --- helpers ------------------------------------------------------------------------


def _unit(position: int) -> list[float]:
    vector = [0.0] * DIM
    vector[position % DIM] = 1.0
    return vector


def _ok_body(
    count: int,
    *,
    order: list[int] | None = None,
    usage: Any = None,
    model: str = op.OPENAI_MODEL_ID,
    vectors: list[Any] | None = None,
) -> dict[str, Any]:
    indexes = order if order is not None else list(range(count))
    data = [
        {
            "object": "embedding",
            "index": index,
            "embedding": vectors[index] if vectors is not None else _unit(index),
        }
        for index in indexes
    ]
    body: dict[str, Any] = {"object": "list", "data": data, "model": model}
    body["usage"] = usage if usage is not None else {"prompt_tokens": 7, "total_tokens": 7}
    return body


class Recorder:
    def __init__(self, responder: Callable[[httpx.Request], httpx.Response]) -> None:
        self.responder = responder
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.responder(request)

    @property
    def count(self) -> int:
        return len(self.requests)

    def payload(self, index: int = 0) -> dict[str, Any]:
        loaded = json.loads(self.requests[index].content)
        assert isinstance(loaded, dict)
        return loaded


def _provider(
    responder: Callable[[httpx.Request], httpx.Response], **kwargs: Any
) -> tuple[OpenAIEmbeddingProvider, Recorder]:
    recorder = Recorder(responder)
    client = httpx.Client(transport=httpx.MockTransport(recorder))
    params: dict[str, Any] = {
        "api_key": FAKE_KEY,
        "model_version": "alias-test",
        "max_batch_size": 64,
        "client": client,
    }
    params.update(kwargs)
    return OpenAIEmbeddingProvider(**params), recorder


def _json_response(status: int, body: Any, headers: dict[str, str] | None = None) -> httpx.Response:
    return httpx.Response(status, json=body, headers=headers)


def _ok_for(texts_count: int) -> Callable[[httpx.Request], httpx.Response]:
    return lambda _req: _json_response(200, _ok_body(texts_count))


# --- request construction -----------------------------------------------------------


def test_document_request_uses_the_approved_model_width_encoding_and_fixed_url() -> None:
    provider, rec = _provider(_ok_for(2))
    result = provider.embed_documents(["first passage", "second passage"])

    assert rec.count == 1
    request = rec.requests[0]
    assert request.method == "POST"
    assert str(request.url) == "https://api.openai.com/v1/embeddings"
    assert request.headers["authorization"] == f"Bearer {FAKE_KEY}"
    assert rec.payload() == {
        "model": "text-embedding-3-large",
        "input": ["first passage", "second passage"],
        "dimensions": 1024,
        "encoding_format": "float",
    }
    assert result.model_id == "text-embedding-3-large"
    assert result.model_version == "alias-test"
    assert result.dimension == 1024
    assert len(result.vectors) == 2


def test_query_uses_the_same_call_semantics_as_documents() -> None:
    provider, rec = _provider(_ok_for(1))
    result = provider.embed_query("what are the negative covenants?")
    assert rec.payload() == {
        "model": "text-embedding-3-large",
        "input": ["what are the negative covenants?"],
        "dimensions": 1024,
        "encoding_format": "float",
    }
    assert len(result.vectors) == 1


def test_provider_exposes_the_embedding_provider_contract() -> None:
    provider, _rec = _provider(_ok_for(1))
    assert provider.provider_name == "openai"
    assert provider.model_id == "text-embedding-3-large"
    assert provider.model_version == "alias-test"
    assert provider.dimension == 1024
    assert provider.max_batch_size == 64


# --- successful response handling ---------------------------------------------------


def test_results_are_reassembled_in_input_order_from_response_indices() -> None:
    provider, _rec = _provider(
        lambda _r: _json_response(200, _ok_body(3, order=[2, 0, 1])),
    )
    result = provider.embed_documents(["a", "b", "c"])
    assert [v.index(1.0) for v in result.vectors] == [0, 1, 2]


def test_integer_valued_numbers_are_accepted_and_returned_as_floats() -> None:
    vector: list[Any] = [0] * DIM
    vector[0] = 1
    provider, _rec = _provider(
        lambda _r: _json_response(200, _ok_body(1, vectors=[vector])),
    )
    result = provider.embed_query("x")
    assert result.vectors[0][0] == 1.0 and isinstance(result.vectors[0][0], float)


# --- response validation (fail closed) ----------------------------------------------


def _post_with_body(body: Any = None, *, raw: bytes | None = None, count: int = 2) -> None:
    def responder(_r: httpx.Request) -> httpx.Response:
        if raw is not None:
            return httpx.Response(200, content=raw)
        return _json_response(200, body)

    provider, _rec = _provider(responder)
    provider.embed_documents([f"text {i}" for i in range(count)])


def test_wrong_item_count_is_a_contract_violation() -> None:
    with pytest.raises(EmbeddingDimensionMismatchError):
        _post_with_body(_ok_body(1), count=2)


def test_wrong_vector_width_is_a_contract_violation() -> None:
    short = [1.0] + [0.0] * (DIM - 2)
    with pytest.raises(EmbeddingDimensionMismatchError):
        _post_with_body(_ok_body(2, vectors=[short, short]))


def test_response_naming_a_different_model_is_rejected() -> None:
    with pytest.raises(EmbeddingDimensionMismatchError):
        _post_with_body(_ok_body(2, model="text-embedding-3-small"))


@pytest.mark.parametrize(
    "order",
    [[0, 0], [0, 2], [-1, 1], [1, 1]],
    ids=["duplicate", "out-of-range", "negative", "missing-0"],
)
def test_duplicate_missing_or_out_of_range_indices_are_rejected(order: list[int]) -> None:
    body = _ok_body(2, order=order, vectors=[_unit(0), _unit(1), _unit(2)])
    with pytest.raises(EmbeddingResponseError):
        _post_with_body(body)


@pytest.mark.parametrize("bad_index", ["0", 0.0, True, None])
def test_non_integer_index_is_rejected(bad_index: Any) -> None:
    body = _ok_body(2)
    body["data"][0]["index"] = bad_index
    with pytest.raises(EmbeddingResponseError):
        _post_with_body(body)


def test_malformed_json_and_wrong_top_level_shapes_are_rejected() -> None:
    with pytest.raises(EmbeddingResponseError):
        _post_with_body(raw=b"<html>not json</html>")
    with pytest.raises(EmbeddingResponseError):
        _post_with_body(["not", "an", "object"])
    with pytest.raises(EmbeddingResponseError):
        _post_with_body({"model": op.OPENAI_MODEL_ID, "data": "nope"})
    body = _ok_body(2)
    body["data"][1] = "not an object"
    with pytest.raises(EmbeddingResponseError):
        _post_with_body(body)


def test_base64_or_non_list_embeddings_are_rejected() -> None:
    body = _ok_body(2)
    body["data"][0]["embedding"] = "AAAA"
    with pytest.raises(EmbeddingResponseError):
        _post_with_body(body)


def test_non_numeric_bool_and_non_finite_values_are_rejected() -> None:
    for bad in ("1.0", True, None, [1.0]):
        vector: list[Any] = _unit(0)
        vector[5] = bad
        with pytest.raises(EmbeddingResponseError):
            _post_with_body(_ok_body(2, vectors=[vector, _unit(1)]))
    for literal in (b"NaN", b"Infinity", b"-Infinity"):
        zeros = b"0.0," * (DIM - 2)
        good = json.dumps(_unit(1)).encode()
        raw = (
            b'{"model":"text-embedding-3-large","data":[{"index":0,"embedding":['
            + literal
            + b","
            + zeros
            + b"1.0]},{"
            + b'"index":1,"embedding":'
            + good
            + b'}],"usage":{"prompt_tokens":1,"total_tokens":1}}'
        )
        with pytest.raises(EmbeddingResponseError):
            _post_with_body(raw=raw)


def test_vectors_that_are_not_unit_length_are_rejected_not_rescaled() -> None:
    half = [0.5] + [0.0] * (DIM - 1)
    with pytest.raises(EmbeddingResponseError, match="unit length"):
        _post_with_body(_ok_body(2, vectors=[half, _unit(1)]))


# --- usage ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("usage", "expected"),
    [
        ({"prompt_tokens": 12, "total_tokens": 12}, 12),
        ({"prompt_tokens": 12}, 12),
        ({"prompt_tokens": 0, "total_tokens": 0}, 0),
        (None, 7),  # the helper's default usage
    ],
)
def test_aggregate_usage_is_prompt_tokens_not_a_sum(usage: Any, expected: int) -> None:
    body = _ok_body(2, usage=usage)
    provider, _rec = _provider(lambda _r: _json_response(200, body))
    assert provider.embed_documents(["a", "b"]).input_tokens == expected


@pytest.mark.parametrize(
    "usage",
    [
        "12",
        [],
        {},
        {"total_tokens": 5},
        {"prompt_tokens": "12", "total_tokens": 12},
        {"prompt_tokens": -1, "total_tokens": -1},
        {"prompt_tokens": True, "total_tokens": True},
        {"prompt_tokens": 12.5, "total_tokens": 12.5},
        {"prompt_tokens": 5, "total_tokens": 6},  # inconsistent: unknown, never summed
    ],
)
def test_missing_or_malformed_usage_is_unknown_never_zero(usage: Any) -> None:
    body = _ok_body(2)
    body["usage"] = usage
    provider, _rec = _provider(lambda _r: _json_response(200, body))
    result = provider.embed_documents(["a", "b"])
    assert result.input_tokens is None
    assert len(result.vectors) == 2  # valid vectors are still returned


def test_absent_usage_key_is_unknown() -> None:
    body = _ok_body(2)
    del body["usage"]
    provider, _rec = _provider(lambda _r: _json_response(200, body))
    assert provider.embed_documents(["a", "b"]).input_tokens is None


# --- error mapping ------------------------------------------------------------------


def _status(status: int, body: Any = None, headers: dict[str, str] | None = None) -> Any:
    return lambda _r: _json_response(status, body if body is not None else {}, headers)


@pytest.mark.parametrize(
    ("status", "error_type"),
    [
        (400, EmbeddingInputError),
        (418, EmbeddingInputError),
        (401, EmbeddingAuthError),
        (403, EmbeddingAuthError),
        (404, EmbeddingConfigurationError),
        (408, EmbeddingTransientError),
        (500, EmbeddingTransientError),
        (502, EmbeddingTransientError),
        (503, EmbeddingTransientError),
        (504, EmbeddingTransientError),
        (302, EmbeddingConfigurationError),
    ],
)
def test_http_statuses_map_to_the_existing_error_types(status: int, error_type: type) -> None:
    provider, rec = _provider(_status(status))
    with pytest.raises(error_type):
        provider.embed_documents(["x"])
    assert rec.count == 1  # exactly one attempt: no retry inside the adapter


def test_plain_rate_limit_is_retryable_and_carries_retry_after() -> None:
    body = {"error": {"code": "rate_limit_exceeded", "type": "requests"}}
    provider, rec = _provider(_status(429, body, {"Retry-After": "7"}))
    with pytest.raises(EmbeddingRateLimitError) as info:
        provider.embed_documents(["x"])
    assert info.value.retry_after_seconds == 7.0
    assert info.value.classification == "transient"
    assert rec.count == 1


@pytest.mark.parametrize(
    ("header", "expected"),
    [("abc", None), ("-3", None), ("nan", None), ("99999", 3600.0), (None, None)],
)
def test_retry_after_is_parsed_defensively(header: str | None, expected: float | None) -> None:
    headers = {"Retry-After": header} if header is not None else None
    provider, _rec = _provider(_status(429, {"error": {"code": "slow_down"}}, headers))
    with pytest.raises(EmbeddingRateLimitError) as info:
        provider.embed_documents(["x"])
    assert info.value.retry_after_seconds == expected


def test_429_without_a_json_body_is_treated_as_a_rate_limit() -> None:
    provider, _rec = _provider(lambda _r: httpx.Response(429, content=b"slow down"))
    with pytest.raises(EmbeddingRateLimitError):
        provider.embed_documents(["x"])


@pytest.mark.parametrize(
    "error",
    [
        {"code": "credit_balance_exhausted"},
        {"code": "organization_spend_limit_exceeded"},
        {"code": "project_spend_limit_exceeded"},
        {"code": "organization_usage_limit_exceeded"},
        {"code": "insufficient_quota"},
        {"type": "insufficient_quota", "code": "something_else"},
    ],
)
def test_quota_and_spend_429s_are_terminal_not_retried_as_rate_limits(
    error: dict[str, str]
) -> None:
    provider, rec = _provider(_status(429, {"error": error}))
    with pytest.raises(EmbeddingAuthError) as info:
        provider.embed_documents(["x"])
    assert not isinstance(info.value, EmbeddingTransientError)
    assert info.value.classification == "deterministic"
    assert rec.count == 1


@pytest.mark.parametrize(
    "exception",
    [
        httpx.ReadTimeout("t"),
        httpx.ConnectTimeout("t"),
        httpx.ConnectError("c"),
        httpx.RemoteProtocolError("p"),
        httpx.ReadError("r"),
    ],
)
def test_timeouts_and_network_failures_are_transient_with_one_attempt(
    exception: Exception,
) -> None:
    def responder(_r: httpx.Request) -> httpx.Response:
        raise exception

    provider, rec = _provider(responder)
    with pytest.raises(EmbeddingTransientError):
        provider.embed_documents(["x"])
    assert rec.count == 1


def test_redirects_are_never_followed_and_the_key_is_not_resent() -> None:
    def responder(_r: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"Location": "https://evil.example/steal"})

    provider, rec = _provider(responder)
    with pytest.raises(EmbeddingConfigurationError, match="redirect"):
        provider.embed_documents(["x"])
    assert rec.count == 1
    assert all(r.url.host == "api.openai.com" for r in rec.requests)


def test_diagnostics_never_contain_content_keys_bodies_or_vectors() -> None:
    hostile_body = {"error": {"message": f"bad input {SECRET_TEXT} {FAKE_KEY}", "code": "x"}}
    cases: list[Callable[[httpx.Request], httpx.Response]] = [
        _status(400, hostile_body),
        _status(401, hostile_body),
        _status(429, hostile_body),
        _status(500, hostile_body),
        lambda _r: httpx.Response(200, content=f"{SECRET_TEXT} {FAKE_KEY}".encode()),
    ]
    for responder in cases:
        provider, _rec = _provider(responder)
        with pytest.raises(Exception) as info:  # noqa: B017 - any mapped error type
            provider.embed_documents([SECRET_TEXT])
        text = f"{info.value!s} {info.value!r} {safe_summary(info.value)}"
        assert SECRET_TEXT not in text and FAKE_KEY not in text
    provider, _rec = _provider(_ok_for(1))
    assert FAKE_KEY not in repr(provider) and "redacted" in repr(provider)


# --- local input validation (no request is sent) -----------------------------------


@pytest.mark.parametrize(
    "texts",
    [
        [],
        [""],
        ["   \n"],
        ["ok", ""],
        ["x" * (op.MAX_INPUT_CHARS + 1)],
        ["x"] * 3,  # exceeds a batch limit of 2 in the test below
    ],
)
def test_invalid_inputs_are_rejected_before_any_request(texts: list[str]) -> None:
    provider, rec = _provider(_ok_for(1), max_batch_size=2)
    with pytest.raises(EmbeddingInputError):
        provider.embed_documents(texts)
    assert rec.count == 0


def test_non_string_input_and_aggregate_size_are_rejected_locally() -> None:
    provider, rec = _provider(_ok_for(1))
    with pytest.raises(EmbeddingInputError):
        provider.embed_documents([123])  # type: ignore[list-item]
    big = "x" * op.MAX_INPUT_CHARS
    needed = op.MAX_TOTAL_INPUT_CHARS // op.MAX_INPUT_CHARS + 1
    with pytest.raises(EmbeddingInputError):
        OpenAIEmbeddingProvider(
            api_key=FAKE_KEY,
            model_version="v",
            max_batch_size=op.MAX_INPUTS_PER_REQUEST,
            client=httpx.Client(transport=httpx.MockTransport(rec)),
        ).embed_documents([big] * needed)
    assert rec.count == 0


def test_provider_side_input_rejection_is_terminal_and_never_truncates() -> None:
    body = {"error": {"code": "context_length_exceeded", "message": SECRET_TEXT}}
    provider, rec = _provider(_status(400, body))
    with pytest.raises(EmbeddingInputError) as info:
        provider.embed_documents(["a long but locally acceptable passage"])
    assert info.value.classification == "deterministic"
    assert rec.count == 1
    assert rec.payload()["input"] == ["a long but locally acceptable passage"]  # sent unchanged


# --- construction, credentials, lifecycle -------------------------------------------


@pytest.mark.parametrize("key", ["", "   ", "has space", "line\nbreak", "tab\tkey"])
def test_malformed_or_missing_key_is_a_configuration_error(key: str) -> None:
    with pytest.raises(EmbeddingConfigurationError):
        OpenAIEmbeddingProvider(api_key=key, model_version="v")


@pytest.mark.parametrize(
    "overrides",
    [
        {"model_version": "  "},
        {"dimension": 768},
        {"dimension": 3072},
        {"max_batch_size": 0},
        {"max_batch_size": op.MAX_INPUTS_PER_REQUEST + 1},
        {"timeout_seconds": 0},
        {"timeout_seconds": -1},
        {"timeout_seconds": op.MAX_TIMEOUT_SECONDS + 1},
        {"timeout_seconds": math.nan},
        {"timeout_seconds": math.inf},
    ],
)
def test_invalid_construction_arguments_fail_closed(overrides: dict[str, Any]) -> None:
    params: dict[str, Any] = {"api_key": FAKE_KEY, "model_version": "v"}
    params.update(overrides)
    with pytest.raises(EmbeddingConfigurationError):
        OpenAIEmbeddingProvider(**params)


def test_construction_creates_no_client_and_does_no_network_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def explode(*_a: object, **_k: object) -> None:
        raise AssertionError("httpx.Client must not be created at construction")

    monkeypatch.setattr(op.httpx, "Client", explode)
    provider = OpenAIEmbeddingProvider(api_key=FAKE_KEY, model_version="v")
    provider.close()  # nothing to close; must not raise


def test_owned_client_is_created_lazily_with_safe_settings_and_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    made: list[httpx.Client] = []
    captured: dict[str, Any] = {}
    real_client = httpx.Client  # `op.httpx` is the same module object: capture first

    def factory(**kwargs: Any) -> httpx.Client:
        captured.update(kwargs)
        client = real_client(transport=httpx.MockTransport(_ok_for(1)))
        made.append(client)
        return client

    monkeypatch.setattr(op.httpx, "Client", factory)
    provider = OpenAIEmbeddingProvider(api_key=FAKE_KEY, model_version="v", timeout_seconds=12)
    assert made == []
    provider.embed_query("x")
    assert len(made) == 1
    provider.embed_query("y")
    assert len(made) == 1  # reused, not recreated per call
    assert captured["follow_redirects"] is False
    assert captured["timeout"].connect == 12 and captured["timeout"].read == 12
    provider.close()
    assert made[0].is_closed
    provider.close()  # idempotent


def test_injected_client_is_not_closed_by_the_provider() -> None:
    client = httpx.Client(transport=httpx.MockTransport(_ok_for(1)))
    with OpenAIEmbeddingProvider(api_key=FAKE_KEY, model_version="v", client=client) as provider:
        provider.embed_query("x")
    assert not client.is_closed
    client.close()


def test_per_request_timeout_is_explicit_and_finite() -> None:
    seen: dict[str, Any] = {}

    def responder(request: httpx.Request) -> httpx.Response:
        seen.update(request.extensions["timeout"])
        return _json_response(200, _ok_body(1))

    provider, _rec = _provider(responder, timeout_seconds=9)
    provider.embed_query("x")
    assert seen == {"connect": 9.0, "read": 9.0, "write": 9.0, "pool": 9.0}


# --- factory and settings -----------------------------------------------------------


class _Cfg:
    def __init__(self, **overrides: Any) -> None:
        self.environment = "production"
        self.embeddings_enabled = True
        self.embedding_provider = "openai"
        self.embedding_model_id = "text-embedding-3-large"
        self.embedding_model_version = "alias-test"
        self.embedding_dimension = DIM
        self.embedding_batch_size = 16
        self.embedding_api_key: Any = FAKE_KEY
        self.embedding_request_timeout_seconds = 30.0
        self.embedding_external_policy_approval: str | None = OPENAI_POLICY_APPROVAL_VALUE
        self.openai_api_key = "sk-LLM-KEY-MUST-NEVER-BE-USED"
        for name, value in overrides.items():
            setattr(self, name, value)


def test_factory_builds_the_openai_provider_only_when_every_prerequisite_is_present() -> None:
    provider, spec = get_embedding_provider(_Cfg())  # type: ignore[arg-type]
    assert isinstance(provider, OpenAIEmbeddingProvider)
    assert provider.max_batch_size == 16
    assert provider._client is None  # no client, no network object yet
    assert spec == EmbeddingModelSpec("openai", "text-embedding-3-large", "alias-test", DIM)


def test_factory_accepts_a_pydantic_secret_and_never_the_llm_key() -> None:
    from pydantic import SecretStr

    provider, _spec = get_embedding_provider(_Cfg(embedding_api_key=SecretStr(FAKE_KEY)))  # type: ignore[arg-type]
    assert FAKE_KEY not in repr(provider)
    with pytest.raises(EmbeddingConfigurationError, match="EMBEDDING_API_KEY"):
        # The LLM key is present on the settings object and must not be used.
        get_embedding_provider(_Cfg(embedding_api_key=None))  # type: ignore[arg-type]
    for blank in ("", "   ", SecretStr("")):
        with pytest.raises(EmbeddingConfigurationError, match="EMBEDDING_API_KEY"):
            get_embedding_provider(_Cfg(embedding_api_key=blank))  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"embeddings_enabled": False}, "disabled"),
        ({"embedding_provider": None}, "EMBEDDING_PROVIDER"),
        ({"embedding_dimension": None}, "EMBEDDING_DIMENSION"),
        ({"embedding_dimension": 768}, "column width"),
        ({"embedding_model_id": "text-embedding-3-small"}, "only 'text-embedding-3-large'"),
        ({"embedding_model_version": None}, "EMBEDDING_MODEL_VERSION"),
        ({"embedding_model_version": "  "}, "EMBEDDING_MODEL_VERSION"),
        ({"embedding_external_policy_approval": None}, "policy"),
        ({"embedding_external_policy_approval": "openai:other"}, "policy"),
        ({"embedding_external_policy_approval": "voyage:voyage-4"}, "policy"),
        ({"embedding_provider": "voyage"}, "not an approved"),
        ({"embedding_provider": "OPENAI"}, "not an approved"),
    ],
)
def test_factory_fails_closed_without_each_prerequisite(
    overrides: dict[str, Any], match: str
) -> None:
    with pytest.raises(EmbeddingConfigurationError, match=match):
        get_embedding_provider(_Cfg(**overrides))  # type: ignore[arg-type]


def test_disabled_embeddings_never_construct_a_live_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def explode(*_a: object, **_k: object) -> None:
        raise AssertionError("the OpenAI provider must not be constructed when disabled")

    monkeypatch.setattr(OpenAIEmbeddingProvider, "__init__", explode)
    monkeypatch.setattr(op.httpx, "Client", explode)
    with pytest.raises(EmbeddingConfigurationError, match="disabled"):
        get_embedding_provider(_Cfg(embeddings_enabled=False))  # type: ignore[arg-type]


def test_fake_provider_remains_local_and_test_only() -> None:
    for environment in ("staging", "production"):
        with pytest.raises(EmbeddingConfigurationError, match="local or test"):
            get_embedding_provider(_Cfg(embedding_provider="fake", environment=environment))  # type: ignore[arg-type]
    provider, _spec = get_embedding_provider(_Cfg(embedding_provider="fake", environment="test"))  # type: ignore[arg-type]
    assert provider.provider_name == "fake"


def test_settings_defaults_keep_embeddings_off_and_secrets_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (
        "EMBEDDINGS_ENABLED",
        "EMBEDDING_PROVIDER",
        "EMBEDDING_API_KEY",
        "EMBEDDING_EXTERNAL_POLICY_APPROVAL",
        "EMBEDDING_REQUEST_TIMEOUT_SECONDS",
    ):
        monkeypatch.delenv(name, raising=False)
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.embeddings_enabled is False
    assert settings.embedding_provider is None
    assert settings.embedding_api_key is None
    assert settings.embedding_external_policy_approval is None
    assert settings.embedding_request_timeout_seconds == 30.0
    keyed = Settings(_env_file=None, embedding_api_key="sk-hidden-value")  # type: ignore[call-arg]
    assert "sk-hidden-value" not in repr(keyed) and "sk-hidden-value" not in str(keyed)


# --- pricing ------------------------------------------------------------------------


def test_openai_price_is_the_standard_synchronous_rate_in_usd_per_million_tokens() -> None:
    pricing = lookup_pricing(provider="openai", model_id="text-embedding-3-large")
    assert pricing is not None and pricing.input_usd_per_million_tokens == 0.13
    assert estimate_cost_usd(
        provider="openai", model_id="text-embedding-3-large", input_tokens=1_000_000
    ) == pytest.approx(0.13)
    assert estimate_cost_usd(
        provider="openai", model_id="text-embedding-3-large", input_tokens=10_000_000
    ) == pytest.approx(1.30)
    # Unknown usage and unknown models stay unknown, never zero; Batch API's
    # discounted rate is not applied.
    assert (
        estimate_cost_usd(provider="openai", model_id="text-embedding-3-large", input_tokens=None)
        is None
    )
    assert (
        estimate_cost_usd(provider="openai", model_id="text-embedding-3-small", input_tokens=5)
        is None
    )


# --- processor integration with the real adapter on a mock transport ------------------


def _config() -> ProcessorConfig:
    return ProcessorConfig(batch_size=2, max_attempts=3)


def _run(
    store: InMemoryJobStore,
    provider: OpenAIEmbeddingProvider,
    budget: EmbeddingRunBudget | None = None,
) -> Any:
    return process_job(
        make_job(),
        store=store,
        provider=provider,
        spec=SPEC,
        budget=budget or EmbeddingRunBudget(max_tokens=1_000_000),
        config=_config(),
    )


def _counting_ok(requests: list[httpx.Request]) -> Callable[[httpx.Request], httpx.Response]:
    def responder(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        n = len(json.loads(request.content)["input"])
        return _json_response(
            200, _ok_body(n, usage={"prompt_tokens": 11 * n, "total_tokens": 11 * n})
        )

    return responder


def test_successful_job_records_vendor_usage_once_per_request_without_double_counting() -> None:
    store = InMemoryJobStore(chunks=make_chunks(5))
    seen: list[httpx.Request] = []
    provider, _rec = _provider(_counting_ok(seen))
    budget = EmbeddingRunBudget(max_tokens=1_000_000)
    result = _run(store, provider, budget)
    assert result.outcome is JobOutcome.COMPLETED
    assert len(seen) == 3  # batches of 2, 2, 1
    assert [c.input_tokens for c in store.calls] == [22, 22, 11]
    assert result.tokens_used == 55 and budget.tokens_used == 55
    assert budget.requests_made == 3
    assert all(call.success for call in store.calls)
    assert [c.estimated_cost_usd for c in store.calls] == [
        pytest.approx(22 * 0.13 / 1e6),
        pytest.approx(22 * 0.13 / 1e6),
        pytest.approx(11 * 0.13 / 1e6),
    ]


def test_missing_usage_keeps_cost_unknown_and_budget_uses_the_estimate() -> None:
    body_without_usage = _ok_body(2)
    del body_without_usage["usage"]
    provider, _rec = _provider(lambda _r: _json_response(200, body_without_usage))
    store = InMemoryJobStore(chunks=make_chunks(2))
    budget = EmbeddingRunBudget(max_tokens=1_000_000)
    result = _run(store, provider, budget)
    assert result.outcome is JobOutcome.COMPLETED
    assert store.calls[0].input_tokens is None and store.calls[0].estimated_cost_usd is None
    assert budget.tokens_used > 0  # estimated, conservative; not zero


def test_transient_failure_requeues_once_and_counts_the_ambiguous_attempt_against_the_budget() -> (
    None
):
    provider, rec = _provider(_status(503))
    store = InMemoryJobStore(chunks=make_chunks(2))
    budget = EmbeddingRunBudget(max_tokens=1_000_000)
    result = _run(store, provider, budget)
    assert result.outcome is JobOutcome.REQUEUED
    assert rec.count == 1  # no retry loop inside the adapter on top of the job layer
    assert store.calls[0].success is False and store.calls[0].error_classification == "transient"
    assert budget.requests_made == 1 and budget.tokens_used > 0  # possibly billed: counted
    assert result.tokens_used == 0  # but not reported as confirmed usage


def test_deterministic_failure_is_not_counted_as_possibly_billed() -> None:
    provider, rec = _provider(_status(400, {"error": {"code": "context_length_exceeded"}}))
    store = InMemoryJobStore(chunks=make_chunks(2))
    budget = EmbeddingRunBudget(max_tokens=1_000_000)
    result = _run(store, provider, budget)
    assert result.outcome is JobOutcome.FAILED
    assert rec.count == 1 and budget.requests_made == 0


@pytest.mark.parametrize(
    "responder",
    [_status(401), _status(429, {"error": {"code": "insufficient_quota"}})],
    ids=["auth", "quota-429"],
)
def test_credential_and_quota_failures_stop_the_run_without_retrying(responder: Any) -> None:
    provider, rec = _provider(responder)
    store = InMemoryJobStore(chunks=make_chunks(2))
    result = _run(store, provider)
    assert result.outcome is JobOutcome.REQUEUED
    assert result.abort_run is True
    assert rec.count == 1
    assert store.requeues[0]["refund_attempt"] is True  # not the job's fault


def test_rate_limit_aborts_the_run_after_a_single_request() -> None:
    provider, rec = _provider(_status(429, {"error": {"code": "rate_limit_exceeded"}}))
    result = _run(InMemoryJobStore(chunks=make_chunks(4)), provider)
    assert result.abort_run is True and rec.count == 1


def test_bounded_attempts_across_layers_one_request_per_job_attempt() -> None:
    provider, rec = _provider(_status(503))
    store = InMemoryJobStore(chunks=make_chunks(2))
    for attempt in (1, 2, 3):
        process_job(
            make_job(attempt_count=attempt),
            store=store,
            provider=provider,
            spec=SPEC,
            budget=EmbeddingRunBudget(max_tokens=1_000_000),
            config=_config(),
        )
    assert rec.count == 3  # one HTTP request per job attempt: never multiplied
    assert store.failures and store.failures[-1]["classification"] == "transient"


# --- ineligible states: zero transmission -------------------------------------------

_SHA = "a" * 64
_OK = EligibilityFacts(
    document_found=True,
    is_archived=False,
    confidentiality_classification="standard",
    payload_checksum=_SHA,
    active_approval_checksum=_SHA,
    extraction_found=True,
    extraction_belongs_to_document=True,
    extraction_is_current=True,
    extraction_status="completed",
)


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"is_archived": True}, EligibilityReason.ARCHIVED),
        ({"extraction_is_current": False}, EligibilityReason.EXTRACTION_NOT_CURRENT),
        (
            {"confidentiality_classification": "restricted"},
            EligibilityReason.NOT_STANDARD_CLASSIFICATION,
        ),
        (
            {"confidentiality_classification": "confidential"},
            EligibilityReason.NOT_STANDARD_CLASSIFICATION,
        ),
        ({"active_approval_checksum": None}, EligibilityReason.NOT_APPROVED),
        ({"payload_checksum": "b" * 64}, EligibilityReason.CHECKSUM_MISMATCH),
        ({"payload_checksum": None}, EligibilityReason.CHECKSUM_MISMATCH),
        ({"extraction_status": "pending"}, EligibilityReason.EXTRACTION_NOT_COMPLETED),
        ({"extraction_status": "processing"}, EligibilityReason.EXTRACTION_NOT_COMPLETED),
        ({"extraction_status": "failed"}, EligibilityReason.EXTRACTION_NOT_COMPLETED),
        ({"extraction_status": "needs_ocr"}, EligibilityReason.EXTRACTION_NOT_COMPLETED),
        ({"extraction_belongs_to_document": False}, EligibilityReason.EXTRACTION_NOT_FOR_DOCUMENT),
        ({"extraction_found": False}, EligibilityReason.EXTRACTION_NOT_FOUND),
        ({"document_found": False}, EligibilityReason.DOCUMENT_NOT_FOUND),
    ],
    ids=lambda v: v.value if isinstance(v, EligibilityReason) else None,
)
def test_ineligible_documents_send_nothing_to_the_provider(
    changes: dict[str, Any], reason: EligibilityReason
) -> None:
    import dataclasses

    decision = evaluate_eligibility(dataclasses.replace(_OK, **changes))
    assert decision.reason is reason and not decision.eligible

    provider, rec = _provider(_ok_for(2))
    store = InMemoryJobStore(chunks=make_chunks(3), default_decision=decision)
    result = _run(store, provider)

    assert result.outcome is JobOutcome.BLOCKED_INELIGIBLE
    assert rec.count == 0  # zero requests: no text, vector request or key left the process
    assert store.calls == [] and store.embeddings == {}
    assert store.blocked_reason == reason.value


def test_approval_revoked_between_batches_stops_before_the_next_request() -> None:
    from app.retrieval.eligibility import EligibilityDecision

    provider, rec = _provider(_counting_ok([]))
    store = InMemoryJobStore(
        chunks=make_chunks(4),
        # Checks happen at job start and again before each provider call.
        eligibility_script=[
            EligibilityDecision(True, EligibilityReason.ELIGIBLE),
            EligibilityDecision(True, EligibilityReason.ELIGIBLE),
            EligibilityDecision(False, EligibilityReason.NOT_APPROVED),
        ],
    )
    result = _run(store, provider)
    assert result.outcome is JobOutcome.BLOCKED_INELIGIBLE
    assert rec.count == 1  # only the batch sent while still eligible
