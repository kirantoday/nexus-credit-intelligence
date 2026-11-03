"""Canonical domain objects for `document_chunk_embedding` (Milestone
10D.2). See `app.models.document_chunk_embedding` for uniqueness,
replacement, and width semantics."""

from __future__ import annotations

import math
import re
import uuid

from pydantic import BaseModel, ConfigDict, field_validator

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ChunkEmbeddingUpsert(BaseModel):
    """One vector ready to be persisted for one chunk. Rejects an empty or
    non-finite vector and a malformed fingerprint; the width is checked
    against the model contract by `app.embeddings.dimensions` and again by
    the database."""

    model_config = ConfigDict(frozen=True)

    chunk_id: uuid.UUID
    content_fingerprint: str
    vector: list[float]

    @field_validator("content_fingerprint")
    @classmethod
    def _fingerprint_is_sha256(cls, value: str) -> str:
        if not _SHA256_RE.match(value):
            raise ValueError("content_fingerprint must be a lowercase hex SHA-256")
        return value

    @field_validator("vector")
    @classmethod
    def _vector_is_usable(cls, value: list[float]) -> list[float]:
        if not value:
            raise ValueError("vector must not be empty")
        if not all(math.isfinite(x) for x in value):
            raise ValueError("vector must contain only finite numbers")
        return value
