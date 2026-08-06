"""Unit tests for `app/scripts/seed_research_universes.py`'s CIK resolution
logic (PLAN.md 24.2) — specifically a real bug this milestone hit live:
`_resolve_cik`'s name-hint fallback must use word-boundary matching, not
bare substring containment, or "yellow" silently matches an unrelated
"Yellowstone Group Ltd." No network — a synthetic ticker map only.
"""

from __future__ import annotations

from app.scripts.seed_research_universes import Candidate, _resolve_cik


def _ticker_map(*entries: tuple[str, str, int]) -> dict[str, dict[str, object]]:
    return {
        ticker.upper(): {"ticker": ticker, "title": title, "cik_str": cik}
        for ticker, title, cik in entries
    }


def test_exact_ticker_match_resolves_directly() -> None:
    ticker_map = _ticker_map(("AAPL", "Apple Inc.", 320193))
    candidate = Candidate("AAPL", "Apple", (), "rationale", None)

    cik, reason = _resolve_cik(ticker_map, candidate)

    assert cik == "320193"
    assert "ticker" in reason


def test_name_fallback_matches_a_whole_word() -> None:
    ticker_map = _ticker_map(("XYZ", "Example Yellow Corp", 111))
    candidate = Candidate("YELL", "Yellow", (), "rationale", None)

    cik, reason = _resolve_cik(ticker_map, candidate)

    assert cik == "111"
    assert "name match" in reason


def test_name_fallback_does_not_match_a_substring_inside_a_longer_word() -> None:
    """The real live bug: ticker YELL doesn't exist; a naive substring check
    ("yellow" in "yellowstone group ltd.") would wrongly resolve to an
    unrelated company. Word-boundary matching must reject this."""
    ticker_map = _ticker_map(("YSGL", "Yellowstone Group Ltd.", 2071489))
    candidate = Candidate("YELL", "Yellow", (), "rationale", None)

    cik, reason = _resolve_cik(ticker_map, candidate)

    assert cik is None
    assert "no ticker or name match" in reason


def test_ambiguous_name_match_is_excluded_not_merged() -> None:
    ticker_map = _ticker_map(
        ("ONE", "Example Yellow Corp", 1),
        ("TWO", "Yellow Holdings Inc.", 2),
    )
    candidate = Candidate("YELL", "Yellow", (), "rationale", None)

    cik, reason = _resolve_cik(ticker_map, candidate)

    assert cik is None
    assert "ambiguous" in reason
    assert "no automatic fuzzy merge" in reason


def test_no_match_at_all_is_reported_clearly() -> None:
    ticker_map = _ticker_map(("AAPL", "Apple Inc.", 320193))
    candidate = Candidate("ZZZZ", "Nonexistent Company", (), "rationale", None)

    cik, reason = _resolve_cik(ticker_map, candidate)

    assert cik is None
    assert "no ticker or name match" in reason
