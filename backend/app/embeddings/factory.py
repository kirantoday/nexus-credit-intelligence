"""Builds the configured `EmbeddingProvider` and its `EmbeddingModelSpec`
(Milestone 10D.2).

Mirrors `app.ai.factory.get_llm_provider`: validates only what the
selected provider needs, never silently substitutes another provider, and
never logs a key. In 10D.2 the only buildable provider is `fake`, and only
in `local`/`test` environments — a fake's vectors are meaningless, so
letting one run against a deployed database would silently poison
retrieval. Real vendors are added by a later, separately approved step.

`settings` is duck-typed (any object with the `Settings` attributes read
below) so this module imports nothing outside the standard library and its
siblings.
"""

from __future__ import annotations

from typing import Protocol

from app.embeddings.base import EmbeddingProvider
from app.embeddings.dimensions import EMBEDDING_COLUMN_DIMENSION, EmbeddingModelSpec
from app.embeddings.errors import EmbeddingConfigurationError
from app.embeddings.fake import (
    FAKE_MODEL_ID,
    FAKE_MODEL_VERSION,
    FAKE_PROVIDER_NAME,
    FakeEmbeddingProvider,
)

_FAKE_ALLOWED_ENVIRONMENTS = frozenset({"local", "test"})


class EmbeddingSettings(Protocol):
    environment: str
    embeddings_enabled: bool
    embedding_provider: str | None
    embedding_model_id: str | None
    embedding_model_version: str | None
    embedding_dimension: int | None
    embedding_batch_size: int


def get_embedding_provider(
    settings: EmbeddingSettings,
) -> tuple[EmbeddingProvider, EmbeddingModelSpec]:
    if not settings.embeddings_enabled:
        raise EmbeddingConfigurationError("EMBEDDINGS_ENABLED is false; embedding is disabled")

    provider_name = settings.embedding_provider
    if not provider_name:
        raise EmbeddingConfigurationError("EMBEDDING_PROVIDER is not set")

    dimension = settings.embedding_dimension
    if dimension is None:
        raise EmbeddingConfigurationError("EMBEDDING_DIMENSION is not set")
    if dimension != EMBEDDING_COLUMN_DIMENSION:
        raise EmbeddingConfigurationError(
            f"EMBEDDING_DIMENSION={dimension} does not match the embedding column width "
            f"{EMBEDDING_COLUMN_DIMENSION}"
        )

    if provider_name == FAKE_PROVIDER_NAME:
        if settings.environment not in _FAKE_ALLOWED_ENVIRONMENTS:
            raise EmbeddingConfigurationError(
                "the fake embedding provider is only permitted when ENVIRONMENT is local or test"
            )
        model_id = settings.embedding_model_id or FAKE_MODEL_ID
        model_version = settings.embedding_model_version or FAKE_MODEL_VERSION
        provider = FakeEmbeddingProvider(
            dimension=dimension,
            model_id=model_id,
            model_version=model_version,
            max_batch_size=settings.embedding_batch_size,
        )
        spec = EmbeddingModelSpec(
            provider=FAKE_PROVIDER_NAME,
            model_id=model_id,
            model_version=model_version,
            dimension=dimension,
        )
        return provider, spec

    raise EmbeddingConfigurationError(
        f"EMBEDDING_PROVIDER={provider_name!r} is not implemented; no real embedding vendor has "
        "been approved yet"
    )
