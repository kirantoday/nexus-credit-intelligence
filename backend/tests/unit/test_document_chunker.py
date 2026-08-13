"""Unit tests for `app.extraction.chunker.chunk_extraction` (Milestone
10C) — pure function, synthetic `ExtractionResult` inputs, no I/O, no
real PDF/PyMuPDF4LLM involved (that's `test_pymupdf4llm_extractor.py`'s
job). Covers: heading/body merging, table atomicity, list detection,
long-section splitting with retained context, oversized-block splitting,
cross-page span, and deterministic/unique ordinals.
"""

from __future__ import annotations

from app.core.types import DocumentChunkElementType
from app.extraction.base import ExtractedPage, ExtractionResult
from app.extraction.chunker import HARD_CEILING_CHARS, TARGET_CHUNK_CHARS, chunk_extraction


def _result(*page_texts: str) -> ExtractionResult:
    return ExtractionResult(
        pages=[
            ExtractedPage(page_number=i + 1, markdown_text=text)
            for i, text in enumerate(page_texts)
        ],
        extractor_provider="test",
        extractor_version="0.0.0",
    )


def test_empty_extraction_produces_zero_chunks() -> None:
    assert chunk_extraction(_result("")) == []
    assert chunk_extraction(_result()) == []


def test_heading_with_body_merges_into_one_chunk() -> None:
    result = _result("## ARTICLE VI\n\nThe Borrower shall not permit...")
    chunks = chunk_extraction(result)
    assert len(chunks) == 1
    assert chunks[0].element_type is DocumentChunkElementType.TEXT
    assert "ARTICLE VI" in chunks[0].content
    assert "shall not permit" in chunks[0].content
    assert chunks[0].section_title == "ARTICLE VI"


def test_consecutive_headings_first_is_standalone_second_merges_with_body() -> None:
    result = _result("# CREDIT AGREEMENT\n\n## ARTICLE VI\n\nBody text here.")
    chunks = chunk_extraction(result)
    assert len(chunks) == 2
    assert chunks[0].element_type is DocumentChunkElementType.HEADING
    assert chunks[0].section_title == "CREDIT AGREEMENT"
    assert chunks[1].element_type is DocumentChunkElementType.TEXT
    assert chunks[1].section_title == "ARTICLE VI"
    assert chunks[1].section_path == "CREDIT AGREEMENT > ARTICLE VI"


def test_table_block_is_never_split_and_flushes_preceding_text() -> None:
    result = _result("Some intro text.\n\n|A|B|\n|---|---|\n|1|2|\n|3|4|\n\nMore text after.")
    chunks = chunk_extraction(result)
    types = [c.element_type for c in chunks]
    assert DocumentChunkElementType.TABLE in types
    table_chunk = next(c for c in chunks if c.element_type is DocumentChunkElementType.TABLE)
    assert table_chunk.content.count("\n") == 3  # header + separator + 2 data rows, atomic
    assert "|1|2|" in table_chunk.content
    assert "|3|4|" in table_chunk.content


def test_list_dominant_block_classified_as_list() -> None:
    result = _result("- First item\n- Second item\n- Third item")
    chunks = chunk_extraction(result)
    assert len(chunks) == 1
    assert chunks[0].element_type is DocumentChunkElementType.LIST


def test_long_section_splits_into_bounded_chunks_retaining_section_context() -> None:
    heading = "## Financial Covenants"
    paragraph = "Word " * 200  # ~1000 chars, well under TARGET but forces multiple flushes
    # Three separate paragraph blocks under the same heading, each large
    # enough that accumulating all three exceeds TARGET_CHUNK_CHARS.
    text = "\n\n".join([heading, paragraph, paragraph, paragraph])
    result = _result(text)
    chunks = chunk_extraction(result)
    assert len(chunks) > 1
    assert all(c.section_title == "Financial Covenants" for c in chunks)
    assert all(len(c.content) <= TARGET_CHUNK_CHARS + len(paragraph) for c in chunks)


def test_oversized_single_block_is_split_at_hard_ceiling() -> None:
    giant = "word " * 2000  # ~10,000 chars, no internal blank lines
    result = _result(giant)
    chunks = chunk_extraction(result)
    assert len(chunks) > 1
    assert all(len(c.content) <= HARD_CEILING_CHARS for c in chunks)


def test_chunk_spans_pages_when_accumulator_carries_over() -> None:
    """No heading/table/size boundary falls between the two pages' content,
    so the accumulator correctly carries straight through the page break
    into one chunk spanning both pages — the desired behavior the milestone
    brief calls out explicitly ("a chunk that starts near the end of one
    page and is still accumulating when the next page begins correctly
    spans both")."""
    result = _result("## Section A\n\nStart of section.", "continued content on page two.")
    chunks = chunk_extraction(result)
    assert len(chunks) == 1
    assert chunks[0].page_start == 1
    assert chunks[0].page_end == 2
    assert "Start of section" in chunks[0].content
    assert "continued content on page two" in chunks[0].content


def test_chunk_indices_are_contiguous_and_unique() -> None:
    result = _result("# A\n\ntext one\n\n## B\n\ntext two\n\n### C\n\ntext three")
    chunks = chunk_extraction(result)
    indices = [c.chunk_index for c in chunks]
    assert indices == list(range(len(chunks)))


def test_deterministic_across_repeated_runs() -> None:
    result = _result("# A\n\n## B\n\nBody.\n\n|x|y|\n|---|---|\n|1|2|")
    first = chunk_extraction(result)
    second = chunk_extraction(result)
    assert [c.content for c in first] == [c.content for c in second]
    assert [c.element_type for c in first] == [c.element_type for c in second]
