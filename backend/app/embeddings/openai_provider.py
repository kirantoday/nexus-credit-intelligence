"""OpenAI `EmbeddingProvider` (Milestone 10D.2, ADR-021).

Approved for LOCAL DEVELOPMENT only: the engineering contract is
`text-embedding-3-large` at 1024 dimensions requested with `dimensions=1024`.
Building this class does not authorize external processing, a key, paid
usage or production use; the factory refuses to construct it unless the
embeddings feature is enabled, a dedicated key is configured and the owner's
policy acknowledgement matches (see `app.embeddings.factory`).

Primary sources (read 2026-11-02, public official documentation):

- Create embeddings (request/response, limits):
  https://developers.openai.com/api/reference/resources/embeddings/methods/create
- Embeddings guide (dimensions, normalization, pricing basis):
  https://developers.openai.com/api/docs/guides/embeddings
- Model page (price, endpoints, default snapshot only):
  https://developers.openai.com/api/docs/models/text-embedding-3-large
- Error codes (429 variants, 5xx, Retry-After):
  https://developers.openai.com/api/docs/guides/error-codes

Documented facts this module relies on (re-verify at live-validation time):
`POST /v1/embeddings` with `model`, `input` (a string or an array of up to
2,048 strings, none empty), `dimensions`, `encoding_format` (`float` default,
set explicitly here); 8,192 tokens per input and 300,000 tokens summed per
request; a response of `{object, data: [{object, index, embedding}], model,
usage: {prompt_tokens, total_tokens}}`; guide says OpenAI embeddings are
normalized to length 1 and that the `dimensions` parameter is the suggested
way to shorten (manual shortening needs re-normalization, which this module
never does).

Design decisions:

- **One HTTP attempt per call.** Retry already exists a layer up (job
  attempts with a cap, and the worker stops the run on rate limiting). A
  retry loop here would multiply calls, so this adapter never retries; it
  classifies the failure and, for a 429 rate limit, surfaces `Retry-After`.
  A timeout or connection failure after the request was sent is ambiguous
  and may have been billed; this module cannot know, and no exactly-once or
  spending-ceiling guarantee is made.
- **Fixed endpoint, no redirects.** The URL is a module constant; there is no
  endpoint setting, and a redirect is treated as a configuration error
  instead of being followed (the key is never sent to another host).
- **Fail closed on the response.** Model name, item count, every `index`,
  vector width, numeric validity and unit length are all checked; nothing is
  repaired, re-ordered by guesswork, truncated, sliced or normalized.
- **No tokenizer is installed**, so input size is checked with a deliberately
  conservative *UTF-8 byte* policy (see `MAX_INPUT_BYTES`). Bytes, not
  characters, because non-ASCII text can need several tokens per character.
  If the model's tokenizer is byte-level (it never emits a token for less than
  one byte; the documentation read does not state the tokenizer, so this is an
  **assumption**), a text of N bytes is at most N tokens, so the caps are an
  upper bound on tokens under that assumption. It is still a heuristic, not a
  compliance guarantee; a vendor rejection is a terminal `EmbeddingInputError`.
  Inputs are never truncated.
- **Request exposure evidence.** Every error raised after an HTTP request was
  actually issued carries `request_attempted=True`, a conservative
  `possibly_billed` judgement and, when a rejected 200 response still carried
  a valid aggregate `prompt_tokens`, that count (`reported_input_tokens`).
  Failures before any request (local validation, construction) carry the
  defaults, so they are never accounted as attempts. Failures in the connect
  phase (`ConnectError`, `ConnectTimeout`, `PoolTimeout`) are marked not
  possibly billed, because no request was delivered; this is an inference from
  where the failure occurred, not proof. Everything else after sending
  (read/write timeouts, dropped connections, every HTTP status including
  4xx, and every rejected 200 response) is treated as possibly billed:
  nothing here claims a request was free or exactly-once.
- **Usage** is the aggregate `usage.prompt_tokens` only (never added to
  `total_tokens`, which would double count). Missing or malformed usage is
  `None`, meaning unknown — never zero. Per-input usage is not inferred.
- **No secrets or content in messages.** Errors carry an HTTP status or a
  category, never a response body, header, key, input text or vector.
- **The `httpx` client is created lazily** on the first request (importing or
  constructing the provider does no network work) and is closed by
  `close()` only when this object created it; an injected client is the
  caller's to close.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from types import TracebackType
from typing import Any

import httpx

from app.embeddings.base import EmbeddingResult
from app.embeddings.dimensions import EMBEDDING_COLUMN_DIMENSION
from app.embeddings.errors import (
    EmbeddingAuthError,
    EmbeddingConfigurationError,
    EmbeddingDimensionMismatchError,
    EmbeddingError,
    EmbeddingInputError,
    EmbeddingRateLimitError,
    EmbeddingResponseError,
    EmbeddingTransientError,
)

OPENAI_PROVIDER_NAME = "openai"
OPENAI_MODEL_ID = "text-embedding-3-large"
OPENAI_EMBEDDINGS_URL = "https://api.openai.com/v1/embeddings"

# Documented limits (create-embeddings reference, 2026-11-02). Not account
# rate limits; those vary by tier and are never assumed here.
MAX_INPUTS_PER_REQUEST = 2048
MAX_INPUT_TOKENS = 8192
MAX_TOTAL_TOKENS_PER_REQUEST = 300_000

# Conservative local size policy (no tokenizer available), in UTF-8 BYTES.
# Under the unverified assumption that tokens are at least one byte each, N
# bytes is at most N tokens, so 8,000 bytes stays under the 8,192-token input
# limit and 300,000 bytes stays under the 300,000-token request limit. For
# ASCII text this equals the character count. Nexus chunks are capped at 4,000
# characters plus a short header (about 4.3 KB, a little more with typographic
# characters that take 3 bytes), so ordinary chunks fit with margin and the
# processor splits a batch before it would exceed the aggregate cap. Heavily
# non-ASCII text (for example CJK, 3 bytes per character) is rejected earlier
# than a character count would: deliberately. A heuristic, not a guarantee.
MAX_INPUT_BYTES = 8_000
MAX_TOTAL_INPUT_BYTES = MAX_TOTAL_TOKENS_PER_REQUEST

DEFAULT_TIMEOUT_SECONDS = 30.0
MAX_TIMEOUT_SECONDS = 300.0

# The guide documents unit-length vectors. This tolerance only absorbs float
# rounding; a vector outside it is rejected, never rescaled.
UNIT_NORM_TOLERANCE = 0.01

_MAX_RETRY_AFTER_SECONDS = 3600.0
_QUOTA_ERROR_CODES = frozenset(
    {
        "insufficient_quota",
        "credit_balance_exhausted",
        "organization_spend_limit_exceeded",
        "project_spend_limit_exceeded",
        "organization_usage_limit_exceeded",
    }
)


class OpenAIEmbeddingProvider:
    def __init__(
        self,
        *,
        api_key: str,
        model_version: str,
        dimension: int = EMBEDDING_COLUMN_DIMENSION,
        max_batch_size: int = 64,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        client: httpx.Client | None = None,
    ) -> None:
        key = api_key.strip() if isinstance(api_key, str) else ""
        if not key or not key.isprintable() or any(ch.isspace() for ch in key):
            raise EmbeddingConfigurationError("the embedding API key is missing or malformed")
        if not model_version or not model_version.strip():
            raise EmbeddingConfigurationError("EMBEDDING_MODEL_VERSION is required")
        if dimension != EMBEDDING_COLUMN_DIMENSION:
            raise EmbeddingConfigurationError(
                f"dimension {dimension} does not match the embedding column width "
                f"{EMBEDDING_COLUMN_DIMENSION}"
            )
        if not 1 <= max_batch_size <= MAX_INPUTS_PER_REQUEST:
            raise EmbeddingConfigurationError(
                f"max_batch_size must be between 1 and {MAX_INPUTS_PER_REQUEST}"
            )
        if not (
            isinstance(timeout_seconds, int | float) and 0 < timeout_seconds <= MAX_TIMEOUT_SECONDS
        ):
            raise EmbeddingConfigurationError(
                f"timeout_seconds must be finite, positive and at most {MAX_TIMEOUT_SECONDS}"
            )
        self._api_key = key
        self._model_version = model_version.strip()
        self._dimension = dimension
        self._max_batch_size = max_batch_size
        self._timeout_seconds = float(timeout_seconds)
        self._client = client
        self._owns_client = client is None

    # --- EmbeddingProvider protocol -------------------------------------------------

    @property
    def provider_name(self) -> str:
        return OPENAI_PROVIDER_NAME

    @property
    def model_id(self) -> str:
        return OPENAI_MODEL_ID

    @property
    def model_version(self) -> str:
        return self._model_version

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def max_batch_size(self) -> int:
        return self._max_batch_size

    @property
    def max_batch_input_size(self) -> int:
        """Aggregate input-size cap per request, in `input_size` units; the
        processor splits batches so that no batch exceeds it."""
        return MAX_TOTAL_INPUT_BYTES

    def input_size(self, text: str) -> int:
        """The size this adapter's local policy assigns to one input (UTF-8
        bytes). Text that cannot be encoded counts as oversized so that the
        request is rejected locally."""
        try:
            return len(text.encode("utf-8"))
        except UnicodeEncodeError:
            return MAX_INPUT_BYTES + 1

    def embed_documents(self, texts: Sequence[str]) -> EmbeddingResult:
        return self._embed(list(texts))

    def embed_query(self, text: str) -> EmbeddingResult:
        # OpenAI documents no document/query task mode, so both go through the
        # same call. The local fingerprint still separates the input types.
        return self._embed([text])

    # --- lifecycle -----------------------------------------------------------------

    def close(self) -> None:
        if self._owns_client and self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> OpenAIEmbeddingProvider:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def __repr__(self) -> str:
        return (
            f"OpenAIEmbeddingProvider(model={OPENAI_MODEL_ID!r}, "
            f"model_version={self._model_version!r}, dimension={self._dimension}, "
            "api_key=<redacted>)"
        )

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                timeout=httpx.Timeout(self._timeout_seconds), follow_redirects=False
            )
        return self._client

    # --- request -------------------------------------------------------------------

    def _embed(self, texts: list[str]) -> EmbeddingResult:
        self._validate_inputs(texts)
        payload: dict[str, Any] = {
            "model": OPENAI_MODEL_ID,
            "input": texts,
            "dimensions": self._dimension,
            "encoding_format": "float",
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}
        try:
            response = self._get_client().post(
                OPENAI_EMBEDDINGS_URL,
                json=payload,
                headers=headers,
                timeout=self._timeout_seconds,
                follow_redirects=False,
            )
        except httpx.TimeoutException as exc:
            # Connect/pool timeouts happen before a request is delivered.
            # Read and write timeouts happen after bytes may have been sent.
            delivered = not isinstance(exc, httpx.ConnectTimeout | httpx.PoolTimeout)
            raise _mark(
                EmbeddingTransientError("the OpenAI request timed out"), billed=delivered
            ) from None
        except httpx.HTTPError as exc:
            delivered = not isinstance(exc, httpx.ConnectError)
            raise _mark(
                EmbeddingTransientError("the OpenAI request failed (network)"), billed=delivered
            ) from None

        if response.status_code != 200:
            # No evidence that an error response is unbilled: stay conservative.
            raise _mark(self._error_for_status(response), billed=True)
        try:
            return self._parse_success(response, expected=len(texts))
        except EmbeddingError as exc:
            # A 200 that fails local validation may still have been billed,
            # and may carry a valid usage count that must not be lost.
            raise _mark(exc, billed=True, tokens=_usage_tokens_from(response)) from None

    def _validate_inputs(self, texts: list[str]) -> None:
        if not texts:
            raise EmbeddingInputError("no inputs to embed")
        if len(texts) > self._max_batch_size:
            raise EmbeddingInputError(
                f"batch of {len(texts)} exceeds the configured maximum {self._max_batch_size}"
            )
        total = 0
        for text in texts:
            if not isinstance(text, str) or not text.strip():
                raise EmbeddingInputError("an input is empty or not text")
            size = self.input_size(text)
            if size > MAX_INPUT_BYTES:
                raise EmbeddingInputError("an input exceeds the local maximum input size")
            total += size
        if total > MAX_TOTAL_INPUT_BYTES:
            raise EmbeddingInputError("the batch exceeds the local maximum total input size")

    # --- errors --------------------------------------------------------------------

    def _error_for_status(
        self, response: httpx.Response
    ) -> (
        EmbeddingAuthError
        | EmbeddingConfigurationError
        | EmbeddingInputError
        | EmbeddingRateLimitError
        | EmbeddingTransientError
    ):
        status = response.status_code
        if 300 <= status < 400:
            return EmbeddingConfigurationError(
                f"unexpected redirect (HTTP {status}); redirects are not followed"
            )
        if status in (401, 403):
            return EmbeddingAuthError(f"OpenAI rejected the credentials (HTTP {status})")
        if status == 404:
            return EmbeddingConfigurationError("OpenAI endpoint or model not found (HTTP 404)")
        if status == 429:
            code, error_type = _error_code_and_type(response)
            if code in _QUOTA_ERROR_CODES or error_type == "insufficient_quota":
                # Billing, spend or quota limits are not fixed by waiting, so
                # this must not be retried as an ordinary rate limit.
                return EmbeddingAuthError("OpenAI quota or spend limit reached (HTTP 429)")
            return EmbeddingRateLimitError(
                "OpenAI rate limit reached (HTTP 429)",
                retry_after_seconds=_retry_after_seconds(response),
            )
        if status == 408 or status >= 500:
            return EmbeddingTransientError(f"OpenAI server or timeout error (HTTP {status})")
        return EmbeddingInputError(f"OpenAI rejected the request (HTTP {status})")

    # --- response ------------------------------------------------------------------

    def _parse_success(self, response: httpx.Response, *, expected: int) -> EmbeddingResult:
        try:
            body: Any = response.json()
        except ValueError:
            raise EmbeddingResponseError("the response is not valid JSON") from None
        if not isinstance(body, dict):
            raise EmbeddingResponseError("the response is not a JSON object")
        if body.get("model") != OPENAI_MODEL_ID:
            raise EmbeddingDimensionMismatchError(
                "the response names a different model than the approved model"
            )
        data = body.get("data")
        if not isinstance(data, list):
            raise EmbeddingResponseError("the response has no data list")
        if len(data) != expected:
            raise EmbeddingDimensionMismatchError(
                f"the response has {len(data)} embeddings for {expected} inputs"
            )

        ordered: list[list[float] | None] = [None] * expected
        for item in data:
            if not isinstance(item, dict):
                raise EmbeddingResponseError("an embedding item is not an object")
            index = item.get("index")
            if not isinstance(index, int) or isinstance(index, bool):
                raise EmbeddingResponseError("an embedding item has no integer index")
            if not 0 <= index < expected:
                raise EmbeddingResponseError("an embedding index is out of range")
            if ordered[index] is not None:
                raise EmbeddingResponseError("an embedding index is duplicated")
            ordered[index] = self._validated_vector(item.get("embedding"))

        vectors: list[list[float]] = []
        for vector in ordered:
            if vector is None:  # unreachable once count, range and duplicates pass
                raise EmbeddingResponseError("an embedding index is missing")
            vectors.append(vector)

        return EmbeddingResult(
            vectors=vectors,
            model_id=OPENAI_MODEL_ID,
            model_version=self._model_version,
            dimension=self._dimension,
            input_tokens=_aggregate_prompt_tokens(body.get("usage")),
        )

    def _validated_vector(self, raw: Any) -> list[float]:
        if not isinstance(raw, list):
            raise EmbeddingResponseError("an embedding is not a list of numbers")
        if len(raw) != self._dimension:
            raise EmbeddingDimensionMismatchError(
                f"an embedding has width {len(raw)}, expected {self._dimension}"
            )
        vector: list[float] = []
        for value in raw:
            if isinstance(value, bool) or not isinstance(value, int | float):
                raise EmbeddingResponseError("an embedding contains a non-numeric value")
            number = float(value)
            if not math.isfinite(number):
                raise EmbeddingResponseError("an embedding contains a non-finite value")
            vector.append(number)
        norm = math.sqrt(sum(v * v for v in vector))
        if abs(norm - 1.0) > UNIT_NORM_TOLERANCE:
            raise EmbeddingResponseError("an embedding is not unit length")
        return vector


def _error_code_and_type(response: httpx.Response) -> tuple[str | None, str | None]:
    """Only the vendor's short `error.code` / `error.type` strings are read;
    the human-readable message (which can echo request content) never is."""
    try:
        body: Any = response.json()
    except ValueError:
        return None, None
    error = body.get("error") if isinstance(body, dict) else None
    if not isinstance(error, dict):
        return None, None
    code = error.get("code")
    error_type = error.get("type")
    return (
        code if isinstance(code, str) else None,
        error_type if isinstance(error_type, str) else None,
    )


def _retry_after_seconds(response: httpx.Response) -> float | None:
    raw = response.headers.get("retry-after")
    if raw is None:
        return None
    try:
        seconds = float(raw)
    except ValueError:
        return None  # an HTTP-date form is deliberately not parsed
    if not math.isfinite(seconds) or seconds < 0:
        return None
    return min(seconds, _MAX_RETRY_AFTER_SECONDS)


def _is_count(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _aggregate_prompt_tokens(usage: Any) -> int | None:
    """`usage.prompt_tokens` for the whole request, or `None` (unknown) when
    absent, malformed, or inconsistent with `total_tokens`. The two fields are
    never summed."""
    if not isinstance(usage, dict):
        return None
    prompt = usage.get("prompt_tokens")
    if not isinstance(prompt, int) or isinstance(prompt, bool) or prompt < 0:
        return None
    total = usage.get("total_tokens")
    if total is not None and (not _is_count(total) or total != prompt):
        return None
    return prompt


def _mark(exc: EmbeddingError, *, billed: bool, tokens: int | None = None) -> EmbeddingError:
    """Attach request-exposure evidence (see `EmbeddingError`)."""
    exc.request_attempted = True
    exc.possibly_billed = billed
    exc.reported_input_tokens = tokens
    return exc


def _usage_tokens_from(response: httpx.Response) -> int | None:
    """Valid aggregate `prompt_tokens` from a response that was otherwise
    rejected, or `None` (unknown) when absent, malformed or unparsable."""
    try:
        body: Any = response.json()
    except ValueError:
        return None
    if not isinstance(body, dict):
        return None
    return _aggregate_prompt_tokens(body.get("usage"))
