"""Unit tests for `app.embeddings.factory` (Milestone 10D.2): disabled by
default, strict model/dimension contract, fake only in local/test, and no
real vendor available."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.embeddings.dimensions import EMBEDDING_COLUMN_DIMENSION
from app.embeddings.errors import EmbeddingConfigurationError
from app.embeddings.factory import get_embedding_provider


def _settings(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "environment": "local",
        "embeddings_enabled": True,
        "embedding_provider": "fake",
        "embedding_model_id": None,
        "embedding_model_version": None,
        "embedding_dimension": EMBEDDING_COLUMN_DIMENSION,
        "embedding_batch_size": 8,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_disabled_feature_flag_refuses_to_build_a_provider() -> None:
    with pytest.raises(EmbeddingConfigurationError, match="disabled"):
        get_embedding_provider(_settings(embeddings_enabled=False))


def test_missing_provider_or_dimension_is_a_configuration_error() -> None:
    with pytest.raises(EmbeddingConfigurationError):
        get_embedding_provider(_settings(embedding_provider=None))
    with pytest.raises(EmbeddingConfigurationError):
        get_embedding_provider(_settings(embedding_dimension=None))


def test_dimension_that_differs_from_the_column_width_is_refused() -> None:
    with pytest.raises(EmbeddingConfigurationError, match="column width"):
        get_embedding_provider(_settings(embedding_dimension=768))


def test_fake_provider_builds_in_local_and_test_with_a_consistent_spec() -> None:
    for environment in ("local", "test"):
        provider, spec = get_embedding_provider(_settings(environment=environment))
        assert provider.dimension == spec.dimension == EMBEDDING_COLUMN_DIMENSION
        assert (provider.provider_name, provider.model_id, provider.model_version) == (
            spec.provider,
            spec.model_id,
            spec.model_version,
        )
        assert provider.max_batch_size == 8


def test_fake_provider_is_refused_in_deployed_environments() -> None:
    for environment in ("staging", "production"):
        with pytest.raises(EmbeddingConfigurationError, match="local or test"):
            get_embedding_provider(_settings(environment=environment))


def test_unapproved_vendors_are_refused() -> None:
    # Superseded wording: before the OpenAI adapter, every real vendor was
    # "not implemented". Now only `fake` and `openai` are buildable; any other
    # name (including Voyage, which is a researched alternative only) fails
    # closed. `openai` is covered, with its prerequisites, in
    # test_openai_embedding_adapter.py.
    for name in ("voyage", "anthropic", "cohere", "OpenAI "):
        with pytest.raises(EmbeddingConfigurationError, match="not an approved"):
            get_embedding_provider(_settings(embedding_provider=name))
