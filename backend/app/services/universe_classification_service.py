"""Evidence-driven Research Universe classification (PLAN.md Milestone 7.5
section 14).

Separates objective evidence from classification, per the milestone's
explicit rule: "do not automatically call every candidate distressed."
Where evidence is definitive (a verified Chapter 11 filing, a confirmed
plan of reorganization), automatic `verified` membership is reasonable.
Weaker or more ambiguous evidence produces a `partial` (system-suggested)
membership instead — visible, but explicitly flagged as needing analyst
confirmation, never silently promoted to a settled fact. Membership is
never *downgraded* automatically (`collection_repository
.upgrade_membership_verification`) — only strengthened as more evidence
accumulates.

These evidence-driven collections are distinct from the 15 Milestone 6.5
Research Universes (`app.scripts.seed_research_universes`,
`curation_method=manual_curated` after the Milestone 7.5 correction — see
that script's docstring): those are hand-picked candidate lists; these are
populated with no human-selected candidate list at all, purely from
`research_evidence`. Both are legitimate, coexisting concepts (PLAN.md
Milestone 7.5 section 15) — this module never touches the curated ones.
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.types import (
    CollectionPriority,
    CollectionScope,
    CollectionType,
    CollectionVisibility,
    CurationMethod,
    EvidenceSeverity,
    EvidenceType,
    VerificationStatus,
)
from app.domain.collection import Collection, CollectionCreate, CollectionMembershipCreate
from app.domain.research_evidence import ResearchEvidence
from app.repositories import collection_repository

# Every slug/name below is deliberately prefixed `system-`/"System-Detected:"
# — Milestone 6.5's 15 curated universes (`app.scripts.seed_research_universes`)
# already used several of the same natural names (`distressed-core`,
# `post-emergence`, `liability-management`, `refinancing-risk`), discovered
# live the first time this module's seed function ran (it silently found
# and reused the *existing curated* collections for those four slugs
# instead of creating new ones, which would have mixed automatic,
# unreviewed memberships into hand-curated, analyst-rationale'd universes
# — a real bug, caught before any live membership was ever written). The
# prefix guarantees no collision with any curated slug now or later, and
# makes the UI distinction between "an analyst put this issuer here" and
# "the system detected this issuer" impossible to miss.

# Definitive evidence: automatic `verified` membership, but only at HIGH
# severity — a low-confidence/bare mention of these same evidence types
# must not auto-classify (PLAN.md: "do not automatically call every
# candidate distressed").
_DEFINITIVE_EVIDENCE_TO_UNIVERSE_SLUG: dict[EvidenceType, str] = {
    EvidenceType.CHAPTER_11: "system-chapter-11",
    EvidenceType.BANKRUPTCY_OR_RECEIVERSHIP: "system-chapter-11",
    EvidenceType.PLAN_CONFIRMED: "system-post-emergence",
}

# Suggestive evidence: `partial` (system-suggested) membership at HIGH or
# MEDIUM severity — an analyst confirms before it becomes a settled fact.
_SUGGESTIVE_EVIDENCE_TO_UNIVERSE_SLUG: dict[EvidenceType, str] = {
    EvidenceType.GOING_CONCERN: "system-going-concern",
    EvidenceType.SUBSTANTIAL_DOUBT: "system-going-concern",
    EvidenceType.DEFAULT_OR_MISSED_PAYMENT: "system-default-covenant-stress",
    EvidenceType.COVENANT_BREACH: "system-default-covenant-stress",
    EvidenceType.DEBT_ACCELERATION: "system-default-covenant-stress",
    EvidenceType.LIABILITY_MANAGEMENT_TRANSACTION: "system-liability-management",
    EvidenceType.EXCHANGE_OFFER: "system-liability-management",
    EvidenceType.RESTRUCTURING_SUPPORT_AGREEMENT: "system-liability-management",
    EvidenceType.REFINANCING: "system-refinancing-risk",
    EvidenceType.MATURITY_EXTENSION: "system-refinancing-risk",
    EvidenceType.DEBT_AMENDMENT: "system-refinancing-risk",
    EvidenceType.STRATEGIC_ALTERNATIVES: "system-restructuring-strategic-alternatives",
    EvidenceType.RESTRUCTURING_ADVISOR: "system-restructuring-strategic-alternatives",
    EvidenceType.DIP_FINANCING: "system-restructuring-strategic-alternatives",
    EvidenceType.EMERGENCY_FINANCING: "system-restructuring-strategic-alternatives",
}

_DISTRESSED_CORE_SLUG = "system-distressed-core"

# Evidence-driven universe definitions seeded once, idempotently — no
# candidate list, membership populated only by `classify_issuer`.
# "Upcoming Maturity Wall" is deliberately excluded: it would require a
# real security-level maturity-date rule this milestone does not build
# (Credit Universe's "no fabricated completeness" rule, PLAN.md Milestone
# 7.5 section 18, applies equally to which universes get auto-populated).
_EVIDENCE_DRIVEN_UNIVERSES: tuple[tuple[str, str, str, CollectionPriority], ...] = (
    (
        _DISTRESSED_CORE_SLUG,
        "System-Detected: Distressed Core",
        "Issuers with at least one verified or system-suggested distress "
        "signal from real provider evidence — the broadest evidence-driven "
        "grouping, populated automatically, never by a hand-picked list.",
        CollectionPriority.HIGH,
    ),
    (
        "system-chapter-11",
        "System-Detected: Chapter 11",
        "Issuers with a verified Chapter 11 / bankruptcy-or-receivership " "filing on record.",
        CollectionPriority.CRITICAL,
    ),
    (
        "system-post-emergence",
        "System-Detected: Post-Emergence",
        "Issuers with a verified confirmed plan of reorganization on record.",
        CollectionPriority.MEDIUM,
    ),
    (
        "system-going-concern",
        "System-Detected: Going Concern",
        "Issuers with going-concern or substantial-doubt language identified "
        "in real SEC filings — system-suggested, pending analyst confirmation.",
        CollectionPriority.HIGH,
    ),
    (
        "system-default-covenant-stress",
        "System-Detected: Default / Covenant Stress",
        "Issuers with missed-payment, covenant-breach, or debt-acceleration "
        "evidence — system-suggested, pending analyst confirmation.",
        CollectionPriority.HIGH,
    ),
    (
        "system-liability-management",
        "System-Detected: Liability Management",
        "Issuers with exchange-offer, restructuring-support-agreement, or "
        "liability-management-transaction evidence — system-suggested.",
        CollectionPriority.MEDIUM,
    ),
    (
        "system-refinancing-risk",
        "System-Detected: Refinancing Risk",
        "Issuers with refinancing, maturity-extension, or debt-amendment "
        "evidence — system-suggested, pending analyst confirmation.",
        CollectionPriority.MEDIUM,
    ),
    (
        "system-restructuring-strategic-alternatives",
        "System-Detected: Restructuring / Strategic Alternatives",
        "Issuers reviewing strategic alternatives, engaging a restructuring "
        "advisor, or securing DIP/emergency financing — system-suggested.",
        CollectionPriority.MEDIUM,
    ),
)


def seed_evidence_driven_universes(db: Session) -> list[Collection]:
    """Idempotent: creates each evidence-driven collection if it doesn't
    already exist, `curation_method=system_seeded` (distinct from the 15
    Milestone 6.5 curated universes' `manual_curated`, post-correction).
    Safe to call on every run — existing collections are returned as-is.

    Raises if an existing collection at one of these slugs is not itself
    `system_seeded` — a real bug this guard exists specifically to catch
    early: an earlier version of this module's slugs (`distressed-core`,
    `post-emergence`, `liability-management`, `refinancing-risk`) collided
    with pre-existing Milestone 6.5 *curated* universe slugs, silently
    reusing them, which would have mixed unreviewed automatic memberships
    into hand-curated, analyst-rationale'd universes had `classify_issuer`
    ever run against them before the collision was caught (it was caught
    before any live membership was written — see the module-level comment
    above `_DEFINITIVE_EVIDENCE_TO_UNIVERSE_SLUG` for the full story).
    """
    collections: list[Collection] = []
    for slug, name, description, priority in _EVIDENCE_DRIVEN_UNIVERSES:
        existing = collection_repository.get_collection_by_slug(db, slug)
        if existing is not None:
            if existing.curation_method is not CurationMethod.SYSTEM_SEEDED:
                raise ValueError(
                    f"evidence-driven universe slug {slug!r} collides with an existing "
                    f"{existing.curation_method.value} collection ({existing.name!r}) — "
                    "refusing to reuse it; pick a different slug"
                )
            collections.append(existing)
            continue
        collections.append(
            collection_repository.create_collection(
                db,
                CollectionCreate(
                    slug=slug,
                    name=name,
                    description=description,
                    collection_type=CollectionType.RESEARCH_UNIVERSE,
                    scope=CollectionScope.ORGANIZATION,
                    visibility=CollectionVisibility.PUBLIC,
                    curation_method=CurationMethod.SYSTEM_SEEDED,
                    verification_status=VerificationStatus.UNVERIFIED,
                    priority=priority,
                    last_refresh_source="universe_classification_service",
                ),
            )
        )
    return collections


def _rationale(evidence: ResearchEvidence) -> str:
    return (
        f"System-classified from {evidence.evidence_provider} evidence "
        f"({evidence.evidence_type.value}, {evidence.severity.value} severity, "
        f"rule {evidence.matched_rule}): “{evidence.evidence_excerpt[:200]}”"
    )


def _upsert_membership(
    db: Session,
    *,
    universe_slug: str,
    issuer_id: UUID,
    verification_status: VerificationStatus,
    evidence: ResearchEvidence,
    as_of_date: date | None,
) -> None:
    collection = collection_repository.get_collection_by_slug(db, universe_slug)
    if collection is None:
        # Universes are seeded once at startup/migration time
        # (`seed_evidence_driven_universes`); a missing slug here means
        # that hasn't run yet — nothing to classify into, not an error.
        return

    existing = collection_repository.get_membership(db, collection.id, issuer_id)
    if existing is None:
        collection_repository.add_membership(
            db,
            CollectionMembershipCreate(
                collection_id=collection.id,
                issuer_id=issuer_id,
                rationale=_rationale(evidence),
                rationale_as_of_date=as_of_date,
                verification_status=verification_status,
                supporting_provenance_ids=[evidence.provenance_id],
                added_by="universe_classification_service",
                system_seeded=True,
            ),
        )
        return

    collection_repository.upgrade_membership_verification(
        db,
        collection.id,
        issuer_id,
        verification_status=verification_status,
        rationale=_rationale(evidence),
        rationale_as_of_date=as_of_date,
        supporting_provenance_ids=[evidence.provenance_id],
    )


def classify_issuer(
    db: Session,
    issuer_id: UUID,
    evidence: list[ResearchEvidence],
    *,
    as_of_date: date | None = None,
) -> None:
    """Classifies one issuer into evidence-driven Research Universes based
    on newly-created `research_evidence` rows. Called from
    `market_discovery_service` right after evidence creation — never
    retroactively re-scans an issuer's full evidence history on its own
    (a caller wanting that re-classifies explicitly by passing that
    issuer's full evidence list).
    """
    any_qualifying = False
    best_qualifying_status = VerificationStatus.PARTIAL

    for item in evidence:
        if item.evidence_type in _DEFINITIVE_EVIDENCE_TO_UNIVERSE_SLUG and item.severity is (
            EvidenceSeverity.HIGH
        ):
            slug = _DEFINITIVE_EVIDENCE_TO_UNIVERSE_SLUG[item.evidence_type]
            _upsert_membership(
                db,
                universe_slug=slug,
                issuer_id=issuer_id,
                verification_status=VerificationStatus.VERIFIED,
                evidence=item,
                as_of_date=as_of_date,
            )
            any_qualifying = True
            best_qualifying_status = VerificationStatus.VERIFIED
        elif item.evidence_type in _SUGGESTIVE_EVIDENCE_TO_UNIVERSE_SLUG and item.severity in (
            EvidenceSeverity.HIGH,
            EvidenceSeverity.MEDIUM,
        ):
            slug = _SUGGESTIVE_EVIDENCE_TO_UNIVERSE_SLUG[item.evidence_type]
            _upsert_membership(
                db,
                universe_slug=slug,
                issuer_id=issuer_id,
                verification_status=VerificationStatus.PARTIAL,
                evidence=item,
                as_of_date=as_of_date,
            )
            any_qualifying = True

    if any_qualifying:
        strongest_evidence = max(
            (
                e
                for e in evidence
                if e.evidence_type in _DEFINITIVE_EVIDENCE_TO_UNIVERSE_SLUG
                or e.evidence_type in _SUGGESTIVE_EVIDENCE_TO_UNIVERSE_SLUG
            ),
            key=lambda e: {"high": 2, "medium": 1, "low": 0}[e.severity.value],
        )
        _upsert_membership(
            db,
            universe_slug=_DISTRESSED_CORE_SLUG,
            issuer_id=issuer_id,
            verification_status=best_qualifying_status,
            evidence=strongest_evidence,
            as_of_date=as_of_date,
        )
