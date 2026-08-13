"""`PyMuPDF4LLMExtractor` — the only `Extractor` implementation in this
codebase (Milestone 10C). `pymupdf4llm`/`pymupdf` (`fitz`) are imported
nowhere else — every other module in this codebase reaches extraction
capability only through the `Extractor` Protocol in `app.extraction.base`.

`pymupdf4llm.to_markdown(..., page_chunks=True)` returns one dict per
page (`text`, `metadata`, `toc_items`, `page_boxes` in the installed
1.28.x series) — live-verified against real synthetic fixtures before
this was written, not assumed from documentation of an older API shape:
headings are emitted as Markdown (`#`/`##`, relative to the page's own
font-size distribution — not every distinct size gets its own level, and
a page with little size variety may get no heading markers at all, a
normal case `app.extraction.chunker` must handle, not an error) and real
ruled tables are emitted as pipe-table Markdown (`|...|` rows plus a
`|---|` separator) — confirmed only appears when the source PDF has
actual ruling lines forming a grid, not merely visually-aligned text.
"""

from __future__ import annotations

import tempfile
from importlib.metadata import version as package_version
from pathlib import Path

import pymupdf4llm  # type: ignore[import-untyped]

from app.extraction.base import ExtractedPage, ExtractionFailure, ExtractionResult

PROVIDER_NAME = "pymupdf4llm"


class PyMuPDF4LLMExtractor:
    def extract(self, source_bytes: bytes, *, content_type: str) -> ExtractionResult:
        del content_type  # this extractor only ever receives PDF bytes (10C scope)
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                # pymupdf4llm's public API takes a file path, not raw bytes —
                # a short-lived temp file, never left behind after this call.
                tmp_path = Path(tmpdir) / "source.pdf"
                tmp_path.write_bytes(source_bytes)
                pages_raw = pymupdf4llm.to_markdown(str(tmp_path), page_chunks=True)
        except Exception as exc:  # noqa: BLE001 - classified as a deterministic
            # extraction failure for the caller; a corrupt/unsupported PDF is
            # never worth retrying automatically (see DocumentExtractionErrorClass).
            raise ExtractionFailure(f"PyMuPDF4LLM failed to parse source: {exc}") from exc

        pages = [
            ExtractedPage(
                page_number=page["metadata"].get("page_number", index + 1),
                markdown_text=page.get("text", ""),
            )
            for index, page in enumerate(pages_raw)
        ]
        return ExtractionResult(
            pages=pages,
            extractor_provider=PROVIDER_NAME,
            extractor_version=package_version("pymupdf4llm"),
        )
