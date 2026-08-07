"""Shared issuer identity resolution (PLAN.md Milestone 7.5).

Extracted from `app/scripts/seed_research_universes.py`'s original
`_resolve_cik`/`_verify_live` (no behavior change to that script — it now
calls these same functions). Two entry points:

- `resolve_issuer_identity_by_ticker_or_name` — the original heuristic path
  (ticker match, falling back to unambiguous word-boundary name match,
  never a fuzzy/automatic merge). Used when only a ticker/name hint is
  known, e.g. a hand-curated seed candidate list.
- `resolve_issuer_identity_by_cik` — a strictly lower false-positive-risk
  path used by the SEC market-discovery pipeline, because a full-text-search
  hit already carries an authoritative CIK straight from SEC itself
  (`_source.ciks`) — no name/ticker guessing is needed at all. Live
  verification (`verify_issuer_live`) is still required before creating a
  *new* issuer, so an inactive/shell CIK is still rejected, not trusted
  blindly.

Both paths funnel into the same outcomes
(`MarketDiscoveryResolutionOutcome`: `matched_existing`/`verified_new`/
`ambiguous`/`rejected`/`unresolved`) and the same "never silently guess"
discipline the word-boundary fix (the Yellow/Yellowstone bug) established:
an ambiguous or failed resolution is always reported with a reason, never
dropped or auto-merged.
"""

from __future__ import annotations

import json
import re

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.types import MarketDiscoveryResolutionOutcome
from app.providers.base.http_client import ThrottledHttpClient
from app.providers.sec_edgar import provider as sec_provider
from app.providers.sec_edgar.client import SecEdgarClient, format_cik10
from app.repositories import issuer_repository

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"


class IssuerResolutionResult(BaseModel):
    """The outcome of one identity-resolution attempt — always populated
    with a human-readable reason, mirroring `_resolve_cik`'s original
    "never silently drop" discipline."""

    model_config = ConfigDict(frozen=True)

    outcome: MarketDiscoveryResolutionOutcome
    cik: str | None
    issuer_id: str | None  # str, not UUID — issuer.id as returned by the repository
    legal_name: str | None
    reason: str


def fetch_sec_ticker_map(http_client: ThrottledHttpClient) -> dict[str, dict[str, object]]:
    response = http_client.get(TICKERS_URL)
    raw = json.loads(response.raw_bytes)
    return {str(entry["ticker"]).upper(): entry for entry in raw.values()}


def resolve_cik_by_ticker_or_name(
    ticker_map: dict[str, dict[str, object]], *, ticker: str, name_hint: str
) -> tuple[str | None, str]:
    """Ticker match first; word-boundary (never bare-substring) name match
    as fallback. `\\b` word boundaries are the fix for a real live false
    positive: a naive `"yellow" in "yellowstone group ltd."` containment
    check silently resolved Yellow Corporation (delisted from
    `company_tickers.json` after its 2023 liquidation) to the unrelated
    "Yellowstone Group Ltd." instead of correctly reporting "no match."
    More than one name match is `ambiguous`, never auto-merged.
    """
    entry = ticker_map.get(ticker.upper())
    if entry is not None:
        return str(entry["cik_str"]), f"resolved by ticker {ticker}"

    name_pattern = re.compile(rf"\b{re.escape(name_hint.lower())}\b")
    matches = [e for e in ticker_map.values() if name_pattern.search(str(e["title"]).lower())]
    if len(matches) == 1:
        return (
            str(matches[0]["cik_str"]),
            f"resolved by unambiguous name match '{matches[0]['title']}'",
        )
    if len(matches) > 1:
        return (
            None,
            f"ambiguous name match ({len(matches)} candidates in company_tickers.json) "
            "— excluded, no automatic fuzzy merge",
        )
    return None, "no ticker or name match found in SEC company_tickers.json"


def verify_issuer_live(http_client: ThrottledHttpClient, cik: str) -> tuple[bool, str]:
    """A real, live `fetch_submissions` call — confirms the CIK is a real,
    active SEC filer with at least one filing on record, not just a
    syntactically valid CIK number."""
    client = SecEdgarClient(http_client)
    cik10 = format_cik10(cik)
    try:
        result = client.fetch_submissions(cik10)
    except Exception as exc:  # noqa: BLE001 - any live-fetch failure means "exclude", not "crash"
        return False, f"live verification fetch failed: {exc}"

    dto = result.dto
    if not dto.name:
        return False, "live verification returned no entity name"
    filing_count = len(dto.filings.recent.accessionNumber)
    if filing_count == 0:
        return False, "live verification found zero filings on record — excluded as inactive/shell"
    return (
        True,
        f"verified live: '{dto.name}' (CIK {cik10}), {filing_count} recent filing(s) on file",
    )


def resolve_issuer_identity_by_cik(
    db: Session, http_client: ThrottledHttpClient, *, cik: str
) -> IssuerResolutionResult:
    """CIK-first resolution for SEC full-text-search discovery hits — the
    CIK is authoritative (SEC's own `_source.ciks`), so this is a strictly
    lower false-positive-risk path than name/ticker matching: no word-
    boundary heuristic is even needed for a *known* issuer, and a *new*
    issuer still goes through the same live-verification gate as the
    original seed-script flow before being created.
    """
    cik10 = format_cik10(cik)
    existing = issuer_repository.get_issuer_by_cik(db, cik10)
    if existing is not None:
        return IssuerResolutionResult(
            outcome=MarketDiscoveryResolutionOutcome.MATCHED_EXISTING,
            cik=existing.cik,
            issuer_id=str(existing.id),
            legal_name=existing.legal_name,
            reason="issuer already known by CIK",
        )

    verified, reason = verify_issuer_live(http_client, cik10)
    if not verified:
        return IssuerResolutionResult(
            outcome=MarketDiscoveryResolutionOutcome.REJECTED,
            cik=cik10,
            issuer_id=None,
            legal_name=None,
            reason=reason,
        )

    issuer, created = sec_provider.ingest_issuer_identity_only(db, http_client, cik=cik10)
    return IssuerResolutionResult(
        outcome=(
            MarketDiscoveryResolutionOutcome.VERIFIED_NEW
            if created
            else MarketDiscoveryResolutionOutcome.MATCHED_EXISTING
        ),
        cik=issuer.cik,
        issuer_id=str(issuer.id),
        legal_name=issuer.legal_name,
        reason=reason,
    )


def resolve_issuer_identity_by_ticker_or_name(
    db: Session,
    http_client: ThrottledHttpClient,
    ticker_map: dict[str, dict[str, object]],
    *,
    ticker: str,
    name_hint: str,
) -> IssuerResolutionResult:
    """The original seed-script heuristic path, now shared. Ambiguous/
    unresolved ticker-or-name lookups never reach live verification or
    issuer creation at all — they are reported and excluded immediately,
    exactly as `seed_research_universes.py` always did.
    """
    cik, resolve_reason = resolve_cik_by_ticker_or_name(
        ticker_map, ticker=ticker, name_hint=name_hint
    )
    if cik is None:
        outcome = (
            MarketDiscoveryResolutionOutcome.AMBIGUOUS
            if "ambiguous" in resolve_reason
            else MarketDiscoveryResolutionOutcome.UNRESOLVED
        )
        return IssuerResolutionResult(
            outcome=outcome, cik=None, issuer_id=None, legal_name=None, reason=resolve_reason
        )

    return resolve_issuer_identity_by_cik(db, http_client, cik=cik)
