"""The model-to-dimension contract (Milestone 10D.2, ADR-021).

`document_chunk_embedding.embedding` is a fixed-width pgvector column.
Changing its width is **not** a runtime setting: it requires a new column
or table plus re-embedding, because existing rows cannot be reinterpreted
at another width. This module is the single place that width is declared in
code, and `validate_result` is the single place every provider response is
checked against it. Three independent layers refuse an incompatible vector:

1. This module: provider-declared dimension, configured dimension, column
   width, and every returned vector's length must all agree *before*
   anything is persisted.
2. `app.domain.document_chunk_embedding.ChunkEmbeddingUpsert`: rejects an
   empty or non-finite vector.
3. The database: the column's `vector(N)` type rejects a wrong-width value,
   and `CHECK (vector_dims(embedding) = dimension)` rejects a row whose
   recorded dimension disagrees with its actual vector.

`EMBEDDING_COLUMN_DIMENSION` is a **DRAFT pilot value** pending provider
and model approval. 1024 is justified only as a width both leading
candidates support natively (see ADR-021); it is not a final decision. The
draft migration (`alembic/drafts/0022_document_embeddings.py`) must be
finalized against the chosen model before it is moved into
`alembic/versions/`, and a unit test fails if the two ever disagree.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from app.embeddings.base import EmbeddingResult
from app.embeddings.errors import EmbeddingConfigurationError, EmbeddingDimensionMismatchError

EMBEDDING_COLUMN_DIMENSION = 1024


@dataclass(frozen=True, slots=True)
class EmbeddingModelSpec:
    """The model identity a job embeds with — and therefore the unique key
    component stored on every embedding row."""

    provider: str
    model_id: str
    model_version: str
    dimension: int

    def __post_init__(self) -> None:
        if not self.provider or not self.model_id or not self.model_version:
            raise EmbeddingConfigurationError("embedding model spec has an empty identity field")
        if self.dimension <= 0:
            raise EmbeddingConfigurationError("embedding dimension must be positive")
        if self.dimension != EMBEDDING_COLUMN_DIMENSION:
            raise EmbeddingConfigurationError(
                f"model dimension {self.dimension} does not match the embedding column width "
                f"{EMBEDDING_COLUMN_DIMENSION}; changing the width requires a new column/table "
                "and re-embedding, not a configuration change"
            )


def validate_result(
    result: EmbeddingResult, *, spec: EmbeddingModelSpec, expected_vectors: int
) -> None:
    """Raises `EmbeddingDimensionMismatchError` unless `result` exactly
    matches `spec` and the number of inputs sent."""
    if (result.model_id, result.model_version) != (spec.model_id, spec.model_version):
        raise EmbeddingDimensionMismatchError(
            "provider returned a different model identity than the job's model spec"
        )
    if result.dimension != spec.dimension:
        raise EmbeddingDimensionMismatchError(
            f"provider reported dimension {result.dimension}, expected {spec.dimension}"
        )
    if len(result.vectors) != expected_vectors:
        raise EmbeddingDimensionMismatchError(
            f"provider returned {len(result.vectors)} vectors for {expected_vectors} inputs"
        )
    for vector in result.vectors:
        _validate_vector(vector, dimension=spec.dimension)


def _validate_vector(vector: Sequence[float], *, dimension: int) -> None:
    if len(vector) != dimension:
        raise EmbeddingDimensionMismatchError(
            f"vector length {len(vector)} does not match expected dimension {dimension}"
        )
    if not all(math.isfinite(x) for x in vector):
        raise EmbeddingDimensionMismatchError("vector contains a non-finite value")
