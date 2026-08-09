"""Unit tests for `app/services/morning_brief_service.py`'s pure
business-day-cycle logic (PLAN.md Milestone 7.5.2's business-day-cycle
correction) — no I/O, no database.

Covers `_previous_business_day` and `_most_recent_business_day` (the
first-ever-cycle fallback). Integration-level scenarios (real canonical
run data driving `get_morning_brief`, idempotent repeated calls,
universe-membership changes, new-vs-historical partitioning) live in
`tests/integration/test_morning_brief_service.py`.
"""

from __future__ import annotations

from datetime import date

from app.services.morning_brief_service import _most_recent_business_day, _previous_business_day

# 2026-08-07 is a Friday, 2026-08-10 is the following Monday.
_FRIDAY = date(2026, 8, 7)
_SATURDAY = date(2026, 8, 8)
_SUNDAY = date(2026, 8, 9)
_MONDAY = date(2026, 8, 10)
_WEDNESDAY = date(2026, 8, 5)


def test_previous_business_day_from_friday_is_thursday() -> None:
    assert _previous_business_day(_FRIDAY) == date(2026, 8, 6)


def test_previous_business_day_from_monday_skips_the_weekend_to_friday() -> None:
    assert _previous_business_day(_MONDAY) == _FRIDAY


def test_previous_business_day_from_a_midweek_day_is_simply_the_day_before() -> None:
    assert _previous_business_day(_WEDNESDAY) == date(2026, 8, 4)


def test_most_recent_business_day_on_a_weekday_is_itself() -> None:
    assert _most_recent_business_day(_WEDNESDAY) == _WEDNESDAY
    assert _most_recent_business_day(_FRIDAY) == _FRIDAY
    assert _most_recent_business_day(_MONDAY) == _MONDAY


def test_most_recent_business_day_on_saturday_is_friday() -> None:
    assert _most_recent_business_day(_SATURDAY) == _FRIDAY


def test_most_recent_business_day_on_sunday_is_friday() -> None:
    assert _most_recent_business_day(_SUNDAY) == _FRIDAY
