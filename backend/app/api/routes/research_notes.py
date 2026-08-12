"""Research Notes API routes (PLAN.md 4.10, 4.12, section 11; Milestone
10A — PLAN.md 24.12).

Thin per PLAN.md section 3: delegates to `research_note_service`, no
business logic or ORM access here.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.research import (
    ArchiveNoteRequest,
    AuditEventListResponse,
    AuditEventResponse,
    ResearchNoteCreateRequest,
    ResearchNoteListResponse,
    ResearchNoteResponse,
    ResearchNoteUpdateRequest,
    ResearchNoteVersionListResponse,
    ResearchNoteVersionResponse,
)
from app.services import research_note_service
from app.services.research_note_service import ResearchNoteArchivedError

router = APIRouter(prefix="/api/research-notes", tags=["research-notes"])


@router.get("", response_model=ResearchNoteListResponse)
def list_notes(
    db: Annotated[Session, Depends(get_db)],
    issuer_id: UUID,
    include_archived: bool = False,
) -> ResearchNoteListResponse:
    notes = research_note_service.list_notes_for_issuer(
        db, issuer_id, include_archived=include_archived
    )
    return ResearchNoteListResponse(notes=[ResearchNoteResponse.from_domain(n) for n in notes])


@router.post("", response_model=ResearchNoteResponse, status_code=status.HTTP_201_CREATED)
def create_note(
    body: ResearchNoteCreateRequest, db: Annotated[Session, Depends(get_db)]
) -> ResearchNoteResponse:
    note = research_note_service.create_note(db, body.to_domain())
    return ResearchNoteResponse.from_domain(note)


@router.get("/{note_id}", response_model=ResearchNoteResponse)
def get_note(note_id: UUID, db: Annotated[Session, Depends(get_db)]) -> ResearchNoteResponse:
    note = research_note_service.get_note(db, note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Research note not found")
    return ResearchNoteResponse.from_domain(note)


@router.patch("/{note_id}", response_model=ResearchNoteResponse)
def update_note(
    note_id: UUID, body: ResearchNoteUpdateRequest, db: Annotated[Session, Depends(get_db)]
) -> ResearchNoteResponse:
    try:
        note = research_note_service.update_note(db, note_id, body.to_domain())
    except ResearchNoteArchivedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Archived notes cannot be edited"
        ) from exc
    if note is None:
        raise HTTPException(status_code=404, detail="Research note not found")
    return ResearchNoteResponse.from_domain(note)


@router.post("/{note_id}/archive", response_model=ResearchNoteResponse)
def archive_note(
    note_id: UUID, body: ArchiveNoteRequest, db: Annotated[Session, Depends(get_db)]
) -> ResearchNoteResponse:
    note = research_note_service.archive_note(db, note_id, archived_by=body.archived_by)
    if note is None:
        raise HTTPException(status_code=404, detail="Research note not found")
    return ResearchNoteResponse.from_domain(note)


@router.get("/{note_id}/versions", response_model=ResearchNoteVersionListResponse)
def list_versions(
    note_id: UUID, db: Annotated[Session, Depends(get_db)]
) -> ResearchNoteVersionListResponse:
    if research_note_service.get_note(db, note_id) is None:
        raise HTTPException(status_code=404, detail="Research note not found")
    versions = research_note_service.list_versions(db, note_id)
    return ResearchNoteVersionListResponse(
        versions=[ResearchNoteVersionResponse.from_domain(v) for v in versions]
    )


@router.get("/{note_id}/versions/{version_number}", response_model=ResearchNoteVersionResponse)
def get_version(
    note_id: UUID, version_number: int, db: Annotated[Session, Depends(get_db)]
) -> ResearchNoteVersionResponse:
    version = research_note_service.get_version(db, note_id, version_number)
    if version is None:
        raise HTTPException(status_code=404, detail="Research note version not found")
    return ResearchNoteVersionResponse.from_domain(version)


@router.get("/{note_id}/audit-events", response_model=AuditEventListResponse)
def list_audit_events(
    note_id: UUID, db: Annotated[Session, Depends(get_db)]
) -> AuditEventListResponse:
    if research_note_service.get_note(db, note_id) is None:
        raise HTTPException(status_code=404, detail="Research note not found")
    events = research_note_service.list_audit_events(db, note_id)
    return AuditEventListResponse(events=[AuditEventResponse.from_domain(e) for e in events])
