"""Unit tests for SEC EDGAR provider DTOs (PLAN.md Milestone 7.5).

Regression test for a real bug found during the Milestone 7.5 Jan-Aug 2026
historical backfill: SEC's real live submissions API returns
`exchanges: [null]` for some issuers (those with no formal listed exchange
— OTC-only, some foreign private issuers), which `SecSubmissionsDTO`
originally rejected outright with a pydantic validation error. This caused
`verify_issuer_live` to report "live verification fetch failed," correctly
failing closed (excluded, never guessed at) but excluding 8 real,
otherwise-resolvable candidates — including Cumulus Media Inc, a real
Chapter 11 filer — for a fixable data-shape reason, not a genuine identity
ambiguity.
"""

from __future__ import annotations

from app.providers.sec_edgar.dto import SecSubmissionsDTO


def test_tolerates_null_entries_in_exchanges() -> None:
    """Real, live-observed shape (not guessed): `exchanges` containing a
    `null` entry for an issuer with no formal listed exchange."""
    payload = {
        "cik": "0001058623",
        "name": "CUMULUS MEDIA INC",
        "tickers": ["CMLS"],
        "exchanges": [None],
    }

    dto = SecSubmissionsDTO.model_validate(payload)

    assert dto.name == "CUMULUS MEDIA INC"
    assert dto.exchanges == [None]


def test_still_parses_normal_populated_exchanges() -> None:
    payload = {
        "cik": "0000320193",
        "name": "Apple Inc.",
        "tickers": ["AAPL"],
        "exchanges": ["Nasdaq"],
    }

    dto = SecSubmissionsDTO.model_validate(payload)

    assert dto.exchanges == ["Nasdaq"]
