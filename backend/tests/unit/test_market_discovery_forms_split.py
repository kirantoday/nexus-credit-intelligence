"""Unit tests for `market_discovery_service._split_forms_for_full_text_search`
(PLAN.md Milestone 7.5.1).

Live-verified against `efts.sec.gov`: a "chapter 11" full-text-search query
over a fixed window returned 577 hits for `forms=8-K` alone, 1002 for
`forms=8-K,10-K`, but 0 for `forms=8-K,10-K/A` — mixing a single
amendment-suffix form into the same comma list as a base form silently
breaks SEC's filter. The 10-form `MONITORED_FORM_TYPES` list (5 base + 5
amendment types) this milestone actually sends returned just 50 hits
instead of the ~1460 confirmed to exist. These tests cover the pure
splitting logic in isolation, no network.
"""

from __future__ import annotations

from app.core.types import MONITORED_FORM_TYPES
from app.services.market_discovery_service import _split_forms_for_full_text_search


def test_splits_mixed_base_and_amendment_forms_into_two_groups() -> None:
    groups = _split_forms_for_full_text_search(("8-K", "8-K/A", "10-K", "10-K/A"))

    assert len(groups) == 2
    for group in groups:
        has_base = any("/" not in f for f in group)
        has_amendment = any("/" in f for f in group)
        assert not (has_base and has_amendment)
    assert {f for group in groups for f in group} == {"8-K", "8-K/A", "10-K", "10-K/A"}


def test_all_base_forms_produce_a_single_group() -> None:
    groups = _split_forms_for_full_text_search(("8-K", "10-K", "10-Q"))

    assert groups == [("10-K", "10-Q", "8-K")]


def test_all_amendment_forms_produce_a_single_group() -> None:
    groups = _split_forms_for_full_text_search(("8-K/A", "10-K/A"))

    assert groups == [("10-K/A", "8-K/A")]


def test_empty_forms_produces_no_groups() -> None:
    assert _split_forms_for_full_text_search(()) == []


def test_full_monitored_form_types_split_matches_live_verified_shape() -> None:
    """The exact 10-form list this milestone's discovery pipeline uses —
    confirms 5 base / 5 amendment, matching the live-verified split that
    recovers full coverage."""
    groups = _split_forms_for_full_text_search(tuple(sorted(MONITORED_FORM_TYPES)))

    assert len(groups) == 2
    sizes = sorted(len(group) for group in groups)
    assert sizes == [5, 5]
