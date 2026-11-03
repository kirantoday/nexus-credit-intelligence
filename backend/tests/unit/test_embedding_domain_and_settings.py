"""Unit tests for the 10D.2 domain objects, vector literal formatting, and
settings defaults. These need pydantic/SQLAlchemy/pydantic-settings (the
project's normal dependencies) but no database, network, or provider."""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.core.types import PageReferenceBasis
from app.db.vector_type import Vector, format_vector_literal
from app.domain.document_chunk_embedding import ChunkEmbeddingUpsert
from app.domain.public_document_approval import PublicDocumentApprovalCreate

_SHA = "c" * 64


def _approval(**overrides: object) -> PublicDocumentApprovalCreate:
    values: dict[str, object] = {
        "research_document_id": uuid.UUID(int=1),
        "approved_raw_payload_checksum": _SHA,
        "source_url": "https://example.test/original",
        "page_reference_basis": PageReferenceBasis.ORIGINAL,
        "approval_basis": "public regulatory filing",
        "approved_by": "operator",
    }
    values.update(overrides)
    return PublicDocumentApprovalCreate(**values)  # type: ignore[arg-type]


def test_embeddings_are_disabled_by_default_and_dimension_is_unset() -> None:
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.embeddings_enabled is False
    assert settings.embedding_dimension is None
    assert settings.embedding_model_id is None


def test_original_page_basis_does_not_require_conversion_lineage() -> None:
    assert _approval().page_reference_basis is PageReferenceBasis.ORIGINAL


def test_converted_pdf_approval_requires_source_hash_and_converter_identity() -> None:
    with pytest.raises(ValidationError):
        _approval(page_reference_basis=PageReferenceBasis.CONVERTED_PDF)
    ok = _approval(
        page_reference_basis=PageReferenceBasis.CONVERTED_PDF,
        source_sha256="d" * 64,
        converter_name="converter",
        converter_version="1.0",
    )
    assert ok.page_reference_basis is PageReferenceBasis.CONVERTED_PDF


@pytest.mark.parametrize("bad", ["", "abc", "G" * 64, "A" * 64, "a" * 63])
def test_approval_checksum_must_be_lowercase_hex_sha256(bad: str) -> None:
    with pytest.raises(ValidationError):
        _approval(approved_raw_payload_checksum=bad)


def test_approval_requires_non_empty_basis_and_approver() -> None:
    with pytest.raises(ValidationError):
        _approval(approval_basis="  ")
    with pytest.raises(ValidationError):
        _approval(approved_by="")


def test_embedding_upsert_rejects_empty_and_non_finite_vectors_and_bad_fingerprints() -> None:
    chunk_id = uuid.UUID(int=2)
    assert ChunkEmbeddingUpsert(chunk_id=chunk_id, content_fingerprint=_SHA, vector=[0.1, 0.2])
    with pytest.raises(ValidationError):
        ChunkEmbeddingUpsert(chunk_id=chunk_id, content_fingerprint=_SHA, vector=[])
    with pytest.raises(ValidationError):
        ChunkEmbeddingUpsert(chunk_id=chunk_id, content_fingerprint=_SHA, vector=[float("nan")])
    with pytest.raises(ValidationError):
        ChunkEmbeddingUpsert(chunk_id=chunk_id, content_fingerprint="xyz", vector=[0.1])


def test_vector_literal_uses_pgvector_text_format() -> None:
    assert format_vector_literal([1.0, 0.5, -0.25]) == "[1.0,0.5,-0.25]"


def test_vector_column_type_declares_its_fixed_width() -> None:
    assert Vector(1024).get_col_spec() == "vector(1024)"
    with pytest.raises(ValueError):
        Vector(0)
