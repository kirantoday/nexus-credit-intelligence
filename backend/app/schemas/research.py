"""Request/response schemas for the Research Notes API (PLAN.md 4.10, 4.12;
Milestone 10A — PLAN.md 24.12).

Kept as its own layer, structurally similar to but independent of
`app.domain.research`/`app.domain.audit` — per PLAN.md section 3, routes
depend on schemas, not domain objects directly, so a domain-layer change
doesn't silently change the wire contract.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.types import AccessClassification, Conviction, ThesisStatus
from app.domain.audit import AuditEvent
from app.domain.research import (
    EvidenceRef,
    ResearchNote,
    ResearchNoteCreate,
    ResearchNoteUpdate,
    ResearchNoteVersion,
)


class EvidenceRefSchema(BaseModel):
    model_config = ConfigDict(frozen=True)

    entity_table: str
    entity_id: UUID
    label: str | None = None

    def to_domain(self) -> EvidenceRef:
        return EvidenceRef(
            entity_table=self.entity_table, entity_id=self.entity_id, label=self.label
        )

    @staticmethod
    def from_domain(ref: EvidenceRef) -> EvidenceRefSchema:
        return EvidenceRefSchema(
            entity_table=ref.entity_table, entity_id=ref.entity_id, label=ref.label
        )


class ResearchNoteCreateRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    issuer_id: UUID
    security_id: UUID | None = None
    title: str = Field(min_length=1, max_length=300)
    thesis_status: ThesisStatus = ThesisStatus.DRAFT
    conviction: Conviction | None = None
    bull_case: str | None = None
    base_case: str | None = None
    bear_case: str | None = None
    catalysts: str | None = None
    risks: str | None = None
    invalidation_conditions: str | None = None
    evidence_refs: list[EvidenceRefSchema] | None = None
    access_classification: AccessClassification = AccessClassification.STANDARD
    author_user_id: str | None = None
    is_demo: bool = False

    def to_domain(self) -> ResearchNoteCreate:
        return ResearchNoteCreate(
            issuer_id=self.issuer_id,
            security_id=self.security_id,
            title=self.title,
            thesis_status=self.thesis_status,
            conviction=self.conviction,
            bull_case=self.bull_case,
            base_case=self.base_case,
            bear_case=self.bear_case,
            catalysts=self.catalysts,
            risks=self.risks,
            invalidation_conditions=self.invalidation_conditions,
            evidence_refs=(
                [r.to_domain() for r in self.evidence_refs]
                if self.evidence_refs is not None
                else None
            ),
            access_classification=self.access_classification,
            author_user_id=self.author_user_id,
            is_demo=self.is_demo,
        )


class ResearchNoteUpdateRequest(BaseModel):
    """All fields optional — `None` means "leave unchanged" (see
    `research_note_service._merge_fields`)."""

    model_config = ConfigDict(frozen=True)

    title: str | None = Field(default=None, min_length=1, max_length=300)
    thesis_status: ThesisStatus | None = None
    conviction: Conviction | None = None
    bull_case: str | None = None
    base_case: str | None = None
    bear_case: str | None = None
    catalysts: str | None = None
    risks: str | None = None
    invalidation_conditions: str | None = None
    evidence_refs: list[EvidenceRefSchema] | None = None
    access_classification: AccessClassification | None = None
    edited_by: str | None = None

    def to_domain(self) -> ResearchNoteUpdate:
        return ResearchNoteUpdate(
            title=self.title,
            thesis_status=self.thesis_status,
            conviction=self.conviction,
            bull_case=self.bull_case,
            base_case=self.base_case,
            bear_case=self.bear_case,
            catalysts=self.catalysts,
            risks=self.risks,
            invalidation_conditions=self.invalidation_conditions,
            evidence_refs=(
                [r.to_domain() for r in self.evidence_refs]
                if self.evidence_refs is not None
                else None
            ),
            access_classification=self.access_classification,
            edited_by=self.edited_by,
        )


class ArchiveNoteRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    archived_by: str | None = None


class ResearchNoteResponse(BaseModel):
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
    evidence_refs: list[EvidenceRefSchema] | None
    access_classification: AccessClassification
    author_user_id: str | None
    is_demo: bool
    current_version_number: int
    is_archived: bool
    archived_at: datetime | None
    archived_by: str | None
    created_at: datetime
    updated_at: datetime

    @staticmethod
    def from_domain(note: ResearchNote) -> ResearchNoteResponse:
        return ResearchNoteResponse(
            id=note.id,
            issuer_id=note.issuer_id,
            security_id=note.security_id,
            title=note.title,
            thesis_status=note.thesis_status,
            conviction=note.conviction,
            bull_case=note.bull_case,
            base_case=note.base_case,
            bear_case=note.bear_case,
            catalysts=note.catalysts,
            risks=note.risks,
            invalidation_conditions=note.invalidation_conditions,
            evidence_refs=(
                [EvidenceRefSchema.from_domain(r) for r in note.evidence_refs]
                if note.evidence_refs is not None
                else None
            ),
            access_classification=note.access_classification,
            author_user_id=note.author_user_id,
            is_demo=note.is_demo,
            current_version_number=note.current_version_number,
            is_archived=note.is_archived,
            archived_at=note.archived_at,
            archived_by=note.archived_by,
            created_at=note.created_at,
            updated_at=note.updated_at,
        )


class ResearchNoteListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    notes: list[ResearchNoteResponse]


class ResearchNoteVersionResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    research_note_id: UUID
    version_number: int
    title: str
    thesis_status: ThesisStatus
    conviction: Conviction | None
    bull_case: str | None
    base_case: str | None
    bear_case: str | None
    catalysts: str | None
    risks: str | None
    invalidation_conditions: str | None
    evidence_refs: list[EvidenceRefSchema] | None
    access_classification: AccessClassification
    edited_by: str | None
    edited_at: datetime

    @staticmethod
    def from_domain(version: ResearchNoteVersion) -> ResearchNoteVersionResponse:
        f = version.fields
        return ResearchNoteVersionResponse(
            id=version.id,
            research_note_id=version.research_note_id,
            version_number=version.version_number,
            title=f.title,
            thesis_status=f.thesis_status,
            conviction=f.conviction,
            bull_case=f.bull_case,
            base_case=f.base_case,
            bear_case=f.bear_case,
            catalysts=f.catalysts,
            risks=f.risks,
            invalidation_conditions=f.invalidation_conditions,
            evidence_refs=(
                [EvidenceRefSchema.from_domain(r) for r in f.evidence_refs]
                if f.evidence_refs is not None
                else None
            ),
            access_classification=f.access_classification,
            edited_by=version.edited_by,
            edited_at=version.edited_at,
        )


class ResearchNoteVersionListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    versions: list[ResearchNoteVersionResponse]


class AuditEventResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    user_id: str | None
    event_type: str
    entity_table: str
    entity_id: UUID | None
    before_state: dict[str, object] | None
    after_state: dict[str, object] | None
    occurred_at: datetime

    @staticmethod
    def from_domain(event: AuditEvent) -> AuditEventResponse:
        return AuditEventResponse(
            id=event.id,
            user_id=event.user_id,
            event_type=event.event_type,
            entity_table=event.entity_table,
            entity_id=event.entity_id,
            before_state=event.before_state,
            after_state=event.after_state,
            occurred_at=event.occurred_at,
        )


class AuditEventListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    events: list[AuditEventResponse]
