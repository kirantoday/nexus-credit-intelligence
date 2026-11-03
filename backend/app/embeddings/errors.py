"""Structured embedding errors (Milestone 10D.2).

`classification` drives retry behavior exactly like
`DocumentExtractionErrorClass` does for extraction: `transient` failures
are retried up to a bounded attempt cap, `deterministic` ones never are.

**Messages must never contain document text or user queries.** Every
raise site passes a fixed, content-free description (a status code, a
count, a model id). `safe_summary` is the only thing persisted to a job
row or log line — never `str(exc)` of an exception that came from a
vendor SDK, which could echo request content.
"""

from __future__ import annotations

from typing import ClassVar


class EmbeddingError(Exception):
    classification: ClassVar[str] = "deterministic"

    # Evidence about the vendor request that preceded this error, set by a
    # provider adapter after it actually issued an HTTP request. The defaults
    # mean "no request was made" (for example local input validation), which
    # is how pre-request failures stay distinguishable from attempted ones.
    # They are facts about *exposure*, never proof of billing or of no billing:
    # `possibly_billed` is a conservative local judgement, and
    # `reported_input_tokens` is the vendor's own aggregate prompt-token count
    # when a response carried a valid one, even if the response was rejected.
    request_attempted: bool = False
    possibly_billed: bool = False
    reported_input_tokens: int | None = None


class EmbeddingTransientError(EmbeddingError):
    """Network failure, timeout, or vendor 5xx — worth retrying."""

    classification: ClassVar[str] = "transient"


class EmbeddingRateLimitError(EmbeddingTransientError):
    def __init__(self, message: str, *, retry_after_seconds: float | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class EmbeddingPersistenceError(EmbeddingTransientError):
    """Writing already-validated vectors failed (connection loss, lock
    timeout, serialization failure, ...). Retried like any transient error
    but only up to the bounded attempt cap, so a persistent database
    problem (for example a constraint violation) still ends in `failed`
    rather than looping. Carries no driver message, which can echo the
    statement's parameters — document text and vectors included."""


class EmbeddingInputError(EmbeddingError):
    """The vendor rejected the input itself (too long, empty, malformed).
    Re-sending the same input will fail the same way."""


class EmbeddingAuthError(EmbeddingError):
    """Missing/invalid credentials or insufficient quota. Not the job's
    fault and not retryable by the job — the whole run must stop."""


class EmbeddingConfigurationError(EmbeddingError):
    """The embedding feature is disabled or misconfigured (including a
    model/dimension contract violation detected before any call)."""


class EmbeddingDimensionMismatchError(EmbeddingError):
    """A provider returned vectors whose width, count, or model identity
    does not match the configured model contract. Persisting them would
    corrupt retrieval, so the batch is rejected."""


class EmbeddingOwnershipLostError(EmbeddingError):
    """The exclusive worker lock cannot be shown to be held. Raised before a
    provider request is made, so no request was sent and nothing is billed;
    the processor requeues the job (attempt refunded) and ends the run."""


class EmbeddingResponseError(EmbeddingError):
    """The vendor answered, but the response is not usable: not JSON, wrong
    shape, an invalid or duplicated index, non-numeric or non-finite values,
    an unexpected model name, or vectors that are not unit length. Re-sending
    would not repair a contract violation, so this is deterministic and
    carries no response content."""


def safe_summary(exc: BaseException) -> str:
    """Content-free description of `exc`: its type name, plus the
    classification for Nexus's own embedding errors. Never `str(exc)`."""
    if isinstance(exc, EmbeddingError):
        return f"{type(exc).__name__} ({exc.classification})"
    return f"{type(exc).__name__} (deterministic)"


def classify(exc: BaseException) -> str:
    """`transient` or `deterministic`. An exception of unrecognized shape
    is deterministic — the 2026-08-13 incident's governing lesson, same as
    `document_extraction_service._classify_error`: never blindly retry
    something unrecognized."""
    if isinstance(exc, EmbeddingError):
        return exc.classification
    return "deterministic"
