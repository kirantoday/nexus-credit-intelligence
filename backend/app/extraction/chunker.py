"""`chunking_v1` (Milestone 10C) — structure-aware chunking over an
`ExtractionResult`. Pure function, no I/O, no extractor-specific
knowledge — operates only on `app.extraction.base.ExtractionResult`'s
generic per-page Markdown shape.

Algorithm, in order of precedence per Markdown block (blocks are
blank-line-separated units within a page's text):

1. A pipe-table block (every non-empty line starts and ends with `|`) is
   never split — emitted as one atomic `table` chunk, flushing whatever
   text was accumulating first.
2. A heading line (`#`...`######`) never merges with the block before
   it — flushes the accumulator, then updates a heading stack (popping
   any heading at the same or deeper level) that drives `section_path`/
   `section_title` for every subsequent chunk, and starts the *next*
   accumulator with the heading text itself as its first line — so a
   heading normally travels together with the body text under it in one
   chunk (matching the citation example in the milestone brief: "ARTICLE
   VI / Financial Covenants / Section 6.11" all appear together with
   their body). A heading that is never followed by body text before the
   next boundary is emitted alone as a standalone `heading` chunk — the
   only way `element_type=heading` occurs.
3. Ordinary paragraph/list blocks accumulate into the current chunk until
   `TARGET_CHUNK_CHARS` is reached, then flush and start a new chunk that
   *retains* the current section context (heading stack unchanged) — "for
   long sections, split into bounded chunks while retaining section
   context," per the milestone brief. A single block larger than
   `HARD_CEILING_CHARS` (rare — a giant run-on paragraph) is split at
   whitespace boundaries so no chunk ever exceeds the ceiling.

`element_type=list` is assigned when a majority of a chunk's non-empty
lines start with a list marker (`-`, `*`, or `N.`/`N)`); everything else
that isn't a table or a heading-only chunk is `text`.

`page_start`/`page_end` track the first and last page that contributed
content to a chunk — usually equal, but a chunk that starts near the end
of one page and is still accumulating when the next page begins correctly
spans both.

`token_count` is `len(content) // 4`, a deterministic approximation
documented as such — never a real tokenizer (no such dependency exists in
this codebase, and none is needed for 10C's zero-embedding scope).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.core.types import DocumentChunkElementType
from app.extraction.base import ExtractionResult

CHUNKING_STRATEGY_VERSION = "structure_v1"

TARGET_CHUNK_CHARS = 2400
HARD_CEILING_CHARS = 4000

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
_TABLE_ROW_RE = re.compile(r"^\|.*\|\s*$")
_LIST_MARKER_RE = re.compile(r"^\s*([-*]|\d+[.)])\s+")


@dataclass(slots=True)
class ChunkDraft:
    """Chunker output, before repository persistence assigns `chunk_index`
    (set by `chunk_extraction` itself, in document order) and before the
    service layer attaches `document_extraction_id`/`research_document_id`/
    `issuer_id`/`confidentiality_classification` (chunker-agnostic —
    provenance/authorization fields, not structural ones)."""

    element_type: DocumentChunkElementType
    content: str
    page_start: int | None
    page_end: int | None
    section_path: str | None
    section_title: str | None
    chunk_index: int = field(default=-1)

    @property
    def token_count(self) -> int:
        return max(1, len(self.content) // 4)


def _split_blocks(markdown_text: str) -> list[str]:
    blocks = re.split(r"\n\s*\n", markdown_text)
    return [b.strip() for b in blocks if b.strip()]


def _is_table_block(block: str) -> bool:
    lines = [line for line in block.splitlines() if line.strip()]
    return len(lines) >= 2 and all(_TABLE_ROW_RE.match(line) for line in lines)


def _heading_match(block: str) -> tuple[int, str] | None:
    lines = [line for line in block.splitlines() if line.strip()]
    if len(lines) != 1:
        return None
    m = _HEADING_RE.match(lines[0])
    if m is None:
        return None
    return len(m.group(1)), m.group(2)


def _is_list_dominant(content: str) -> bool:
    lines = [line for line in content.splitlines() if line.strip()]
    if not lines:
        return False
    list_lines = sum(1 for line in lines if _LIST_MARKER_RE.match(line))
    return list_lines > len(lines) / 2


def _split_oversized(block: str, max_chars: int) -> list[str]:
    """Splits a single block exceeding `HARD_CEILING_CHARS` at whitespace
    boundaries — only reached for a genuinely giant run-on paragraph with
    no internal blank lines, not the common case."""
    words = block.split(" ")
    pieces: list[str] = []
    current: list[str] = []
    current_len = 0
    for word in words:
        added_len = len(word) + (1 if current else 0)
        if current and current_len + added_len > max_chars:
            pieces.append(" ".join(current))
            current = [word]
            current_len = len(word)
        else:
            current.append(word)
            current_len += added_len
    if current:
        pieces.append(" ".join(current))
    return pieces


class _Accumulator:
    """Mutable buffer for one in-progress chunk. A thin, private class
    (not a dataclass) purely to keep `chunk_extraction`'s main loop free
    of a dozen `nonlocal` statements."""

    def __init__(self) -> None:
        self.lines: list[str] = []
        self.page_start: int | None = None
        self.page_end: int | None = None
        self.has_body = False

    def append(self, text: str, *, page_number: int, is_body: bool) -> None:
        self.lines.append(text)
        if self.page_start is None:
            self.page_start = page_number
        self.page_end = page_number
        self.has_body = self.has_body or is_body

    @property
    def char_count(self) -> int:
        return sum(len(line) for line in self.lines)

    def is_empty(self) -> bool:
        return not self.lines

    def reset(self) -> None:
        self.lines = []
        self.page_start = None
        self.page_end = None
        self.has_body = False


def chunk_extraction(result: ExtractionResult) -> list[ChunkDraft]:
    drafts: list[ChunkDraft] = []
    heading_stack: list[tuple[int, str]] = []
    acc = _Accumulator()

    def section_title() -> str | None:
        return heading_stack[-1][1] if heading_stack else None

    def section_path() -> str | None:
        return " > ".join(title for _level, title in heading_stack) if heading_stack else None

    def flush() -> None:
        if acc.is_empty():
            return
        content = "\n\n".join(acc.lines).strip()
        if not content:
            acc.reset()
            return
        element_type = (
            DocumentChunkElementType.HEADING
            if not acc.has_body
            else (
                DocumentChunkElementType.LIST
                if _is_list_dominant(content)
                else DocumentChunkElementType.TEXT
            )
        )
        drafts.append(
            ChunkDraft(
                element_type=element_type,
                content=content,
                page_start=acc.page_start,
                page_end=acc.page_end,
                section_path=section_path(),
                section_title=section_title(),
            )
        )
        acc.reset()

    for page in result.pages:
        for block in _split_blocks(page.markdown_text):
            if _is_table_block(block):
                flush()
                drafts.append(
                    ChunkDraft(
                        element_type=DocumentChunkElementType.TABLE,
                        content=block,
                        page_start=page.page_number,
                        page_end=page.page_number,
                        section_path=section_path(),
                        section_title=section_title(),
                    )
                )
                continue

            heading = _heading_match(block)
            if heading is not None:
                flush()
                level, title = heading
                while heading_stack and heading_stack[-1][0] >= level:
                    heading_stack.pop()
                heading_stack.append((level, title))
                acc.append(block, page_number=page.page_number, is_body=False)
                continue

            pieces = (
                _split_oversized(block, HARD_CEILING_CHARS)
                if len(block) > HARD_CEILING_CHARS
                else [block]
            )
            for piece in pieces:
                if acc.char_count and acc.char_count + len(piece) > TARGET_CHUNK_CHARS:
                    flush()
                acc.append(piece, page_number=page.page_number, is_body=True)

    flush()

    for index, draft in enumerate(drafts):
        draft.chunk_index = index
    return drafts
