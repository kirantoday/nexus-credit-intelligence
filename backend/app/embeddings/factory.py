"""Builds the configured `EmbeddingProvider` and its `EmbeddingModelSpec`
(Milestone 10D.2).

Mirrors `app.ai.factory.get_llm_provider`: validates only what the
selected provider needs, never silently substitutes another provider, and
never logs a key. Two providers are buildable: `fake`, only in
`local`/`test` environments (a fake's vectors are meaningless, so letting
one run against a deployed database would silently poison retrieval), and
`openai` (`text-embedding-3-large`, approved for local development only).
Selecting `openai` additionally requires a dedicated `EMBEDDING_API_KEY`
(never the LLM's `OPENAI_API_KEY`) and an explicit owner policy
acknowledgement; without both, construction fails closed before any client
or network object exists. Any other provider name is refused.

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
from app.embeddings.openai_provider import (
    OPENAI_MODEL_ID,
    OPENAI_PROVIDER_NAME,
    OpenAIEmbeddingProvider,
)

_FAKE_ALLOWED_ENVIRONMENTS = frozenset({"local", "test"})

# The value `EMBEDDING_EXTERNAL_POLICY_APPROVAL` must equal before a real
# vendor can be built. It is a configuration-level acknowledgement that the
# owner approved this provider/model/data-handling policy; it is NOT an audit
# record (see docs/proposed/10D2-openai-adapter-implementation-report-*.md).
OPENAI_POLICY_APPROVAL_VALUE = f"{OPENAI_PROVIDER_NAME}:{OPENAI_MODEL_ID}"


class EmbeddingSettings(Protocol):
    environment: str
    embeddings_enabled: bool
    embedding_provider: str | None
    embedding_model_id: str | None
    embedding_model_version: str | None
    embedding_dimension: int | None
    embedding_batch_size: int
    # Read only when `embedding_provider == "openai"`.
    embedding_api_key: object
    embedding_request_timeout_seconds: float
    embedding_external_policy_approval: str | None


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

    if provider_name == OPENAI_PROVIDER_NAME:
        return _build_openai(settings, dimension)

    raise EmbeddingConfigurationError(
        f"EMBEDDING_PROVIDER={provider_name!r} is not an approved embedding provider"
    )


def _secret_value(secret: object) -> str | None:
    """Accepts a plain string or a pydantic `SecretStr`-like object."""
    getter = getattr(secret, "get_secret_value", None)
    value = getter() if callable(getter) else secret
    return value if isinstance(value, str) and value.strip() else None


def _build_openai(
    settings: EmbeddingSettings, dimension: int
) -> tuple[EmbeddingProvider, EmbeddingModelSpec]:
    if settings.embedding_model_id not in (None, "", OPENAI_MODEL_ID):
        raise EmbeddingConfigurationError(
            f"only {OPENAI_MODEL_ID!r} is approved for the openai embedding provider"
        )
    model_version = (settings.embedding_model_version or "").strip()
    if not model_version:
        raise EmbeddingConfigurationError(
            "EMBEDDING_MODEL_VERSION is required for the openai embedding provider"
        )
    if settings.embedding_external_policy_approval != OPENAI_POLICY_APPROVAL_VALUE:
        raise EmbeddingConfigurationError(
            "the owner's external-processing policy for "
            f"{OPENAI_POLICY_APPROVAL_VALUE!r} is not recorded "
            "(EMBEDDING_EXTERNAL_POLICY_APPROVAL); live use stays blocked"
        )
    # A dedicated key only: never fall back to the LLM credential.
    api_key = _secret_value(settings.embedding_api_key)
    if api_key is None:
        raise EmbeddingConfigurationError("EMBEDDING_API_KEY is not set")

    provider = OpenAIEmbeddingProvider(
        api_key=api_key,
        model_version=model_version,
        dimension=dimension,
        max_batch_size=settings.embedding_batch_size,
        timeout_seconds=settings.embedding_request_timeout_seconds,
    )
    spec = EmbeddingModelSpec(
        provider=OPENAI_PROVIDER_NAME,
        model_id=OPENAI_MODEL_ID,
        model_version=model_version,
        dimension=dimension,
    )
    return provider, spec
