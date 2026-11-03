"""Repository for `document_chunk_embedding` (Milestone 10D.2).

Function-style, flush-not-commit. Vector writes use explicit SQL with
`CAST(:embedding AS vector)` rather than the ORM column, so they do not
depend on how a driver adapts a Python list (see `app.db.vector_type`).

**Replacement is a single guarded upsert, never delete-then-insert.** The
statement inserts a new row, or — when `(chunk_id, embedding_model,
embedding_model_version)` already exists — updates it **only if the stored
`content_fingerprint` differs from the new one**. Consequences:

- an unchanged chunk is a no-op (idempotent reruns, duplicate writers);
- a changed chunk is replaced atomically in one statement, so a valid
  vector is never absent, and if the new vector never arrives (provider
  failure) this function is simply never called and the old row remains;
- two writers racing on the same chunk converge on one row.

Inserted/replaced/unchanged counts are computed from a pre-read of the
stored fingerprints in the same transaction. Under a race they are
approximate; the stored data is correct regardless. The SQL here is
exercised only by the gated integration tests — unit tests do not prove it.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import NamedTuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.base import NEXUS_SCHEMA
from app.db.vector_type import format_vector_literal
from app.domain.document_chunk_embedding import ChunkEmbeddingUpsert


class UpsertCounts(NamedTuple):
    inserted: int
    replaced: int
    unchanged: int


_FINGERPRINTS_FOR_EXTRACTION_SQL = text(
    f"""
    SELECT e.chunk_id, e.content_fingerprint
    FROM {NEXUS_SCHEMA}.document_chunk_embedding e
    JOIN {NEXUS_SCHEMA}.document_chunk c ON c.id = e.chunk_id
    WHERE c.document_extraction_id = :extraction_id
      AND e.embedding_model = :model
      AND e.embedding_model_version = :version
    """
)

_FINGERPRINTS_FOR_CHUNKS_SQL = text(
    f"""
    SELECT chunk_id, content_fingerprint
    FROM {NEXUS_SCHEMA}.document_chunk_embedding
    WHERE chunk_id = ANY(:chunk_ids)
      AND embedding_model = :model
      AND embedding_model_version = :version
    """
)

_UPSERT_SQL = text(
    f"""
    INSERT INTO {NEXUS_SCHEMA}.document_chunk_embedding
        (chunk_id, job_id, embedding_model, embedding_model_version, dimension,
         content_fingerprint, embedding, provenance_id)
    VALUES
        (:chunk_id, :job_id, :model, :version, :dimension,
         :fingerprint, CAST(:embedding AS vector), :provenance_id)
    ON CONFLICT (chunk_id, embedding_model, embedding_model_version) DO UPDATE SET
        job_id = EXCLUDED.job_id,
        dimension = EXCLUDED.dimension,
        content_fingerprint = EXCLUDED.content_fingerprint,
        embedding = EXCLUDED.embedding,
        provenance_id = EXCLUDED.provenance_id,
        revision = {NEXUS_SCHEMA}.document_chunk_embedding.revision + 1,
        updated_at = clock_timestamp()
    WHERE {NEXUS_SCHEMA}.document_chunk_embedding.content_fingerprint
        <> EXCLUDED.content_fingerprint
    """
)


def get_fingerprints_for_extraction(
    db: Session, *, document_extraction_id: uuid.UUID, model: str, version: str
) -> dict[uuid.UUID, str]:
    rows = db.execute(
        _FINGERPRINTS_FOR_EXTRACTION_SQL,
        {"extraction_id": document_extraction_id, "model": model, "version": version},
    ).all()
    return {row.chunk_id: row.content_fingerprint for row in rows}


def upsert_batch(
    db: Session,
    *,
    job_id: uuid.UUID,
    provenance_id: uuid.UUID,
    model: str,
    version: str,
    dimension: int,
    items: Sequence[ChunkEmbeddingUpsert],
) -> UpsertCounts:
    if not items:
        return UpsertCounts(0, 0, 0)

    stored = {
        row.chunk_id: row.content_fingerprint
        for row in db.execute(
            _FINGERPRINTS_FOR_CHUNKS_SQL,
            {"chunk_ids": [item.chunk_id for item in items], "model": model, "version": version},
        ).all()
    }

    inserted = replaced = unchanged = 0
    params: list[dict[str, object]] = []
    for item in items:
        previous = stored.get(item.chunk_id)
        if previous is None:
            inserted += 1
        elif previous != item.content_fingerprint:
            replaced += 1
        else:
            unchanged += 1
            continue
        params.append(
            {
                "chunk_id": item.chunk_id,
                "job_id": job_id,
                "model": model,
                "version": version,
                "dimension": dimension,
                "fingerprint": item.content_fingerprint,
                "embedding": format_vector_literal(item.vector),
                "provenance_id": provenance_id,
            }
        )

    if params:
        db.execute(_UPSERT_SQL, params)
        db.flush()
    return UpsertCounts(inserted, replaced, unchanged)
