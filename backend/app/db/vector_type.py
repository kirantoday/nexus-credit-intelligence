"""Minimal SQLAlchemy column type for a pgvector `vector(N)` column
(Milestone 10D.2).

This exists so `Base.metadata` can describe the embedding column without
adding a Python dependency before the `pgvector` package decision is made
(see ADR-021). It declares only the DDL type. **Application writes do not
use it**: `document_chunk_embedding_repository` inserts with explicit SQL
(`CAST(:embedding AS vector)`), which does not depend on how a driver
adapts a Python list. Reads of vectors are not needed until 10D.3, which
will decide between this type's operators and the `pgvector` package.

The type never touches the `vector` extension itself — that is created by
migration 0001 and is a shared, database-wide resource.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.types import UserDefinedType


def format_vector_literal(values: list[float]) -> str:
    """pgvector's text input format: `[0.1,0.2,...]`."""
    return "[" + ",".join(repr(float(v)) for v in values) + "]"


class Vector(UserDefinedType[Any]):
    cache_ok = True

    def __init__(self, dimensions: int) -> None:
        if dimensions <= 0:
            raise ValueError("vector dimensions must be positive")
        self.dimensions = dimensions

    def get_col_spec(self, **kw: Any) -> str:
        return f"vector({self.dimensions})"

    def bind_processor(self, dialect: Any) -> Any:
        def process(value: list[float] | None) -> str | None:
            return None if value is None else format_vector_literal(value)

        return process
