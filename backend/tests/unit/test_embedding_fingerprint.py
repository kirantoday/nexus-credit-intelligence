"""Unit tests for `app.embeddings.fingerprint` (Milestone 10D.2): the
fingerprint must be stable for identical input and change whenever anything
that changes the vector changes."""

from __future__ import annotations

from app.core.types import EmbeddingInputType
from app.embeddings.fingerprint import (
    EMBEDDING_INPUT_TEMPLATE_VERSION,
    build_embedding_input,
    compute_fingerprint,
    estimate_tokens,
)


def _fp(**overrides: object) -> str:
    base: dict[str, object] = {
        "embedded_text": build_embedding_input(
            document_title="Credit Agreement", section_path="ARTICLE VI > 6.01", content="Body."
        ),
        "input_type": EmbeddingInputType.DOCUMENT,
        "model_id": "m",
        "model_version": "1",
        "dimension": 1024,
    }
    base.update(overrides)
    return compute_fingerprint(**base)  # type: ignore[arg-type]


def test_fingerprint_is_stable_and_lowercase_sha256_hex() -> None:
    first = _fp()
    assert first == _fp()
    assert len(first) == 64
    assert first == first.lower()
    int(first, 16)


def test_input_includes_title_section_and_untouched_content() -> None:
    text = build_embedding_input(
        document_title="  Credit Agreement  ", section_path=" A > B ", content="  Body  \n"
    )
    assert text == "Document: Credit Agreement\nSection: A > B\n\n  Body  \n"


def test_missing_section_is_represented_consistently() -> None:
    assert "Section: -\n" in build_embedding_input(
        document_title="T", section_path=None, content="x"
    )
    assert build_embedding_input(document_title="T", section_path="  ", content="x") == (
        build_embedding_input(document_title="T", section_path=None, content="x")
    )


def test_changed_title_changes_fingerprint() -> None:
    a = build_embedding_input(document_title="A", section_path=None, content="x")
    b = build_embedding_input(document_title="B", section_path=None, content="x")
    assert _fp(embedded_text=a) != _fp(embedded_text=b)


def test_changed_section_path_changes_fingerprint() -> None:
    a = build_embedding_input(document_title="T", section_path="S1", content="x")
    b = build_embedding_input(document_title="T", section_path="S2", content="x")
    assert _fp(embedded_text=a) != _fp(embedded_text=b)


def test_changed_content_changes_fingerprint() -> None:
    a = build_embedding_input(document_title="T", section_path=None, content="x")
    b = build_embedding_input(document_title="T", section_path=None, content="y")
    assert _fp(embedded_text=a) != _fp(embedded_text=b)


def test_changed_model_id_version_dimension_or_input_type_changes_fingerprint() -> None:
    base = _fp()
    assert _fp(model_id="other") != base
    assert _fp(model_version="2") != base
    assert _fp(dimension=512) != base
    assert _fp(input_type=EmbeddingInputType.QUERY) != base


def test_changed_template_version_changes_fingerprint() -> None:
    assert _fp(template_version="v2") != _fp(template_version=EMBEDDING_INPUT_TEMPLATE_VERSION)


def test_length_prefixing_prevents_field_boundary_collisions() -> None:
    # Without length prefixes these two would concatenate identically.
    a = compute_fingerprint(
        embedded_text="bc",
        input_type=EmbeddingInputType.DOCUMENT,
        model_id="a",
        model_version="1",
        dimension=1,
    )
    b = compute_fingerprint(
        embedded_text="c",
        input_type=EmbeddingInputType.DOCUMENT,
        model_id="ab",
        model_version="1",
        dimension=1,
    )
    assert a != b


def test_estimate_tokens_is_deterministic_with_floor_of_one() -> None:
    assert estimate_tokens("") == 1
    assert estimate_tokens("abcd" * 10) == 10
