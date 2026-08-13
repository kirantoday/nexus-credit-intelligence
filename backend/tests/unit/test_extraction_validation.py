"""Unit tests for `app.extraction.validation` (Milestone 10C):
`detect_needs_ocr`'s heuristic and `validate_chunks`'s deterministic
pre-promotion checks."""

from __future__ import annotations

from app.core.types import DocumentChunkElementType
from app.extraction.base import ExtractedPage, ExtractionResult
from app.extraction.chunker import ChunkDraft
from app.extraction.validation import detect_needs_ocr, validate_chunks


def _chunk(index: int, content: str = "some content", **overrides: object) -> ChunkDraft:
    defaults: dict[str, object] = dict(
        element_type=DocumentChunkElementType.TEXT,
        content=content,
        page_start=1,
        page_end=1,
        section_path=None,
        section_title=None,
        chunk_index=index,
    )
    defaults.update(overrides)
    return ChunkDraft(**defaults)  # type: ignore[arg-type]


def test_needs_ocr_true_for_near_empty_pages() -> None:
    result = ExtractionResult(
        pages=[ExtractedPage(page_number=1, markdown_text=".")],
        extractor_provider="test",
        extractor_version="0.0.0",
    )
    assert detect_needs_ocr(result) is True


def test_needs_ocr_false_for_real_content() -> None:
    result = ExtractionResult(
        pages=[
            ExtractedPage(
                page_number=1,
                markdown_text="# ARTICLE VI\n\nThe Borrower shall not permit the ratio to exceed "
                "4.50 to 1.00 as of the last day of any Test Period.",
            )
        ],
        extractor_provider="test",
        extractor_version="0.0.0",
    )
    assert detect_needs_ocr(result) is False


def test_needs_ocr_false_for_zero_pages() -> None:
    result = ExtractionResult(pages=[], extractor_provider="test", extractor_version="0.0.0")
    assert detect_needs_ocr(result) is False


def test_validate_chunks_fails_on_empty_list() -> None:
    result = validate_chunks([])
    assert result.passed is False


def test_validate_chunks_passes_for_well_formed_chunks() -> None:
    chunks = [_chunk(0), _chunk(1), _chunk(2)]
    result = validate_chunks(chunks)
    assert result.passed is True


def test_validate_chunks_fails_on_duplicate_ordinal() -> None:
    chunks = [_chunk(0), _chunk(0)]
    result = validate_chunks(chunks)
    assert result.passed is False
    assert "duplicate" in result.reason


def test_validate_chunks_fails_on_empty_content() -> None:
    chunks = [_chunk(0, content="   ")]
    result = validate_chunks(chunks)
    assert result.passed is False


def test_validate_chunks_fails_on_invalid_page_range() -> None:
    chunks = [_chunk(0, page_start=5, page_end=2)]
    result = validate_chunks(chunks)
    assert result.passed is False


def test_validate_chunks_fails_on_non_contiguous_ordinals() -> None:
    chunks = [_chunk(0), _chunk(2)]
    result = validate_chunks(chunks)
    assert result.passed is False
