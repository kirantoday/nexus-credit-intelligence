"""Unit tests for the deterministic fake provider and the model/dimension
contract (`app.embeddings.fake`, `.dimensions`, `.errors`, Milestone
10D.2). No network, no database, no vendor."""

from __future__ import annotations

import math

import pytest

from app.embeddings.base import EmbeddingResult
from app.embeddings.dimensions import (
    EMBEDDING_COLUMN_DIMENSION,
    EmbeddingModelSpec,
    validate_result,
)
from app.embeddings.errors import (
    EmbeddingAuthError,
    EmbeddingConfigurationError,
    EmbeddingDimensionMismatchError,
    EmbeddingInputError,
    EmbeddingRateLimitError,
    EmbeddingTransientError,
    classify,
    safe_summary,
)
from app.embeddings.fake import FakeEmbeddingProvider

SPEC = EmbeddingModelSpec(
    provider="fake", model_id="fake-embedding", model_version="fake-1", dimension=1024
)


def test_fake_is_deterministic_unit_length_and_correct_width() -> None:
    provider = FakeEmbeddingProvider()
    first = provider.embed_documents(["alpha", "beta"])
    second = FakeEmbeddingProvider().embed_documents(["alpha", "beta"])
    assert first.vectors == second.vectors
    assert len(first.vectors) == 2
    assert all(len(v) == EMBEDDING_COLUMN_DIMENSION for v in first.vectors)
    assert math.isclose(math.sqrt(sum(x * x for x in first.vectors[0])), 1.0, rel_tol=1e-9)
    assert first.vectors[0] != first.vectors[1]


def test_query_embedding_differs_from_document_embedding_of_same_text() -> None:
    provider = FakeEmbeddingProvider()
    doc = provider.embed_documents(["Can Big Lots take on more debt?"]).vectors[0]
    query = provider.embed_query("Can Big Lots take on more debt?").vectors[0]
    assert doc != query


def test_fake_reports_usage_or_none_and_counts_calls() -> None:
    provider = FakeEmbeddingProvider()
    result = provider.embed_documents(["abcd" * 4])
    assert result.input_tokens == 4
    assert provider.call_count == 1
    assert provider.texts_sent == 1
    assert FakeEmbeddingProvider(report_usage=False).embed_documents(["x"]).input_tokens is None


def test_fake_failure_injection_is_one_shot_per_registration() -> None:
    provider = FakeEmbeddingProvider()
    provider.fail_next(EmbeddingTransientError("boom"), times=2)
    for _ in range(2):
        with pytest.raises(EmbeddingTransientError):
            provider.embed_documents(["x"])
    assert provider.embed_documents(["x"]).vectors  # third call succeeds
    assert provider.call_count == 3


def test_fake_enforces_batch_and_input_limits() -> None:
    provider = FakeEmbeddingProvider(max_batch_size=2, max_input_chars=10)
    with pytest.raises(EmbeddingInputError):
        provider.embed_documents(["a", "b", "c"])
    with pytest.raises(EmbeddingInputError):
        provider.embed_documents(["x" * 11])


def test_error_classification_and_safe_summary_never_expose_message() -> None:
    assert classify(EmbeddingTransientError("m")) == "transient"
    assert classify(EmbeddingRateLimitError("m", retry_after_seconds=3)) == "transient"
    assert classify(EmbeddingInputError("m")) == "deterministic"
    assert classify(EmbeddingAuthError("m")) == "deterministic"
    assert classify(ValueError("anything")) == "deterministic"
    secret = ValueError("SECRET DOCUMENT TEXT")
    assert "SECRET" not in safe_summary(secret)
    assert safe_summary(secret) == "ValueError (deterministic)"
    assert safe_summary(EmbeddingTransientError("SECRET")) == "EmbeddingTransientError (transient)"


def test_spec_rejects_dimension_that_does_not_match_the_column_width() -> None:
    with pytest.raises(EmbeddingConfigurationError):
        EmbeddingModelSpec(provider="p", model_id="m", model_version="1", dimension=768)
    with pytest.raises(EmbeddingConfigurationError):
        EmbeddingModelSpec(provider="p", model_id="", model_version="1", dimension=1024)
    with pytest.raises(EmbeddingConfigurationError):
        EmbeddingModelSpec(provider="p", model_id="m", model_version="1", dimension=0)


def test_validate_result_accepts_a_matching_response() -> None:
    result = FakeEmbeddingProvider().embed_documents(["a", "b"])
    validate_result(result, spec=SPEC, expected_vectors=2)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda r: EmbeddingResult(r.vectors, r.model_id, r.model_version, 512, r.input_tokens),
        lambda r: EmbeddingResult(r.vectors, "other-model", r.model_version, 1024, r.input_tokens),
        lambda r: EmbeddingResult(r.vectors, r.model_id, "fake-2", 1024, r.input_tokens),
        lambda r: EmbeddingResult(r.vectors[:-1], r.model_id, r.model_version, 1024, 1),
        lambda r: EmbeddingResult(
            [v[:-1] for v in r.vectors], r.model_id, r.model_version, 1024, 1
        ),
        lambda r: EmbeddingResult(
            [[float("nan")] + v[1:] for v in r.vectors], r.model_id, r.model_version, 1024, 1
        ),
        lambda r: EmbeddingResult(
            [[float("inf")] + v[1:] for v in r.vectors], r.model_id, r.model_version, 1024, 1
        ),
    ],
)
def test_validate_result_rejects_any_incompatible_response(mutate: object) -> None:
    good = FakeEmbeddingProvider().embed_documents(["a", "b"])
    bad = mutate(good)  # type: ignore[operator]
    with pytest.raises(EmbeddingDimensionMismatchError):
        validate_result(bad, spec=SPEC, expected_vectors=2)
