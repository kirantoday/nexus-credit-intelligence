"""Public-document eligibility (Milestone 10D.2, ADR-021).

A document's chunks may be sent to an external embedding vendor — and, in
10D.3+, returned by retrieval — only if **every** condition below holds
*right now*, evaluated from the authoritative parent rows, never from a
chunk's copied `confidentiality_classification`:

1. A server-side approval exists in `public_document_approval` and is not
   revoked. This is the allowlist. It is written only by an operator
   script; no API route, request parameter, ID, or header can add to it.
2. The parent `research_document` is not archived.
3. Its `confidentiality_classification` is `standard`. This is *necessary
   but never sufficient*: the field is client-supplied at upload, so on its
   own it proves nothing about whether a document is public.
4. The stored file's checksum equals the checksum pinned at approval time,
   so a different file can never inherit an earlier approval.
5. The extraction belongs to that document, is the document's current
   extraction, and is `completed`.

The checks run in this order so that a document with no approval fails
closed on the allowlist before anything else is considered.

`RetrievalScope` is the seam where real identity/authorization plugs in
later (a user-aware scope would be a second implementation). There is
deliberately **no** all-access or fallback scope, and the single scope that
exists, `PUBLIC_ALLOWLIST_SCOPE`, takes no input from a caller.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class EligibilityReason(StrEnum):
    ELIGIBLE = "eligible"
    DOCUMENT_NOT_FOUND = "document_not_found"
    NOT_APPROVED = "not_approved"
    ARCHIVED = "archived"
    NOT_STANDARD_CLASSIFICATION = "not_standard_classification"
    CHECKSUM_MISMATCH = "checksum_mismatch"
    EXTRACTION_NOT_FOUND = "extraction_not_found"
    EXTRACTION_NOT_FOR_DOCUMENT = "extraction_not_for_document"
    EXTRACTION_NOT_CURRENT = "extraction_not_current"
    EXTRACTION_NOT_COMPLETED = "extraction_not_completed"


@dataclass(frozen=True, slots=True)
class EligibilityFacts:
    """A snapshot of the authoritative parent rows for one
    (document, extraction) pair, loaded fresh by the repository. `None`
    fields mean "no such row", not "unknown"."""

    document_found: bool
    is_archived: bool
    confidentiality_classification: str | None
    payload_checksum: str | None
    active_approval_checksum: str | None
    extraction_found: bool
    extraction_belongs_to_document: bool
    extraction_is_current: bool
    extraction_status: str | None


@dataclass(frozen=True, slots=True)
class EligibilityDecision:
    eligible: bool
    reason: EligibilityReason


def _deny(reason: EligibilityReason) -> EligibilityDecision:
    return EligibilityDecision(False, reason)


def evaluate_eligibility(facts: EligibilityFacts) -> EligibilityDecision:
    if not facts.document_found:
        return _deny(EligibilityReason.DOCUMENT_NOT_FOUND)
    if facts.active_approval_checksum is None:
        return _deny(EligibilityReason.NOT_APPROVED)
    if facts.is_archived:
        return _deny(EligibilityReason.ARCHIVED)
    if facts.confidentiality_classification != "standard":
        return _deny(EligibilityReason.NOT_STANDARD_CLASSIFICATION)
    if facts.payload_checksum is None or facts.payload_checksum != facts.active_approval_checksum:
        return _deny(EligibilityReason.CHECKSUM_MISMATCH)
    if not facts.extraction_found:
        return _deny(EligibilityReason.EXTRACTION_NOT_FOUND)
    if not facts.extraction_belongs_to_document:
        return _deny(EligibilityReason.EXTRACTION_NOT_FOR_DOCUMENT)
    if not facts.extraction_is_current:
        return _deny(EligibilityReason.EXTRACTION_NOT_CURRENT)
    if facts.extraction_status != "completed":
        return _deny(EligibilityReason.EXTRACTION_NOT_COMPLETED)
    return EligibilityDecision(True, EligibilityReason.ELIGIBLE)


class RetrievalScope(Protocol):
    """Decides whether a (document, extraction) pair may be embedded or
    retrieved. 10D.3 adds the SQL-predicate counterpart, tested for parity
    with `evaluate`."""

    @property
    def name(self) -> str: ...

    def evaluate(self, facts: EligibilityFacts) -> EligibilityDecision: ...


class PublicAllowlistScope:
    """The only scope: explicitly approved public documents. Takes no
    constructor arguments and reads nothing from a request."""

    @property
    def name(self) -> str:
        return "public_allowlist"

    def evaluate(self, facts: EligibilityFacts) -> EligibilityDecision:
        return evaluate_eligibility(facts)


PUBLIC_ALLOWLIST_SCOPE: RetrievalScope = PublicAllowlistScope()
