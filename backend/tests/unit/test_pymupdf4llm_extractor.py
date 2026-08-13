"""Unit tests for `app.extraction.pymupdf4llm_extractor.PyMuPDF4LLMExtractor`
(Milestone 10C) — the only place `pymupdf4llm`/`pymupdf` is imported
outside this test file and the eval fixture generator. Uses the real
eval-corpus fixtures (no network, no database) — a real, deterministic
PDF library call, matching this project's precedent of testing real
parsing logic directly rather than mocking it (see
`test_run_market_discovery.py`'s equivalent choice for HTTP-level fakes
vs. this file's choice to exercise the real library for something purely
computational)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.extraction.base import ExtractionFailure
from app.extraction.pymupdf4llm_extractor import PyMuPDF4LLMExtractor

_FIXTURES_DIR = Path(__file__).parent.parent.parent / "eval" / "document_intelligence" / "fixtures"


def test_extract_real_pdf_returns_pages_with_markdown_headings() -> None:
    content = (_FIXTURES_DIR / "credit_agreement_excerpt.pdf").read_bytes()
    result = PyMuPDF4LLMExtractor().extract(content, content_type="application/pdf")
    assert result.page_count == 2
    assert result.extractor_provider == "pymupdf4llm"
    assert result.extractor_version
    assert "CREDIT AGREEMENT" in result.pages[0].markdown_text
    assert result.pages[0].page_number == 1
    assert result.pages[1].page_number == 2


def test_extract_real_table_pdf_produces_pipe_table_syntax() -> None:
    content = (_FIXTURES_DIR / "lender_presentation_excerpt.pdf").read_bytes()
    result = PyMuPDF4LLMExtractor().extract(content, content_type="application/pdf")
    assert "|" in result.pages[0].markdown_text
    assert "First Lien Term Loan B" in result.pages[0].markdown_text


def test_extract_garbage_bytes_raises_extraction_failure() -> None:
    with pytest.raises(ExtractionFailure):
        PyMuPDF4LLMExtractor().extract(b"not a real pdf at all", content_type="application/pdf")
