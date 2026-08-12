"""Unit tests for `app/repositories/search_repository.py`'s pure helpers
(PLAN.md 4.13, 8; Milestone 12A).

Everything else in this module issues real SQL against live-only
generated `tsvector` columns — covered by
`tests/integration/test_search_service.py` instead.
"""

from __future__ import annotations

from app.repositories.search_repository import _first_non_empty, _truncate


def test_truncate_returns_none_for_none_or_empty() -> None:
    assert _truncate(None) is None
    assert _truncate("") is None
    assert _truncate("   ") is None


def test_truncate_returns_short_text_unchanged() -> None:
    assert _truncate("Chapter 11 filing", length=180) == "Chapter 11 filing"


def test_truncate_shortens_long_text_with_ellipsis() -> None:
    long_text = "A" * 200
    result = _truncate(long_text, length=50)
    assert result is not None
    assert len(result) <= 50
    assert result.endswith("…")


def test_first_non_empty_returns_first_truthy_value() -> None:
    assert _first_non_empty(None, "", "base case text", "bull case text") == "base case text"


def test_first_non_empty_returns_none_when_all_empty() -> None:
    assert _first_non_empty(None, "", None) is None
