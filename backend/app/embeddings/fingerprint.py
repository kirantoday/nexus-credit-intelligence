"""Embedded-input construction and content fingerprinting (Milestone 10D.2).

The fingerprint answers one question: *would re-embedding this chunk with
this model produce a different input to the vendor than what the stored
vector was built from?* It covers the exact embedded text plus every piece
of model metadata that changes the vector, so an unchanged fingerprint
means a stored vector can be trusted and no provider call is needed.

What changes it: the document title (analysts can edit it), the chunk's
section path, the chunk content (immutable per chunk id today, but covered
anyway), the template version, the input type, and the model's id/version/
dimension. Each field is length-prefixed so adjacent fields can never be
re-split into a colliding combination.
"""

from __future__ import annotations

import hashlib

from app.core.types import EmbeddingInputType

# Bump when `build_embedding_input`'s layout changes — every stored
# fingerprint then differs, which is exactly what marks existing vectors
# stale.
EMBEDDING_INPUT_TEMPLATE_VERSION = "v1"

_NO_SECTION = "-"


def build_embedding_input(*, document_title: str, section_path: str | None, content: str) -> str:
    """The exact string sent to the vendor for one chunk. Title and section
    path carry context a mid-section chunk would otherwise lack ("Section
    6.01 — Indebtedness" for a chunk that starts mid-paragraph). `content`
    is never altered."""
    title = document_title.strip()
    section = (section_path or "").strip() or _NO_SECTION
    return f"Document: {title}\nSection: {section}\n\n{content}"


def compute_fingerprint(
    *,
    embedded_text: str,
    input_type: EmbeddingInputType,
    model_id: str,
    model_version: str,
    dimension: int,
    template_version: str = EMBEDDING_INPUT_TEMPLATE_VERSION,
) -> str:
    digest = hashlib.sha256()
    for field in (
        template_version,
        input_type.value,
        model_id,
        model_version,
        str(dimension),
        embedded_text,
    ):
        encoded = field.encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return digest.hexdigest()


def estimate_tokens(text: str) -> int:
    """Deterministic approximation (`len // 4`, floor 1) matching
    `app.extraction.chunker`'s documented `token_count` — used only for
    pre-call budget checks, never as the recorded usage when the vendor
    reports a real count."""
    return max(1, len(text) // 4)
