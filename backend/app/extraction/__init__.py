"""Document Intelligence extraction/chunking layer (Milestone 10C).

`app.extraction.base` defines the provider-neutral `Extractor` Protocol
and `ExtractionResult` (ADR-010's shape, applied to extraction instead of
chat completion — see that module's docstring). `pymupdf4llm_extractor`
is the only implementation; `pymupdf4llm`/`pymupdf` are imported nowhere
else in this codebase. `chunker` implements `chunking_v1`, a pure function
over `ExtractionResult` with no extractor-specific knowledge. `validation`
holds the deterministic pre-promotion checks, including the `needs_ocr`
heuristic.
"""

from __future__ import annotations
