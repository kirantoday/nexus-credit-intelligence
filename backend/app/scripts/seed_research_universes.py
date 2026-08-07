"""Seed script: Research Universes populated with real, live-verified SEC
issuers (PLAN.md 24.2, 24.1).

    python -m app.scripts.seed_research_universes

Never fabricates a CIK, filing, or distress status. Every candidate is:
1. Resolved to a CIK via SEC's public `company_tickers.json` (ticker match,
   falling back to an unambiguous company-name substring match — never a
   fuzzy/automatic merge when more than one name matches).
2. Live-verified via a real `fetch_submissions` call, confirming the entity
   exists and has at least one filing on record.
3. Ingested via `providers.sec_edgar.provider.ingest_issuer_identity_only`
   (the standard Provider DTO -> Normalizer -> Canonical Domain Object ->
   Repository pipeline, ADR-004) — idempotent against issuers that already
   exist (e.g. Apple Inc. from Milestone 3).

Unresolved/ambiguous/inactive candidates are excluded and the reason is
printed, never silently dropped or guessed at (per the request's explicit
"document rejected or ambiguous candidates" requirement).

Idempotent end to end — safe to re-run: existing collections/issuers are
detected and skipped rather than duplicated.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from app.config import get_settings
from app.core.issuer_resolver import fetch_sec_ticker_map, resolve_issuer_identity_by_ticker_or_name
from app.core.types import (
    CollectionPriority,
    CollectionScope,
    CollectionType,
    CollectionVisibility,
    CurationMethod,
    MarketDiscoveryResolutionOutcome,
    VerificationStatus,
)
from app.db.session import SessionLocal
from app.domain.collection import CollectionCreate, CollectionMembershipCreate
from app.providers.base.http_client import ThrottledHttpClient
from app.repositories import collection_repository


@dataclass(frozen=True, slots=True)
class Candidate:
    ticker: str
    name_hint: str
    universes: tuple[str, ...]
    rationale: str
    rationale_as_of_date: str | None  # ISO date, or None for an undated general rationale


@dataclass(frozen=True, slots=True)
class UniverseDefinition:
    slug: str
    name: str
    description: str
    collection_type: CollectionType
    priority: CollectionPriority | None


# Fifteen requested universes (PLAN.md 24, the enhancement request's
# "INITIAL RESEARCH UNIVERSES" list). Priority is reserved metadata for a
# future Morning Research Brief prioritization feature — not used for
# sorting logic this milestone.
_UNIVERSES: tuple[UniverseDefinition, ...] = (
    UniverseDefinition(
        "distressed-core",
        "Distressed Core",
        "Issuers with well-documented, dated credit distress — the core coverage list "
        "for active distressed-credit research.",
        CollectionType.RESEARCH_UNIVERSE,
        CollectionPriority.CRITICAL,
    ),
    UniverseDefinition(
        "chapter-11-bankruptcy",
        "Chapter 11 / Bankruptcy",
        "Issuers with a real, dated Chapter 11 (or equivalent) filing on the public record.",
        CollectionType.RESEARCH_UNIVERSE,
        CollectionPriority.CRITICAL,
    ),
    UniverseDefinition(
        "post-emergence",
        "Post-Emergence",
        "Issuers that have emerged from a prior Chapter 11 restructuring and are being "
        "tracked for post-emergence credit performance.",
        CollectionType.RESEARCH_UNIVERSE,
        CollectionPriority.HIGH,
    ),
    UniverseDefinition(
        "liability-management",
        "Liability Management",
        "Issuers with documented exchange offers, uptiering, or other liability "
        "management transaction activity.",
        CollectionType.RESEARCH_UNIVERSE,
        CollectionPriority.HIGH,
    ),
    UniverseDefinition(
        "refinancing-risk",
        "Refinancing Risk",
        "Issuers whose capital structure carries meaningful near-term refinancing risk.",
        CollectionType.RESEARCH_UNIVERSE,
        CollectionPriority.HIGH,
    ),
    UniverseDefinition(
        "upcoming-maturity-wall",
        "Upcoming Maturity Wall",
        "Issuers with material bond/loan maturities in the near-term maturity wall.",
        CollectionType.RESEARCH_UNIVERSE,
        CollectionPriority.HIGH,
    ),
    UniverseDefinition(
        "fallen-angels",
        "Fallen Angels",
        "Large public issuers that have lost investment-grade rating within recent history.",
        CollectionType.RESEARCH_UNIVERSE,
        CollectionPriority.MEDIUM,
    ),
    UniverseDefinition(
        "high-yield",
        "High Yield",
        "Below-investment-grade public issuers with actively traded debt.",
        CollectionType.RESEARCH_UNIVERSE,
        CollectionPriority.MEDIUM,
    ),
    UniverseDefinition(
        "healthcare",
        "Healthcare",
        "Public healthcare-sector issuers with credit-relevant history.",
        CollectionType.RESEARCH_UNIVERSE,
        CollectionPriority.MEDIUM,
    ),
    UniverseDefinition(
        "consumer-retail",
        "Consumer & Retail",
        "Public consumer/retail issuers spanning distress to turnaround.",
        CollectionType.RESEARCH_UNIVERSE,
        CollectionPriority.MEDIUM,
    ),
    UniverseDefinition(
        "telecom-media",
        "Telecom & Media",
        "Public telecom and media issuers with credit-relevant leverage or restructuring history.",
        CollectionType.RESEARCH_UNIVERSE,
        CollectionPriority.MEDIUM,
    ),
    UniverseDefinition(
        "transportation",
        "Transportation",
        "Public transportation-sector issuers (airlines, rental, freight) with "
        "credit-relevant history.",
        CollectionType.RESEARCH_UNIVERSE,
        CollectionPriority.MEDIUM,
    ),
    UniverseDefinition(
        "energy",
        "Energy",
        "Public energy-sector issuers with credit-relevant leverage or restructuring history.",
        CollectionType.RESEARCH_UNIVERSE,
        CollectionPriority.MEDIUM,
    ),
    UniverseDefinition(
        "real-estate",
        "Real Estate",
        "Public real-estate issuers (REITs and operators) with credit-relevant history.",
        CollectionType.RESEARCH_UNIVERSE,
        CollectionPriority.MEDIUM,
    ),
    UniverseDefinition(
        "investment-grade-benchmarks",
        "Investment Grade Benchmarks",
        "Large, stable investment-grade issuers used as a clean baseline for leverage, "
        "coverage, liquidity, maturity profile, and spread comparison — never mixed into "
        "distressed-screening views.",
        CollectionType.BENCHMARK,
        CollectionPriority.LOW,
    ),
)

# Real-world candidates. `rationale` cites a real, dated, publicly-documented
# reason a distressed-credit team would track this issuer — a curatorial
# judgment, not an assertion of *current* status (PLAN.md 24.1: membership
# alone never asserts current distress/bankruptcy/rating). Live filing
# activity, if any, is what the Overnight Distress Filing Monitor separately
# surfaces as dated evidence.
_CANDIDATES: tuple[Candidate, ...] = (
    Candidate(
        "RAD",
        "Rite Aid",
        ("distressed-core", "chapter-11-bankruptcy", "consumer-retail"),
        "Filed for Chapter 11 bankruptcy protection in October 2023 (a second Chapter 11 "
        "followed in 2025); tracked for distressed-retail credit history.",
        "2023-10-15",
    ),
    Candidate(
        "LUMN",
        "Lumen Technologies",
        (
            "distressed-core",
            "refinancing-risk",
            "upcoming-maturity-wall",
            "high-yield",
            "telecom-media",
        ),
        "Highly levered legacy telecom carrier with a publicly documented history of "
        "liability-management and refinancing activity.",
        None,
    ),
    Candidate(
        "MNK",
        "Mallinckrodt",
        (
            "distressed-core",
            "chapter-11-bankruptcy",
            "post-emergence",
            "liability-management",
            "healthcare",
        ),
        "Filed Chapter 11 twice (2020 and 2023), most recently emerging via a prepackaged "
        "plan in November 2023; tracked for post-emergence and liability-management history.",
        "2023-11-14",
    ),
    Candidate(
        "CYH",
        "Community Health Systems",
        (
            "liability-management",
            "refinancing-risk",
            "upcoming-maturity-wall",
            "high-yield",
            "healthcare",
        ),
        "Highly levered hospital operator with documented liability-management exchange "
        "activity and a closely watched maturity profile.",
        None,
    ),
    Candidate(
        "CVNA",
        "Carvana",
        ("liability-management", "high-yield", "consumer-retail"),
        "Completed a widely covered debt exchange/liability-management transaction in 2023 "
        "as part of a broader balance-sheet restructuring.",
        "2023-07-01",
    ),
    Candidate(
        "OPI",
        "Office Properties Income Trust",
        ("refinancing-risk", "upcoming-maturity-wall", "real-estate"),
        "Office-sector REIT with a publicly documented near-term maturity wall amid office "
        "real estate credit pressure.",
        None,
    ),
    Candidate(
        "SATS",
        "EchoStar",
        ("high-yield", "telecom-media"),
        "Satellite/wireless carrier (merged with DISH Network in 2024) with below-"
        "investment-grade public debt.",
        None,
    ),
    Candidate(
        "DBD",
        "Diebold Nixdorf",
        ("distressed-core", "chapter-11-bankruptcy", "post-emergence"),
        "Completed a prepackaged Chapter 11 restructuring in September 2023; tracked for "
        "post-emergence credit performance.",
        "2023-09-01",
    ),
    Candidate(
        "YELL",
        "Yellow",
        ("distressed-core", "chapter-11-bankruptcy", "transportation"),
        "Filed for Chapter 11 bankruptcy and ceased trucking operations in August 2023.",
        "2023-08-06",
    ),
    Candidate(
        "BIG",
        "Big Lots",
        ("distressed-core", "chapter-11-bankruptcy", "consumer-retail"),
        "Filed for Chapter 11 bankruptcy protection in September 2024.",
        "2024-09-09",
    ),
    Candidate(
        "EXE",
        "Expand Energy",
        ("post-emergence", "energy"),
        "Formed from the 2024 merger of Chesapeake Energy (which emerged from its own "
        "Chapter 11 in 2021) and Southwestern Energy; tracked for post-emergence history.",
        None,
    ),
    Candidate(
        "HTZ",
        "Hertz Global",
        ("post-emergence", "transportation"),
        "Emerged from Chapter 11 bankruptcy in June 2021; tracked for post-emergence "
        "credit performance amid fleet-related earnings pressure.",
        "2021-06-30",
    ),
    Candidate(
        "FYBR",
        "Frontier Communications",
        ("refinancing-risk", "telecom-media"),
        "Emerged from a prior Chapter 11 in 2021; agreed to be acquired by Verizon "
        "(announced September 2024), a transaction relevant to its capital structure.",
        None,
    ),
    Candidate(
        "BHC",
        "Bausch Health",
        ("high-yield", "healthcare"),
        "Highly levered specialty pharmaceutical issuer with below-investment-grade public debt.",
        None,
    ),
    Candidate(
        "AMC",
        "AMC Entertainment",
        ("high-yield", "consumer-retail", "telecom-media"),
        "Highly levered cinema operator with a publicly documented history of dilutive "
        "and liability-management financing since 2020.",
        None,
    ),
    Candidate(
        "SAVE",
        "Spirit Airlines",
        ("high-yield", "transportation"),
        "Filed for Chapter 11 bankruptcy protection in November 2024.",
        "2024-11-18",
    ),
    Candidate(
        "CAR",
        "Avis Budget Group",
        ("fallen-angels", "high-yield", "transportation"),
        "Rental-car operator with below-investment-grade public debt and fleet-residual-"
        "value sensitivity.",
        None,
    ),
    Candidate(
        "OXY",
        "Occidental Petroleum",
        ("fallen-angels", "energy"),
        "Lost investment-grade rating following the 2019 Anadarko acquisition; tracked as "
        "a fallen-angel deleveraging story.",
        None,
    ),
    Candidate(
        "F",
        "Ford Motor",
        ("fallen-angels",),
        "Lost investment-grade rating from multiple agencies in 2020; large public "
        "issuer tracked for leverage/coverage trend.",
        "2020-03-25",
    ),
    Candidate(
        "KHC",
        "Kraft Heinz",
        ("fallen-angels",),
        "Faced ratings pressure and a downgrade toward the investment-grade/high-yield "
        "boundary following its 2019 write-down and SEC inquiry.",
        None,
    ),
    Candidate(
        "AAPL",
        "Apple",
        ("investment-grade-benchmarks",),
        "Clean investment-grade baseline issuer for leverage, coverage, and spread comparison.",
        None,
    ),
    Candidate(
        "MSFT",
        "Microsoft",
        ("investment-grade-benchmarks",),
        "Clean investment-grade baseline issuer for leverage, coverage, and spread comparison.",
        None,
    ),
    Candidate(
        "JNJ",
        "Johnson & Johnson",
        ("investment-grade-benchmarks",),
        "Clean investment-grade baseline issuer for leverage, coverage, and spread comparison.",
        None,
    ),
    Candidate(
        "JPM",
        "JPMorgan Chase",
        ("investment-grade-benchmarks",),
        "Clean investment-grade baseline issuer for leverage, coverage, and spread comparison.",
        None,
    ),
    Candidate(
        "COST",
        "Costco Wholesale",
        ("investment-grade-benchmarks",),
        "Clean investment-grade baseline issuer for leverage, coverage, and spread comparison.",
        None,
    ),
    # Added after the first live run: RAD/MNK/YELL/BIG/FYBR/SAVE genuinely
    # have no current SEC ticker (confirmed via a direct live name search,
    # not just the primary ticker lookup) — real delistings after
    # bankruptcy, not a resolution bug. These five replace/supplement that
    # gap with other real, currently-active, well-documented issuers.
    Candidate(
        "COMM",
        "CommScope",
        ("liability-management", "high-yield", "telecom-media"),
        "Completed a below-par debt exchange (an uptiering liability-management "
        "transaction) in 2023 as part of a broader balance-sheet restructuring.",
        None,
    ),
    Candidate(
        "TLN",
        "Talen Energy",
        ("post-emergence", "energy"),
        "Emerged from Chapter 11 bankruptcy in 2023; tracked for post-emergence credit "
        "performance.",
        None,
    ),
    Candidate(
        "SABR",
        "Sabre",
        ("high-yield",),
        "Highly levered travel-technology issuer with below-investment-grade public debt.",
        None,
    ),
    Candidate(
        "IHRT",
        "iHeartMedia",
        ("liability-management", "high-yield", "telecom-media"),
        "Highly levered radio broadcaster with documented debt-exchange/liability-"
        "management activity in 2024.",
        None,
    ),
    Candidate(
        "AAL",
        "American Airlines Group",
        ("high-yield", "transportation"),
        "Highly levered legacy airline carrying substantial pandemic-era debt with "
        "below-investment-grade public debt.",
        None,
    ),
)


def main() -> int:
    settings = get_settings()
    if SessionLocal is None:
        print("ERROR: DATABASE_URL is not configured.", file=sys.stderr)
        return 1
    if not settings.sec_user_agent:
        print("ERROR: SEC_USER_AGENT is not configured.", file=sys.stderr)
        return 1

    http_client = ThrottledHttpClient(user_agent=settings.sec_user_agent)
    db = SessionLocal()

    accepted: dict[str, str] = {}  # ticker -> issuer legal name
    rejected: dict[str, str] = {}  # ticker -> reason
    issuer_ids_by_ticker: dict[str, str] = {}  # ticker -> issuer.id (str form of UUID)

    try:
        print(f"Fetching SEC company_tickers.json ({len(_CANDIDATES)} candidates to resolve)...")
        ticker_map = fetch_sec_ticker_map(http_client)

        for candidate in _CANDIDATES:
            result = resolve_issuer_identity_by_ticker_or_name(
                db, http_client, ticker_map, ticker=candidate.ticker, name_hint=candidate.name_hint
            )
            if (
                result.outcome
                not in (
                    MarketDiscoveryResolutionOutcome.MATCHED_EXISTING,
                    MarketDiscoveryResolutionOutcome.VERIFIED_NEW,
                )
                or result.issuer_id is None
            ):
                rejected[candidate.ticker] = result.reason
                print(f"  REJECTED {candidate.ticker} ({candidate.name_hint}): {result.reason}")
                continue

            db.commit()
            accepted[candidate.ticker] = result.legal_name or ""
            issuer_ids_by_ticker[candidate.ticker] = result.issuer_id
            status = (
                "ingested"
                if result.outcome == MarketDiscoveryResolutionOutcome.VERIFIED_NEW
                else "already existed (idempotent skip)"
            )
            print(
                f"  ACCEPTED {candidate.ticker} -> {result.legal_name} "
                f"(CIK {result.cik}, {status})"
            )

        print(
            f"\nResolution complete: {len(accepted)} accepted, {len(rejected)} rejected "
            f"of {len(_CANDIDATES)} candidates."
        )

        print("\nCreating Research Universes...")
        now = datetime.now(UTC)
        for universe_def in _UNIVERSES:
            existing = collection_repository.get_collection_by_slug(db, universe_def.slug)
            if existing is not None:
                collection = existing
                print(f"  EXISTS  {universe_def.name} (slug={universe_def.slug})")
                # Milestone 7.5 self-heal: these 15 universes are each a
                # hand-picked, individually-rationale'd candidate list — that
                # is MANUAL_CURATED, not SYSTEM_SEEDED (the value the
                # original Milestone 6.5 script used, before that
                # distinction was meaningful). See
                # `collection_repository.update_curation_method`.
                if collection.curation_method != CurationMethod.MANUAL_CURATED:
                    collection = collection_repository.update_curation_method(
                        db, collection.id, CurationMethod.MANUAL_CURATED
                    )
                    db.commit()
                    print("          corrected curation_method -> manual_curated")
            else:
                collection = collection_repository.create_collection(
                    db,
                    CollectionCreate(
                        slug=universe_def.slug,
                        name=universe_def.name,
                        description=universe_def.description,
                        collection_type=universe_def.collection_type,
                        scope=CollectionScope.ORGANIZATION,
                        visibility=CollectionVisibility.PUBLIC,
                        curation_method=CurationMethod.MANUAL_CURATED,
                        verification_status=VerificationStatus.VERIFIED,
                        last_verified_at=now,
                        priority=universe_def.priority,
                        verification_count=1,
                        last_refresh_source="seed_research_universes_script",
                    ),
                )
                db.commit()
                print(f"  CREATED {universe_def.name} (slug={universe_def.slug})")

            member_count = 0
            for candidate in _CANDIDATES:
                if universe_def.slug not in candidate.universes:
                    continue
                if candidate.ticker not in issuer_ids_by_ticker:
                    continue
                membership, membership_created = collection_repository.add_membership(
                    db,
                    CollectionMembershipCreate(
                        collection_id=collection.id,
                        issuer_id=UUID(issuer_ids_by_ticker[candidate.ticker]),
                        rationale=candidate.rationale,
                        rationale_as_of_date=(
                            datetime.fromisoformat(candidate.rationale_as_of_date).date()
                            if candidate.rationale_as_of_date
                            else None
                        ),
                        verification_status=VerificationStatus.VERIFIED,
                        added_by="seed_research_universes_script",
                        system_seeded=True,
                    ),
                )
                db.commit()
                member_count += 1
            print(f"          {member_count} member(s)")

        print("\n=== Summary ===")
        print(f"Universes: {len(_UNIVERSES)}")
        print(f"Unique issuers accepted: {len(accepted)}")
        print(f"Candidates rejected: {len(rejected)}")
        if rejected:
            print("Rejected candidates and reasons:")
            for ticker, reason in rejected.items():
                print(f"  - {ticker}: {reason}")
        return 0
    finally:
        db.close()
        http_client.close()


if __name__ == "__main__":
    sys.exit(main())
