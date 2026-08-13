"""Deterministic extraction/chunk quality validation (Milestone 10C).

Runs *before* promotion — a `document_extraction` attempt is never marked
`completed`/`is_current=true` unless `validate_chunks` passes. No LLM-as-
judge, no Ragas — every check here is a cheap, deterministic assertion
over already-computed structures, matching the milestone's "0 AI calls"
requirement.

`detect_needs_ocr` is a conservative heuristic distinct from a parser
failure: a scanned/image-only PDF still "extracts successfully" (no
exception) but produces near-zero real text relative to its page count —
that is a different, honestly-labeled condition
(`DocumentExtractionStatus.NEEDS_OCR`) from `FAILED`, per the milestone
brief's explicit instruction not to conflate the two.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.extraction.base import ExtractionResult
from app.extraction.chunker import ChunkDraft

# Below this average of non-whitespace characters per page, a
# successfully-parsed-but-content-thin PDF is treated as scanned/
# image-only rather than a genuinely short-but-real document. Chosen
# conservatively (a real one-line title page would still likely clear
# this) — see `app.eval.document_intelligence` fixtures for a validated
# example on both sides of the threshold.
_NEEDS_OCR_CHARS_PER_PAGE_THRESHOLD = 40.0


def detect_needs_ocr(result: ExtractionResult) -> bool:
    if result.page_count == 0:
        return False
    total_chars = sum(len(page.markdown_text.strip()) for page in result.pages)
    return (total_chars / result.page_count) < _NEEDS_OCR_CHARS_PER_PAGE_THRESHOLD


@dataclass(frozen=True, slots=True)
class ValidationResult:
    passed: bool
    reason: str


def validate_chunks(chunks: list[ChunkDraft]) -> ValidationResult:
    """Every check is cheap and deterministic — no chunk content is judged
    for "quality" beyond these structural guarantees; the milestone's own
    deterministic eval corpus (`backend/eval/document_intelligence/`) is
    the tool for judging chunking *quality*, not this function.
    `confidentiality_classification` propagation is not re-validated here:
    it is a single assignment from the source document's own classification
    at `DocumentChunkCreate` construction time in
    `document_extraction_service`, applied identically to every chunk —
    there is no branch that could apply it inconsistently, so there is
    nothing here for a structural check to catch."""
    if not chunks:
        return ValidationResult(False, "extraction produced zero chunks")

    seen_ordinals: set[int] = set()
    for chunk in chunks:
        if chunk.chunk_index in seen_ordinals:
            return ValidationResult(
                False, f"duplicate chunk_index {chunk.chunk_index} — ordinals must be unique"
            )
        seen_ordinals.add(chunk.chunk_index)

        if not chunk.content.strip():
            return ValidationResult(False, f"chunk {chunk.chunk_index} has empty content")

        if (
            chunk.page_start is not None
            and chunk.page_end is not None
            and chunk.page_start > chunk.page_end
        ):
            return ValidationResult(
                False,
                f"chunk {chunk.chunk_index} has invalid page range "
                f"({chunk.page_start} > {chunk.page_end})",
            )

    if seen_ordinals != set(range(len(chunks))):
        return ValidationResult(False, "chunk ordinals are not a contiguous 0..N-1 sequence")

    return ValidationResult(True, f"{len(chunks)} chunks passed validation")
