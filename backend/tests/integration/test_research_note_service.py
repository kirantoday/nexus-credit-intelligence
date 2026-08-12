"""Integration tests for `app/services/research_note_service.py` (PLAN.md
4.10, 4.12, 24.12; Milestone 10A) against the live shared `nexus` schema.

Covers: create writes note + version 1 + a `research_note_created` audit
event; a material edit snapshots a new version and a
`research_note_updated` audit event with correct before/after state; a
no-op edit (merged fields identical to current) writes neither; editing an
archived note raises `ResearchNoteArchivedError`; archiving is idempotent
and writes exactly one `research_note_archived` audit event; issuer listing
respects `include_archived`; version history and audit-event history are
both retrievable and correctly ordered.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.core.types import AccessClassification, Conviction, ThesisStatus
from app.domain.issuer import Issuer, IssuerCreate
from app.domain.research import ResearchNoteCreate, ResearchNoteUpdate
from app.repositories import issuer_repository, provenance_repository
from app.services import research_note_service
from app.services.research_note_service import ResearchNoteArchivedError
from tests.integration.conftest import reported_public_provenance


def _seed_issuer(
    db: Session, *, legal_name: str = "Trinseo PLC (Test)", ticker: str | None = None
) -> Issuer:
    provenance = provenance_repository.create_provenance(db, reported_public_provenance())
    return issuer_repository.create_issuer(
        db, IssuerCreate(legal_name=legal_name, ticker=ticker, provenance_id=provenance.id)
    )


def _create_request(issuer_id: object, **overrides: object) -> ResearchNoteCreate:
    defaults: dict[str, object] = dict(
        issuer_id=issuer_id,
        title="Covenant Stress Thesis",
        thesis_status=ThesisStatus.ACTIVE,
        conviction=Conviction.MEDIUM,
        bull_case="Refinancing completes on favorable terms.",
        base_case="Covenant waiver secured, liquidity stabilizes.",
        bear_case="Chapter 11 filing within two quarters.",
        catalysts="Q3 covenant compliance certificate.",
        risks="Further EBITDA deterioration.",
        invalidation_conditions="Going concern qualification issued.",
        access_classification=AccessClassification.STANDARD,
        author_user_id="demo-analyst",
    )
    defaults.update(overrides)
    return ResearchNoteCreate(**defaults)  # type: ignore[arg-type]


def test_create_note_writes_version_one_and_audit_event(db_session: Session) -> None:
    issuer = _seed_issuer(db_session)
    note = research_note_service.create_note(db_session, _create_request(issuer.id))

    assert note.current_version_number == 1
    assert note.is_archived is False

    versions = research_note_service.list_versions(db_session, note.id)
    assert len(versions) == 1
    assert versions[0].version_number == 1
    assert versions[0].fields.title == note.title

    events = research_note_service.list_audit_events(db_session, note.id)
    assert len(events) == 1
    assert events[0].event_type == "research_note_created"
    assert events[0].before_state is None
    assert events[0].after_state is not None
    assert events[0].user_id == "demo-analyst"


def test_material_update_creates_new_version_and_audit_event(db_session: Session) -> None:
    issuer = _seed_issuer(db_session)
    note = research_note_service.create_note(db_session, _create_request(issuer.id))

    updated = research_note_service.update_note(
        db_session,
        note.id,
        ResearchNoteUpdate(
            thesis_status=ThesisStatus.INVALIDATED,
            bear_case="Chapter 11 petition filed; the bear case has materialized.",
            edited_by="demo-analyst-2",
        ),
    )
    assert updated is not None
    assert updated.current_version_number == 2
    assert updated.thesis_status == ThesisStatus.INVALIDATED

    versions = research_note_service.list_versions(db_session, note.id)
    assert [v.version_number for v in versions] == [2, 1]
    assert versions[0].fields.thesis_status == ThesisStatus.INVALIDATED
    # Version 1 renders standalone with its original content, untouched.
    assert versions[1].fields.thesis_status == ThesisStatus.ACTIVE

    events = research_note_service.list_audit_events(db_session, note.id)
    assert [e.event_type for e in events] == ["research_note_updated", "research_note_created"]
    update_event = events[0]
    assert update_event.before_state is not None
    assert update_event.after_state is not None
    assert update_event.before_state["thesis_status"] == "active"
    assert update_event.after_state["thesis_status"] == "invalidated"
    assert update_event.user_id == "demo-analyst-2"


def test_noop_update_writes_no_version_or_audit_event(db_session: Session) -> None:
    issuer = _seed_issuer(db_session)
    note = research_note_service.create_note(db_session, _create_request(issuer.id))

    result = research_note_service.update_note(
        db_session, note.id, ResearchNoteUpdate(title=note.title)
    )
    assert result is not None
    assert result.current_version_number == 1

    assert len(research_note_service.list_versions(db_session, note.id)) == 1
    assert len(research_note_service.list_audit_events(db_session, note.id)) == 1


def test_update_nonexistent_note_returns_none(db_session: Session) -> None:
    result = research_note_service.update_note(
        db_session, uuid4(), ResearchNoteUpdate(title="Anything")
    )
    assert result is None


def test_editing_archived_note_raises(db_session: Session) -> None:
    issuer = _seed_issuer(db_session)
    note = research_note_service.create_note(db_session, _create_request(issuer.id))
    research_note_service.archive_note(db_session, note.id, archived_by="demo-admin")

    with pytest.raises(ResearchNoteArchivedError):
        research_note_service.update_note(db_session, note.id, ResearchNoteUpdate(title="New"))


def test_archive_is_idempotent_and_writes_exactly_one_audit_event(db_session: Session) -> None:
    issuer = _seed_issuer(db_session)
    note = research_note_service.create_note(db_session, _create_request(issuer.id))

    first = research_note_service.archive_note(db_session, note.id, archived_by="demo-admin")
    second = research_note_service.archive_note(db_session, note.id, archived_by="demo-admin")

    assert first is not None
    assert first.is_archived is True
    assert first.archived_at is not None
    assert second is not None
    assert second.is_archived is True

    events = research_note_service.list_audit_events(db_session, note.id)
    archive_events = [e for e in events if e.event_type == "research_note_archived"]
    assert len(archive_events) == 1


def test_archive_nonexistent_note_returns_none(db_session: Session) -> None:
    assert research_note_service.archive_note(db_session, uuid4(), archived_by=None) is None


def test_list_notes_for_issuer_respects_include_archived(db_session: Session) -> None:
    issuer = _seed_issuer(db_session)
    live = research_note_service.create_note(
        db_session, _create_request(issuer.id, title="Live Note")
    )
    archived = research_note_service.create_note(
        db_session, _create_request(issuer.id, title="Archived Note")
    )
    research_note_service.archive_note(db_session, archived.id, archived_by="demo-admin")

    active_only = research_note_service.list_notes_for_issuer(db_session, issuer.id)
    assert {n.id for n in active_only} == {live.id}

    all_notes = research_note_service.list_notes_for_issuer(
        db_session, issuer.id, include_archived=True
    )
    assert {n.id for n in all_notes} == {live.id, archived.id}


def test_list_notes_issuer_scoped_matches_list_notes_for_issuer(db_session: Session) -> None:
    """`list_notes(issuer_id=...)` must return exactly the same notes, in
    the same order, as the original `list_notes_for_issuer` — the
    Research Notes workspace's cross-issuer capability must not change
    issuer-scoped behavior at all."""
    issuer = _seed_issuer(db_session)
    other_issuer = _seed_issuer(db_session, legal_name="Unrelated Issuer (Test)")
    note_a = research_note_service.create_note(
        db_session, _create_request(issuer.id, title="Note A")
    )
    note_b = research_note_service.create_note(
        db_session, _create_request(issuer.id, title="Note B")
    )
    research_note_service.create_note(
        db_session, _create_request(other_issuer.id, title="Other Issuer's Note")
    )

    scoped_original = research_note_service.list_notes_for_issuer(db_session, issuer.id)
    scoped_new = research_note_service.list_notes(db_session, issuer_id=issuer.id)

    assert [n.id for n in scoped_original] == [n.id for n, _legal_name, _ticker in scoped_new]
    assert {n.id for n, _, _ in scoped_new} == {note_a.id, note_b.id}


def test_list_notes_cross_issuer_returns_notes_from_every_issuer(db_session: Session) -> None:
    issuer_1 = _seed_issuer(db_session, legal_name="Cross-Issuer Test Corp A")
    issuer_2 = _seed_issuer(db_session, legal_name="Cross-Issuer Test Corp B")
    note_1 = research_note_service.create_note(
        db_session, _create_request(issuer_1.id, title="Note on Issuer A")
    )
    note_2 = research_note_service.create_note(
        db_session, _create_request(issuer_2.id, title="Note on Issuer B")
    )

    all_notes = research_note_service.list_notes(db_session)
    ids = {n.id for n, _legal_name, _ticker in all_notes}

    assert note_1.id in ids
    assert note_2.id in ids


def test_list_notes_cross_issuer_respects_include_archived(db_session: Session) -> None:
    issuer = _seed_issuer(db_session, legal_name="Archive Filter Test Corp")
    live = research_note_service.create_note(
        db_session, _create_request(issuer.id, title="Live Cross-Issuer Note")
    )
    archived = research_note_service.create_note(
        db_session, _create_request(issuer.id, title="Archived Cross-Issuer Note")
    )
    research_note_service.archive_note(db_session, archived.id, archived_by="demo-admin")

    active_only_ids = {n.id for n, _, _ in research_note_service.list_notes(db_session)}
    assert live.id in active_only_ids
    assert archived.id not in active_only_ids

    all_ids = {
        n.id for n, _, _ in research_note_service.list_notes(db_session, include_archived=True)
    }
    assert live.id in all_ids
    assert archived.id in all_ids


def test_list_notes_includes_issuer_display_fields(db_session: Session) -> None:
    issuer_with_ticker = _seed_issuer(db_session, legal_name="Ticker Corp", ticker="TICK")
    issuer_without_ticker = _seed_issuer(db_session, legal_name="No Ticker Corp", ticker=None)
    note_with_ticker = research_note_service.create_note(
        db_session, _create_request(issuer_with_ticker.id, title="Has Ticker")
    )
    note_without_ticker = research_note_service.create_note(
        db_session, _create_request(issuer_without_ticker.id, title="No Ticker")
    )

    all_notes = research_note_service.list_notes(db_session)
    by_id = {n.id: (legal_name, ticker) for n, legal_name, ticker in all_notes}

    assert by_id[note_with_ticker.id] == ("Ticker Corp", "TICK")
    assert by_id[note_without_ticker.id] == ("No Ticker Corp", None)


def test_get_version_fetches_specific_snapshot(db_session: Session) -> None:
    issuer = _seed_issuer(db_session)
    note = research_note_service.create_note(db_session, _create_request(issuer.id))
    research_note_service.update_note(
        db_session, note.id, ResearchNoteUpdate(conviction=Conviction.HIGH, edited_by="analyst")
    )

    v1 = research_note_service.get_version(db_session, note.id, 1)
    v2 = research_note_service.get_version(db_session, note.id, 2)
    missing = research_note_service.get_version(db_session, note.id, 99)

    assert v1 is not None and v1.fields.conviction == Conviction.MEDIUM
    assert v2 is not None and v2.fields.conviction == Conviction.HIGH
    assert missing is None


def test_demo_note_flag_is_persisted(db_session: Session) -> None:
    issuer = _seed_issuer(db_session)
    note = research_note_service.create_note(
        db_session,
        _create_request(issuer.id, is_demo=True, title="Demo Research Note: Trinseo PLC"),
    )
    assert note.is_demo is True
    fetched = research_note_service.get_note(db_session, note.id)
    assert fetched is not None
    assert fetched.is_demo is True
