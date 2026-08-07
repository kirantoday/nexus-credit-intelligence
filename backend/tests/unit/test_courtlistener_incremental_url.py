"""Unit test for `CourtListenerClient`'s TD-012 incremental-sync URL builder
(PLAN.md Milestone 7.5). Pure string construction, no network — the actual
live-verified behavior of `id__gt`/`order_by=id` was confirmed via a real
`OPTIONS` request against `docket-entries/` before this was implemented
(see `app/providers/courtlistener/provider.py`'s `sync_docket_entries`
docstring).
"""

from __future__ import annotations

from app.providers.courtlistener.client import CourtListenerClient


def test_full_walk_url_orders_by_entry_number() -> None:
    client = CourtListenerClient(http_client=None)  # type: ignore[arg-type]

    url = client.docket_entries_url(67460054)

    assert "docket=67460054" in url
    assert "order_by=entry_number" in url
    assert "id__gt" not in url


def test_incremental_url_filters_by_id_greater_than_and_orders_by_id() -> None:
    client = CourtListenerClient(http_client=None)  # type: ignore[arg-type]

    url = client.docket_entries_incremental_url(67460054, since_entry_id=555999)

    assert "docket=67460054" in url
    assert "id__gt=555999" in url
    assert "order_by=id" in url
