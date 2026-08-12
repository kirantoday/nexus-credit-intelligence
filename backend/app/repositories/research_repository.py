"""Repository for `research_note` / `research_note_version` (PLAN.md 4.10;
Milestone 10A — PLAN.md 24.12).

Function-style, domain objects only, flush-not-commit — see
`provenance_repository.py`'s module docstring for this project's repository
conventions. Versioning and audit-event orchestration live in
`app.services.research_note_service`, not here: this module only persists
whatever the service tells it to.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.types import AccessClassification, Conviction, ThesisStatus
from app.domain.research import (
    EvidenceRef,
    ResearchNote,
    ResearchNoteCreate,
    ResearchNoteFields,
    ResearchNoteVersion,
    ResearchNoteVersionCreate,
)
from app.models.issuer import Issuer as IssuerModel
from app.models.research import ResearchNote as ResearchNoteModel
from app.models.research import ResearchNoteVersion as ResearchNoteVersionModel


def _evidence_refs_to_jsonb(refs: list[EvidenceRef] | None) -> list[dict[str, str]] | None:
    if refs is None:
        return None
    return [
        {"entity_table": r.entity_table, "entity_id": str(r.entity_id), "label": r.label or ""}
        for r in refs
    ]


def _evidence_refs_from_jsonb(raw: list[dict[str, str]] | None) -> list[EvidenceRef] | None:
    if raw is None:
        return None
    return [
        EvidenceRef(
            entity_table=r["entity_table"],
            entity_id=UUID(r["entity_id"]),
            label=r.get("label") or None,
        )
        for r in raw
    ]


def _note_to_domain(row: ResearchNoteModel) -> ResearchNote:
    return ResearchNote(
        id=row.id,
        issuer_id=row.issuer_id,
        security_id=row.security_id,
        title=row.title,
        thesis_status=ThesisStatus(row.thesis_status),
        conviction=Conviction(row.conviction) if row.conviction else None,
        bull_case=row.bull_case,
        base_case=row.base_case,
        bear_case=row.bear_case,
        catalysts=row.catalysts,
        risks=row.risks,
        invalidation_conditions=row.invalidation_conditions,
        evidence_refs=_evidence_refs_from_jsonb(row.evidence_refs),
        access_classification=AccessClassification(row.access_classification),
        author_user_id=row.author_user_id,
        is_demo=row.is_demo,
        current_version_number=row.current_version_number,
        is_archived=row.is_archived,
        archived_at=row.archived_at,
        archived_by=row.archived_by,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _version_to_domain(row: ResearchNoteVersionModel) -> ResearchNoteVersion:
    return ResearchNoteVersion(
        id=row.id,
        research_note_id=row.research_note_id,
        version_number=row.version_number,
        fields=ResearchNoteFields(
            title=row.title,
            thesis_status=ThesisStatus(row.thesis_status),
            conviction=Conviction(row.conviction) if row.conviction else None,
            bull_case=row.bull_case,
            base_case=row.base_case,
            bear_case=row.bear_case,
            catalysts=row.catalysts,
            risks=row.risks,
            invalidation_conditions=row.invalidation_conditions,
            evidence_refs=_evidence_refs_from_jsonb(row.evidence_refs),
            access_classification=AccessClassification(row.access_classification),
        ),
        edited_by=row.edited_by,
        edited_at=row.edited_at,
    )


def create_note(db: Session, data: ResearchNoteCreate) -> ResearchNote:
    row = ResearchNoteModel(
        issuer_id=data.issuer_id,
        security_id=data.security_id,
        title=data.title,
        thesis_status=data.thesis_status.value,
        conviction=data.conviction.value if data.conviction else None,
        bull_case=data.bull_case,
        base_case=data.base_case,
        bear_case=data.bear_case,
        catalysts=data.catalysts,
        risks=data.risks,
        invalidation_conditions=data.invalidation_conditions,
        evidence_refs=_evidence_refs_to_jsonb(data.evidence_refs),
        access_classification=data.access_classification.value,
        author_user_id=data.author_user_id,
        is_demo=data.is_demo,
    )
    db.add(row)
    db.flush()
    db.refresh(row)
    return _note_to_domain(row)


def get_note(db: Session, note_id: UUID) -> ResearchNote | None:
    row = db.get(ResearchNoteModel, note_id)
    return _note_to_domain(row) if row is not None else None


def list_notes_by_issuer(
    db: Session, issuer_id: UUID, *, include_archived: bool = False
) -> list[ResearchNote]:
    stmt = select(ResearchNoteModel).where(ResearchNoteModel.issuer_id == issuer_id)
    if not include_archived:
        stmt = stmt.where(ResearchNoteModel.is_archived.is_(False))
    stmt = stmt.order_by(ResearchNoteModel.updated_at.desc())
    rows = db.execute(stmt).scalars().all()
    return [_note_to_domain(row) for row in rows]


def list_notes(
    db: Session, *, issuer_id: UUID | None = None, include_archived: bool = False
) -> list[tuple[ResearchNote, str, str | None]]:
    """Cross-issuer (or, with `issuer_id`, single-issuer) note listing with
    joined issuer display fields — backs the Research Notes workspace page
    (PLAN.md row 9 slice, workspace-discoverability follow-up).

    Additive alongside `list_notes_by_issuer`: that function is unchanged
    and still backs `research_note_service.list_notes_for_issuer`
    (in turn used by `app.scripts.seed_demo_research_note` and unaffected
    by this addition). When `issuer_id` is supplied here, the filter/
    archive/ordering logic is identical to `list_notes_by_issuer`'s, so
    the issuer-scoped API response is unchanged except for the two new
    additive fields.
    """
    stmt = select(ResearchNoteModel, IssuerModel.legal_name, IssuerModel.ticker).join(
        IssuerModel, ResearchNoteModel.issuer_id == IssuerModel.id
    )
    if issuer_id is not None:
        stmt = stmt.where(ResearchNoteModel.issuer_id == issuer_id)
    if not include_archived:
        stmt = stmt.where(ResearchNoteModel.is_archived.is_(False))
    stmt = stmt.order_by(ResearchNoteModel.updated_at.desc())
    rows = db.execute(stmt).all()
    return [
        (_note_to_domain(note_row), legal_name, ticker) for note_row, legal_name, ticker in rows
    ]


def apply_note_fields(
    db: Session, note_id: UUID, fields: ResearchNoteFields, *, new_version_number: int
) -> ResearchNote | None:
    """Applies an edited field set to the live `research_note` row and bumps
    `current_version_number`. Caller (`research_note_service`) is
    responsible for having already written the pre-edit snapshot to
    `research_note_version`."""
    row = db.get(ResearchNoteModel, note_id)
    if row is None:
        return None
    row.title = fields.title
    row.thesis_status = fields.thesis_status.value
    row.conviction = fields.conviction.value if fields.conviction else None
    row.bull_case = fields.bull_case
    row.base_case = fields.base_case
    row.bear_case = fields.bear_case
    row.catalysts = fields.catalysts
    row.risks = fields.risks
    row.invalidation_conditions = fields.invalidation_conditions
    row.evidence_refs = _evidence_refs_to_jsonb(fields.evidence_refs)
    row.access_classification = fields.access_classification.value
    row.current_version_number = new_version_number
    row.updated_at = datetime.now(UTC)
    db.flush()
    db.refresh(row)
    return _note_to_domain(row)


def archive_note(db: Session, note_id: UUID, *, archived_by: str | None) -> ResearchNote | None:
    row = db.get(ResearchNoteModel, note_id)
    if row is None or row.is_archived:
        return None
    row.is_archived = True
    row.archived_at = datetime.now(UTC)
    row.archived_by = archived_by
    db.flush()
    db.refresh(row)
    return _note_to_domain(row)


def create_version(db: Session, data: ResearchNoteVersionCreate) -> ResearchNoteVersion:
    row = ResearchNoteVersionModel(
        research_note_id=data.research_note_id,
        version_number=data.version_number,
        title=data.fields.title,
        thesis_status=data.fields.thesis_status.value,
        conviction=data.fields.conviction.value if data.fields.conviction else None,
        bull_case=data.fields.bull_case,
        base_case=data.fields.base_case,
        bear_case=data.fields.bear_case,
        catalysts=data.fields.catalysts,
        risks=data.fields.risks,
        invalidation_conditions=data.fields.invalidation_conditions,
        evidence_refs=_evidence_refs_to_jsonb(data.fields.evidence_refs),
        access_classification=data.fields.access_classification.value,
        edited_by=data.edited_by,
    )
    db.add(row)
    db.flush()
    db.refresh(row)
    return _version_to_domain(row)


def list_versions(db: Session, note_id: UUID) -> list[ResearchNoteVersion]:
    stmt = (
        select(ResearchNoteVersionModel)
        .where(ResearchNoteVersionModel.research_note_id == note_id)
        .order_by(ResearchNoteVersionModel.version_number.desc())
    )
    rows = db.execute(stmt).scalars().all()
    return [_version_to_domain(row) for row in rows]


def get_version(db: Session, note_id: UUID, version_number: int) -> ResearchNoteVersion | None:
    stmt = select(ResearchNoteVersionModel).where(
        ResearchNoteVersionModel.research_note_id == note_id,
        ResearchNoteVersionModel.version_number == version_number,
    )
    row = db.execute(stmt).scalars().first()
    return _version_to_domain(row) if row is not None else None
