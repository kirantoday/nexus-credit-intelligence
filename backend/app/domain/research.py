"""Canonical domain objects for `research_note` / `research_note_version`
(PLAN.md 4.10; Milestone 10A — PLAN.md 24.12).

See `app.models.research`'s module docstring for the structured-sections-
instead-of-`body_markdown` design note and the `evidence_refs` convention.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.core.types import AccessClassification, Conviction, ThesisStatus


class EvidenceRef(BaseModel):
    """A pointer to an existing Nexus record a note cites as evidence —
    never a copy of that record's content."""

    model_config = ConfigDict(frozen=True)

    entity_table: str
    entity_id: UUID
    label: str | None = None


class ResearchNoteCreate(BaseModel):
    """Everything needed to create a `research_note` row; id/timestamps are
    server-generated."""

    model_config = ConfigDict(frozen=True)

    issuer_id: UUID
    security_id: UUID | None = None
    title: str
    thesis_status: ThesisStatus
    conviction: Conviction | None = None
    bull_case: str | None = None
    base_case: str | None = None
    bear_case: str | None = None
    catalysts: str | None = None
    risks: str | None = None
    invalidation_conditions: str | None = None
    evidence_refs: list[EvidenceRef] | None = None
    access_classification: AccessClassification = AccessClassification.STANDARD
    author_user_id: str | None = None
    is_demo: bool = False


class ResearchNoteFields(BaseModel):
    """The subset of `ResearchNote` fields that are both editable and
    snapshotted into `research_note_version` on a material edit — factored
    out so the service's "did anything material change" comparison and the
    version-snapshot construction share one field list."""

    model_config = ConfigDict(frozen=True)

    title: str
    thesis_status: ThesisStatus
    conviction: Conviction | None
    bull_case: str | None
    base_case: str | None
    bear_case: str | None
    catalysts: str | None
    risks: str | None
    invalidation_conditions: str | None
    evidence_refs: list[EvidenceRef] | None
    access_classification: AccessClassification


class ResearchNoteUpdate(BaseModel):
    """Partial update — unset fields leave the existing value unchanged."""

    model_config = ConfigDict(frozen=True)

    title: str | None = None
    thesis_status: ThesisStatus | None = None
    conviction: Conviction | None = None
    bull_case: str | None = None
    base_case: str | None = None
    bear_case: str | None = None
    catalysts: str | None = None
    risks: str | None = None
    invalidation_conditions: str | None = None
    evidence_refs: list[EvidenceRef] | None = None
    access_classification: AccessClassification | None = None
    edited_by: str | None = None


class ResearchNote(BaseModel):
    """A persisted `research_note` row."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    issuer_id: UUID
    security_id: UUID | None
    title: str
    thesis_status: ThesisStatus
    conviction: Conviction | None
    bull_case: str | None
    base_case: str | None
    bear_case: str | None
    catalysts: str | None
    risks: str | None
    invalidation_conditions: str | None
    evidence_refs: list[EvidenceRef] | None
    access_classification: AccessClassification
    author_user_id: str | None
    is_demo: bool
    current_version_number: int
    is_archived: bool
    archived_at: datetime | None
    archived_by: str | None
    created_at: datetime
    updated_at: datetime

    @property
    def fields(self) -> ResearchNoteFields:
        return ResearchNoteFields(
            title=self.title,
            thesis_status=self.thesis_status,
            conviction=self.conviction,
            bull_case=self.bull_case,
            base_case=self.base_case,
            bear_case=self.bear_case,
            catalysts=self.catalysts,
            risks=self.risks,
            invalidation_conditions=self.invalidation_conditions,
            evidence_refs=self.evidence_refs,
            access_classification=self.access_classification,
        )


class ResearchNoteVersionCreate(BaseModel):
    """Everything needed to create a `research_note_version` snapshot row."""

    model_config = ConfigDict(frozen=True)

    research_note_id: UUID
    version_number: int
    fields: ResearchNoteFields
    edited_by: str | None = None


class ResearchNoteVersion(BaseModel):
    """A persisted `research_note_version` row — a full, standalone
    snapshot, never a diff."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    research_note_id: UUID
    version_number: int
    fields: ResearchNoteFields
    edited_by: str | None
    edited_at: datetime
