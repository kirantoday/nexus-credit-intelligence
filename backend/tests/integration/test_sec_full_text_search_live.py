"""Live proof that `SecEdgarClient.search_full_text` really talks to SEC's
full-text-search API and parses a real response (PLAN.md Milestone 7.5).
Skipped gracefully without `SEC_USER_AGENT`, matching this project's
established gating pattern (see `test_sec_edgar_live_ingestion.py`).

Deliberately does not assert an exact hit count — SEC's live index changes
daily — only that the call succeeds and the shape is real.
"""

from __future__ import annotations

from datetime import date

from app.providers.base.http_client import ThrottledHttpClient
from app.providers.sec_edgar.client import SecEdgarClient


def test_live_full_text_search_returns_real_shape(sec_http_client: ThrottledHttpClient) -> None:
    client = SecEdgarClient(sec_http_client)

    result = client.search_full_text(
        '"chapter 11"',
        forms=("8-K",),
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 3),
        size=10,
    )

    assert result.dto.hits.total.value >= 0
    for hit in result.dto.hits.hits:
        assert hit.source.ciks
        assert hit.source.adsh
        assert hit.source.form
        assert hit.source.file_date
