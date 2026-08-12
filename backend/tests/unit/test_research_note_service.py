"""Unit tests for `app/services/research_note_service.py`'s pure logic
(PLAN.md 4.10, 24.12; Milestone 10A).

`_merge_fields` is the only pure function in this service — everything else
needs a database (covered by
`tests/integration/test_research_note_service.py`). Covers: `None` means
"leave unchanged," `""`/`[]` are valid explicit-clear values distinguishable
from `None`, and unrelated fields are untouched by a partial update.
"""

from __future__ import annotations

from app.core.types import AccessClassification, Conviction, ThesisStatus
from app.domain.research import EvidenceRef, ResearchNoteFields, ResearchNoteUpdate
from app.services.research_note_service import _merge_fields

_BASE_FIELDS = ResearchNoteFields(
    title="Trinseo PLC — Covenant Stress Thesis",
    thesis_status=ThesisStatus.ACTIVE,
    conviction=Conviction.MEDIUM,
    bull_case="Refinancing completes on favorable terms.",
    base_case="Covenant waiver secured, liquidity stabilizes.",
    bear_case="Chapter 11 filing within two quarters.",
    catalysts="Q3 covenant compliance certificate.",
    risks="Further EBITDA deterioration.",
    invalidation_conditions="Going concern qualification issued.",
    evidence_refs=None,
    access_classification=AccessClassification.STANDARD,
)


def test_merge_fields_all_none_leaves_everything_unchanged() -> None:
    update = ResearchNoteUpdate()
    merged = _merge_fields(_BASE_FIELDS, update)
    assert merged == _BASE_FIELDS


def test_merge_fields_updates_only_specified_field() -> None:
    update = ResearchNoteUpdate(conviction=Conviction.HIGH)
    merged = _merge_fields(_BASE_FIELDS, update)
    assert merged.conviction == Conviction.HIGH
    assert merged.title == _BASE_FIELDS.title
    assert merged.bull_case == _BASE_FIELDS.bull_case


def test_merge_fields_empty_string_explicitly_clears_text_field() -> None:
    update = ResearchNoteUpdate(catalysts="")
    merged = _merge_fields(_BASE_FIELDS, update)
    assert merged.catalysts == ""
    assert merged.catalysts != _BASE_FIELDS.catalysts


def test_merge_fields_empty_list_explicitly_clears_evidence_refs() -> None:
    with_refs = _BASE_FIELDS.model_copy(
        update={
            "evidence_refs": [
                EvidenceRef(
                    entity_table="sec_filing", entity_id="00000000-0000-0000-0000-000000000001"
                )
            ]
        }
    )
    update = ResearchNoteUpdate(evidence_refs=[])
    merged = _merge_fields(with_refs, update)
    assert merged.evidence_refs == []


def test_merge_fields_thesis_status_transition_to_invalidated() -> None:
    update = ResearchNoteUpdate(
        thesis_status=ThesisStatus.INVALIDATED,
        bear_case="Chapter 11 petition filed; base case materialized as bear case.",
    )
    merged = _merge_fields(_BASE_FIELDS, update)
    assert merged.thesis_status == ThesisStatus.INVALIDATED
    assert merged.bear_case != _BASE_FIELDS.bear_case
    assert merged.bull_case == _BASE_FIELDS.bull_case


def test_merge_fields_identical_update_produces_equal_fields() -> None:
    """No-op detection in `update_note` relies on `==` between
    `ResearchNoteFields` instances — confirm equal content compares equal
    even when constructed through two different paths (base vs. merged)."""
    update = ResearchNoteUpdate(title=_BASE_FIELDS.title)
    merged = _merge_fields(_BASE_FIELDS, update)
    assert merged == _BASE_FIELDS
