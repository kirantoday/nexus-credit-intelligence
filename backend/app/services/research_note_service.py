"""Research Note create/edit/archive orchestration + versioning + audit
trail (PLAN.md 4.10, 4.12; Milestone 10A — PLAN.md 24.12).

Versioning model: every save — the initial create and every subsequent
material edit — produces one immutable, standalone `research_note_version`
snapshot of the *resulting* state, numbered sequentially starting at 1 (so
"Version 1 -> Version 2 -> Version 3" in the UI always means exactly what it
says: three real, independently-renderable states, the last of which is also
the note's current live content). Within one edit's transaction, the version
row is written before the live `research_note` row is updated (literal
ordering, satisfying PLAN.md 4.10/section 11's "snapshot before applying the
update") — so a mid-transaction failure can never leave an edit applied
without a corresponding snapshot of the state it produced.

An edit is "material" — and thus version-worthy — exactly when it changes
any of the fields in `ResearchNoteFields` (the full set of thesis content:
title, thesis status, conviction, bull/base/bear case, catalysts, risks,
invalidation conditions, evidence references, access classification). A
save that changes nothing is a no-op: no new version, no audit event.

Research-note versions and audit events serve different, deliberately
uncollapsed purposes (per the user's explicit instruction): a version is the
reconstructable historical *content* of the note; an audit event is the
who/what/when *fact that a write happened*, independent of whether the UI
ever renders that write's full content.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.types import AuditEventType
from app.domain.audit import AuditEvent, AuditEventCreate
from app.domain.research import (
    ResearchNote,
    ResearchNoteCreate,
    ResearchNoteFields,
    ResearchNoteUpdate,
    ResearchNoteVersion,
    ResearchNoteVersionCreate,
)
from app.repositories import audit_repository, research_repository

_ENTITY_TABLE = "research_note"


class ResearchNoteArchivedError(Exception):
    """Raised when an edit is attempted against an archived note. Archived
    notes are read-only — their history stands as the final record."""

    def __init__(self, note_id: UUID) -> None:
        self.note_id = note_id
        super().__init__(f"research_note {note_id} is archived and cannot be edited")


def _merge_fields(existing: ResearchNoteFields, update: ResearchNoteUpdate) -> ResearchNoteFields:
    """`None` on an updatable field means "leave unchanged"; text fields can
    be explicitly cleared with `""`, list fields with `[]` — both are valid,
    distinguishable non-`None` values. `conviction` cannot currently be
    explicitly unset back to `None` once set (a `None` there always reads as
    "no change"); a known, minor limitation, not a full unset-sentinel
    scheme, since no workflow in this milestone needs it."""
    return ResearchNoteFields(
        title=update.title if update.title is not None else existing.title,
        thesis_status=(
            update.thesis_status if update.thesis_status is not None else existing.thesis_status
        ),
        conviction=update.conviction if update.conviction is not None else existing.conviction,
        bull_case=update.bull_case if update.bull_case is not None else existing.bull_case,
        base_case=update.base_case if update.base_case is not None else existing.base_case,
        bear_case=update.bear_case if update.bear_case is not None else existing.bear_case,
        catalysts=update.catalysts if update.catalysts is not None else existing.catalysts,
        risks=update.risks if update.risks is not None else existing.risks,
        invalidation_conditions=(
            update.invalidation_conditions
            if update.invalidation_conditions is not None
            else existing.invalidation_conditions
        ),
        evidence_refs=(
            update.evidence_refs if update.evidence_refs is not None else existing.evidence_refs
        ),
        access_classification=(
            update.access_classification
            if update.access_classification is not None
            else existing.access_classification
        ),
    )


def create_note(db: Session, data: ResearchNoteCreate) -> ResearchNote:
    note = research_repository.create_note(db, data)
    research_repository.create_version(
        db,
        ResearchNoteVersionCreate(
            research_note_id=note.id,
            version_number=1,
            fields=note.fields,
            edited_by=data.author_user_id,
        ),
    )
    audit_repository.create_event(
        db,
        AuditEventCreate(
            user_id=data.author_user_id,
            event_type=AuditEventType.RESEARCH_NOTE_CREATED.value,
            entity_table=_ENTITY_TABLE,
            entity_id=note.id,
            before_state=None,
            after_state=note.fields.model_dump(mode="json"),
        ),
    )
    return note


def get_note(db: Session, note_id: UUID) -> ResearchNote | None:
    return research_repository.get_note(db, note_id)


def list_notes_for_issuer(
    db: Session, issuer_id: UUID, *, include_archived: bool = False
) -> list[ResearchNote]:
    return research_repository.list_notes_by_issuer(
        db, issuer_id, include_archived=include_archived
    )


def update_note(db: Session, note_id: UUID, data: ResearchNoteUpdate) -> ResearchNote | None:
    """Returns `None` if the note doesn't exist. Raises
    `ResearchNoteArchivedError` if it exists but is archived. Returns the
    unchanged note (no version, no audit event) if the merged fields are
    identical to what's already live."""
    existing = research_repository.get_note(db, note_id)
    if existing is None:
        return None
    if existing.is_archived:
        raise ResearchNoteArchivedError(note_id)

    merged = _merge_fields(existing.fields, data)
    if merged == existing.fields:
        return existing

    new_version_number = existing.current_version_number + 1
    research_repository.create_version(
        db,
        ResearchNoteVersionCreate(
            research_note_id=note_id,
            version_number=new_version_number,
            fields=merged,
            edited_by=data.edited_by,
        ),
    )
    updated = research_repository.apply_note_fields(
        db, note_id, merged, new_version_number=new_version_number
    )
    audit_repository.create_event(
        db,
        AuditEventCreate(
            user_id=data.edited_by,
            event_type=AuditEventType.RESEARCH_NOTE_UPDATED.value,
            entity_table=_ENTITY_TABLE,
            entity_id=note_id,
            before_state=existing.fields.model_dump(mode="json"),
            after_state=merged.model_dump(mode="json"),
        ),
    )
    return updated


def archive_note(db: Session, note_id: UUID, *, archived_by: str | None) -> ResearchNote | None:
    """Idempotent no-op (returns the already-archived note) if called
    twice — archiving is the only "removal" path for a note (no hard
    delete): the point of an audit trail is defeated if the audited entity
    itself can vanish along with its version history."""
    existing = research_repository.get_note(db, note_id)
    if existing is None:
        return None
    if existing.is_archived:
        return existing

    archived = research_repository.archive_note(db, note_id, archived_by=archived_by)
    audit_repository.create_event(
        db,
        AuditEventCreate(
            user_id=archived_by,
            event_type=AuditEventType.RESEARCH_NOTE_ARCHIVED.value,
            entity_table=_ENTITY_TABLE,
            entity_id=note_id,
            before_state={"is_archived": False},
            after_state={"is_archived": True},
        ),
    )
    return archived


def list_versions(db: Session, note_id: UUID) -> list[ResearchNoteVersion]:
    return research_repository.list_versions(db, note_id)


def get_version(db: Session, note_id: UUID, version_number: int) -> ResearchNoteVersion | None:
    return research_repository.get_version(db, note_id, version_number)


def list_audit_events(db: Session, note_id: UUID) -> list[AuditEvent]:
    return audit_repository.list_events_for_entity(db, _ENTITY_TABLE, note_id)
