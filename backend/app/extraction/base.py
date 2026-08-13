"""`Extractor` Protocol (Milestone 10C) — no business/domain/service code
depends on a vendor extraction SDK directly. Mirrors `app.ai.providers.
base.LLMProvider`'s already-established shape (ADR-010): plain, Nexus-owned
dataclasses cross the boundary, never a vendor-specific object.

`ExtractionResult` is intentionally generic — any extractor that can
express a document as an ordered sequence of per-page Markdown-like text
(headings via `#`/`##`/..., tables via pipe syntax) satisfies this
contract, not only PyMuPDF4LLM. `app.extraction.chunker` (`chunking_v1`)
consumes only this shape, never a PyMuPDF4LLM-specific object.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ExtractedPage:
    page_number: int  # 1-indexed, matches how analysts cite PDF pages
    markdown_text: str


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    pages: list[ExtractedPage]
    extractor_provider: str
    extractor_version: str

    @property
    def page_count(self) -> int:
        return len(self.pages)


class ExtractionFailure(Exception):
    """The extractor could not process the source bytes at all — a
    deterministic failure (corrupt/unsupported PDF) by default. Callers
    that can distinguish a transient cause (e.g. a Storage download
    failure that happens before the extractor is ever invoked) classify
    that separately — see `app.services.document_extraction_service`."""


class Extractor(Protocol):
    def extract(self, source_bytes: bytes, *, content_type: str) -> ExtractionResult:
        """Raises `ExtractionFailure` if `source_bytes` cannot be parsed at
        all. Never raises for a "successful but suspiciously thin" result
        (e.g. a scanned PDF with near-zero real text) — that judgment
        belongs to `app.extraction.validation.detect_needs_ocr`, which
        runs on a *returned* `ExtractionResult`, not inside the adapter."""
        ...
