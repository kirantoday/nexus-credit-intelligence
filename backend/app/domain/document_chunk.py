"""Canonical domain objects for `document_chunk` (Milestone 10C).

See `app.models.document_chunk`'s module docstring for the denormalized
`issuer_id`/`confidentiality_classification` rationale.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.core.types import AccessClassification, DocumentChunkElementType


class DocumentChunkCreate(BaseModel):
    model_config = ConfigDict(frozen=True)

    document_extraction_id: uuid.UUID
    research_document_id: uuid.UUID
    issuer_id: uuid.UUID
    chunk_index: int
    element_type: DocumentChunkElementType
    content: str
    content_type: str = "markdown"
    page_start: int | None = None
    page_end: int | None = None
    section_path: str | None = None
    section_title: str | None = None
    token_count: int | None = None
    confidentiality_classification: AccessClassification


class DocumentChunk(BaseModel):
    """A persisted `document_chunk` row."""

    model_config = ConfigDict(frozen=True)

    id: uuid.UUID
    document_extraction_id: uuid.UUID
    research_document_id: uuid.UUID
    issuer_id: uuid.UUID
    chunk_index: int
    element_type: DocumentChunkElementType
    content: str
    content_type: str
    page_start: int | None
    page_end: int | None
    section_path: str | None
    section_title: str | None
    token_count: int | None
    confidentiality_classification: AccessClassification
    created_at: datetime
