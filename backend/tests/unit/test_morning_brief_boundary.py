"""Unit tests for `app/services/morning_brief_service.py`'s pure boundary
logic (PLAN.md Milestone 7.5.2 correction) — no I/O, no database.

Covers `_previous_business_day_morning_boundary` (the first-ever-brief
fallback) and `_should_record_new_view` (the idempotent-refresh gap
predicate behind `record_brief_view`). Integration-level scenarios (a real
`morning_brief_view` row driving `get_morning_brief`, universe-membership
changes, new-vs-historical partitioning) live in
`tests/integration/test_morning_brief_service.py`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.services.morning_brief_service import (
    MIN_VIEW_GAP,
    _previous_business_day_morning_boundary,
    _should_record_new_view,
)

# A Wednesday (2026-08-05) 10:00 UTC — an ordinary mid-week reference point.
_WEDNESDAY = datetime(2026, 8, 5, 10, 0, tzinfo=UTC)
# A Monday (2026-08-10) 10:00 UTC.
_MONDAY = datetime(2026, 8, 10, 10, 0, tzinfo=UTC)
# A Sunday (2026-08-09) 10:00 UTC.
_SUNDAY = datetime(2026, 8, 9, 10, 0, tzinfo=UTC)


def test_fallback_from_a_weekday_is_the_previous_day() -> None:
    boundary = _previous_business_day_morning_boundary(_WEDNESDAY)
    assert boundary.date().isoformat() == "2026-08-04"  # Tuesday
    assert boundary.hour == 6


def test_fallback_from_monday_skips_back_to_friday() -> None:
    """The previous calendar day before a Monday is Sunday — a weekend,
    never a real analyst workday — so the fallback must skip back to the
    preceding Friday, not land on Sunday."""
    boundary = _previous_business_day_morning_boundary(_MONDAY)
    assert boundary.date().isoformat() == "2026-08-07"  # Friday
    assert boundary.weekday() == 4


def test_fallback_from_sunday_also_skips_back_to_friday() -> None:
    boundary = _previous_business_day_morning_boundary(_SUNDAY)
    assert boundary.date().isoformat() == "2026-08-07"  # Friday


def test_should_record_new_view_when_none_exists_yet() -> None:
    assert _should_record_new_view(None, _WEDNESDAY) is True


def test_should_not_record_within_min_gap() -> None:
    """Idempotent refresh/reopen: a view recorded moments ago must not be
    re-recorded, or the boundary would silently advance on every page
    refresh within the same working session."""
    recent = _WEDNESDAY - timedelta(minutes=5)
    assert _should_record_new_view(recent, _WEDNESDAY) is False


def test_should_record_once_min_gap_has_elapsed() -> None:
    old_enough = _WEDNESDAY - MIN_VIEW_GAP - timedelta(minutes=1)
    assert _should_record_new_view(old_enough, _WEDNESDAY) is True


def test_should_not_record_exactly_at_the_gap_boundary() -> None:
    exactly_at_gap = _WEDNESDAY - MIN_VIEW_GAP
    assert _should_record_new_view(exactly_at_gap, _WEDNESDAY) is False
