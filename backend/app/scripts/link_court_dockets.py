"""Link real CourtListener dockets to real, already-verified issuers
(PLAN.md sections 4.5, 15, Milestone 7).

    python -m app.scripts.link_court_dockets

Live-verifies each candidate via CourtListener's real Search API before
linking — never a hand-typed/guessed `courtlistener_docket_id`, the same
live-verification discipline `app.scripts.seed_research_universes`
established for SEC issuer identity. A candidate whose search doesn't
return the expected docket id is rejected and the reason printed, never
silently skipped.

Idempotent — safe to re-run: `court_docket_repository.create_docket` is a
get-or-create by `courtlistener_docket_id`.

Candidates are real, genuinely distressed issuers already seeded by
Milestone 6.5 (`app.scripts.seed_research_universes`) whose real Chapter 11
filings were already independently confirmed via live SEC EDGAR evidence in
that milestone's Historical Backfill Demo — linking their real CourtListener
dockets here lets the same real distress event be corroborated by a second,
independent real provider (PLAN.md's "research operating system" workflow
chain: Evidence -> Alerts, now fed by more than one provider).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

from app.config import get_settings
from app.db.session import SessionLocal
from app.providers.courtlistener.client import build_http_client
from app.providers.courtlistener.provider import DocketSearchCandidate, link_docket, search_dockets
from app.repositories import issuer_repository


@dataclass(frozen=True, slots=True)
class LinkCandidate:
    issuer_cik: str
    search_query: str
    court: str
    expected_courtlistener_docket_id: int
    note: str


# Real issuers already seeded by Milestone 6.5 with a real, independently
# confirmed Chapter 11 filing (via live SEC EDGAR evidence — see BUILD_LOG.md).
# `expected_courtlistener_docket_id` was live-verified once during Milestone 7
# development (see BUILD_LOG.md) and is re-verified live again on every run —
# never trusted as a bare literal.
_CANDIDATES: tuple[LinkCandidate, ...] = (
    LinkCandidate(
        issuer_cik="0000028823",  # Diebold Nixdorf, Inc.
        search_query="Diebold Holding Company",
        court="txsb",
        expected_courtlistener_docket_id=67460054,
        note="Diebold Holding Company, Inc. and Diebold Nixdorf Holding Company, Inc., "
        "23-90602, filed 2023-06-01 — the real Chapter 11 case, jointly administered.",
    ),
    LinkCandidate(
        issuer_cik="0001415404",  # EchoStar CORP
        search_query="Hughes Satellite Systems",
        court="txsb",
        expected_courtlistener_docket_id=73709078,
        note="Hughes Satellite Systems Corporation (HSSC, an EchoStar subsidiary), "
        "26-90739, filed 2026-08-02 — matches the real 8-K disclosed 2026-08-03 "
        "already ingested as sec_edgar evidence in Milestone 6.5's backfill.",
    ),
    LinkCandidate(
        issuer_cik="0001456772",  # OFFICE PROPERTIES INCOME TRUST
        search_query="Office Properties Income Trust",
        court="txsb",
        expected_courtlistener_docket_id=71832072,
        note="SIR Santa Clara LP and Office Properties Income Trust, 25-90592, "
        "filed 2025-10-30 — matches the real 10-Q/8-K date already ingested as "
        "sec_edgar evidence in Milestone 6.5's backfill.",
    ),
)


def main() -> int:
    settings = get_settings()
    if SessionLocal is None:
        print("ERROR: DATABASE_URL is not configured.", file=sys.stderr)
        return 1
    if not settings.courtlistener_api_token:
        print("ERROR: COURTLISTENER_API_TOKEN is not configured.", file=sys.stderr)
        return 1

    http_client = build_http_client(
        user_agent="nexus-credit-intelligence-research (link_court_dockets)",
        api_token=settings.courtlistener_api_token,
        max_retry_after_seconds=settings.courtlistener_retry_after_max_seconds,
    )
    db = SessionLocal()

    linked = 0
    rejected: list[str] = []
    try:
        for candidate in _CANDIDATES:
            issuer = issuer_repository.get_issuer_by_cik(db, candidate.issuer_cik)
            if issuer is None:
                reason = f"no issuer with CIK {candidate.issuer_cik} exists yet"
                rejected.append(f"{candidate.search_query}: {reason}")
                print(f"  REJECTED {candidate.search_query}: {reason}")
                continue

            search_results = search_dockets(
                db, http_client, query=candidate.search_query, court=candidate.court
            )
            match: DocketSearchCandidate | None = next(
                (
                    c
                    for c in search_results
                    if c.dto.docket_id == candidate.expected_courtlistener_docket_id
                ),
                None,
            )
            if match is None:
                reason = (
                    f"expected docket_id {candidate.expected_courtlistener_docket_id} "
                    f"not found in {len(search_results)} live search result(s)"
                )
                rejected.append(f"{candidate.search_query}: {reason}")
                print(f"  REJECTED {candidate.search_query}: {reason}")
                continue

            docket, created = link_docket(db, issuer_id=issuer.id, candidate=match)
            db.commit()
            status = "linked" if created else "already linked (idempotent skip)"
            print(
                f"  LINKED {issuer.legal_name} -> {docket.case_name} "
                f"({docket.docket_number}, {docket.court}) [{status}]"
            )
            print(f"          {candidate.note}")
            linked += 1

        print("\n=== Summary ===")
        print(f"Dockets linked: {linked}")
        print(f"Candidates rejected: {len(rejected)}")
        if rejected:
            print("Rejected candidates and reasons:")
            for reason in rejected:
                print(f"  - {reason}")
        return 0
    finally:
        db.close()
        http_client.close()


if __name__ == "__main__":
    sys.exit(main())
