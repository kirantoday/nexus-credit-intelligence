"""`EmbeddingProvider` Protocol (Milestone 10D.2, ADR-021).

Deliberately separate from `app.ai.providers.base.LLMProvider`, whose
reserved `create_embeddings` stub is left untouched: embeddings need
distinct document/query calls, a declared model identity and dimension, and
token usage, none of which that stub's signature can express.

No application code depends on a vendor SDK directly. No real vendor
adapter exists in 10D.2 — vendor and model selection is deferred to the
approved bake-off — so `fake.FakeEmbeddingProvider` is the only
implementation.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class EmbeddingResult:
    """One provider response. `input_tokens` is `None` when the vendor does
    not report usage — a caller must treat that as unknown, never zero."""

    vectors: list[list[float]]
    model_id: str
    model_version: str
    dimension: int
    input_tokens: int | None


class EmbeddingProvider(Protocol):
    @property
    def provider_name(self) -> str: ...

    @property
    def model_id(self) -> str: ...

    @property
    def model_version(self) -> str: ...

    @property
    def dimension(self) -> int: ...

    @property
    def max_batch_size(self) -> int: ...

    def embed_documents(self, texts: Sequence[str]) -> EmbeddingResult:
        """Embeds stored passages. One vector per input, in input order."""
        ...

    def embed_query(self, text: str) -> EmbeddingResult:
        """Embeds one search query (a single vector)."""
        ...
