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
from app.domain.alert import AlertEvent
from app.domain.collection import Collection, CollectionCreate, CollectionMembershipCreate
from app.domain.evidence_bundle import group_evidence_into_bundles
from app.domain.research_evidence import ResearchEvidence
from app.repositories import alert_repository, collection_repository

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


def definitive_evidence_types() -> list[EvidenceType]:
    """The evidence types that can drive automatic `verified` membership —
    exposed for `app.scripts.reclassify_system_universes`, which needs to
    find every issuer with this specific kind of evidence to backfill
    `alert_event.issuer_is_subject` for pre-Milestone-7.5.1 rows."""
    return list(_DEFINITIVE_EVIDENCE_TO_UNIVERSE_SLUG)


def classification_relevant_evidence_types() -> list[EvidenceType]:
    """Every evidence type `compute_expected_memberships` looks at (both
    definitive and suggestive) — exposed for
    `app.scripts.reclassify_system_universes` to find every issuer whose
    memberships might need recomputing."""
    return list(_DEFINITIVE_EVIDENCE_TO_UNIVERSE_SLUG) + list(_SUGGESTIVE_EVIDENCE_TO_UNIVERSE_SLUG)


def evidence_driven_universe_slugs() -> list[tuple[str, str]]:
    """`(slug, name)` for each of the 8 evidence-driven collections —
    exposed read-only for `app.scripts.reclassify_system_universes`'s
    `--dry-run` preview, which must not import `_EVIDENCE_DRIVEN_UNIVERSES`
    directly."""
    return [(slug, name) for slug, name, _description, _priority in _EVIDENCE_DRIVEN_UNIVERSES]


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


def effective_reviews(
    db: Session, evidence: list[ResearchEvidence]
) -> dict[UUID, tuple[EvidenceSeverity, bool | None]]:
    """Resolves each evidence item's *effective* severity and
    issuer-is-subject signal from the AI-reviewed alert that already covers
    it, not the raw Layer-1 deterministic severity alone.

    Milestone 7.5.1 root cause: Layer 1's deterministic rules match a phrase
    ("chapter 11", "event of default") with no concept of *whose* event it
    describes — a bare regex match scores identically whether an excerpt
    reports the issuer's own bankruptcy or a director's former employer's,
    a customer's, or generic contract boilerplate. The Layer 2 AI review
    already resolves this correctly (it reads the excerpt in context), and
    already produces a cautious, evidence-grounded severity for the exact
    same bundle `alert_synthesis_service` turns into an alert — this
    function is what lets classification stop re-deriving a cruder signal
    from Layer 1 alone and instead reuse that already-computed judgment.
    Evidence whose bundle has no alert on file yet (a caller invoking this
    ahead of alert synthesis, or a bundle synthesis skipped for some reason)
    falls back to the item's own Layer-1 severity with an unknown
    issuer-is-subject signal — the exact pre-Milestone-7.5.1 behavior, never
    a hard failure.
    """
    resolved: dict[UUID, tuple[EvidenceSeverity, bool | None]] = {}
    for bundle in group_evidence_into_bundles(evidence):
        alert: AlertEvent | None = alert_repository.get_alert_by_bundle_key(db, bundle.bundle_key)
        for item in bundle.evidence:
            if alert is not None:
                resolved[item.id] = (alert.severity, alert.issuer_is_subject)
            else:
                resolved[item.id] = (item.severity, None)
    return resolved


_SEVERITY_RANK = {"high": 2, "medium": 1, "low": 0}
_STATUS_RANK = {VerificationStatus.PARTIAL: 0, VerificationStatus.VERIFIED: 1}


def compute_expected_memberships(
    evidence: list[ResearchEvidence],
    effective: dict[UUID, tuple[EvidenceSeverity, bool | None]],
) -> dict[str, tuple[VerificationStatus, ResearchEvidence]]:
    """Pure classification: given an issuer's evidence and each item's
    *effective* severity/issuer-is-subject signal (`effective_reviews`),
    computes which evidence-driven universes the issuer qualifies for and
    at what verification status — no DB reads or writes, no side effects.

    One entry per qualifying universe slug (the strongest verification
    status across every evidence item that maps to it, with a
    representative evidence item for the membership rationale) — shared by
    both `classify_issuer` (the live, upgrade-only per-call path) and
    `app.scripts.reclassify_system_universes` (the full, idempotent
    rebuild — including downgrades and removals — Milestone 7.5.1 section
    9 requires), so both apply the exact same rules; only how a caller
    *applies* the result differs.
    """
    best: dict[str, tuple[VerificationStatus, ResearchEvidence]] = {}

    def _consider(slug: str, status: VerificationStatus, item: ResearchEvidence) -> None:
        current = best.get(slug)
        if current is None or _STATUS_RANK[status] > _STATUS_RANK[current[0]]:
            best[slug] = (status, item)

    qualifying_evidence: list[ResearchEvidence] = []
    best_qualifying_status = VerificationStatus.PARTIAL

    for item in evidence:
        effective_severity, issuer_is_subject = effective.get(item.id, (item.severity, None))
        if item.evidence_type in _DEFINITIVE_EVIDENCE_TO_UNIVERSE_SLUG and effective_severity is (
            EvidenceSeverity.HIGH
        ):
            slug = _DEFINITIVE_EVIDENCE_TO_UNIVERSE_SLUG[item.evidence_type]
            # A subsidiary/affiliate's (or an unrelated third party's) real
            # bankruptcy is still relevant to the issuer's credit profile —
            # surfaced, never discarded — but must not overclaim that the
            # issuer itself filed (PLAN.md Milestone 7.5.1 section 2).
            # Requires an *explicit* True, not merely "not False": an
            # unconfirmed/unknown attribution (`None` — no AI review ever
            # ran for this bundle, or a re-review attempt failed) must never
            # silently default to `verified` for an objective, high-
            # precision-required category. Chapter 11's own live-verified
            # false-positive patterns (a boilerplate SEC cover-page
            # checkbox, a bundle-mate's unrelated higher-severity evidence)
            # are exactly the cases this closes — an unresolved attribution
            # downgrades to `partial`, the same as a confirmed third party.
            status = (
                VerificationStatus.VERIFIED
                if issuer_is_subject is True
                else VerificationStatus.PARTIAL
            )
            _consider(slug, status, item)
            qualifying_evidence.append(item)
            if status is VerificationStatus.VERIFIED:
                best_qualifying_status = VerificationStatus.VERIFIED
        elif item.evidence_type in _SUGGESTIVE_EVIDENCE_TO_UNIVERSE_SLUG and effective_severity in (
            EvidenceSeverity.HIGH,
            EvidenceSeverity.MEDIUM,
        ):
            slug = _SUGGESTIVE_EVIDENCE_TO_UNIVERSE_SLUG[item.evidence_type]
            _consider(slug, VerificationStatus.PARTIAL, item)
            qualifying_evidence.append(item)

    if qualifying_evidence:
        strongest_evidence = max(
            qualifying_evidence,
            key=lambda e: _SEVERITY_RANK[effective.get(e.id, (e.severity, None))[0].value],
        )
        _consider(_DISTRESSED_CORE_SLUG, best_qualifying_status, strongest_evidence)

    return best


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
    issuer's full evidence list — see `compute_expected_memberships`,
    which this delegates to).

    Gates on each evidence item's *effective* severity — the AI-reviewed
    alert's severity when one exists, falling back to the item's own
    Layer-1 severity otherwise (`effective_reviews`) — not the raw Layer-1
    severity directly, per Milestone 7.5.1's calibration pass: a bare
    deterministic phrase match is a candidate, not a verdict. Upgrade-only
    (`_upsert_membership`) — this live, incremental path never downgrades
    or removes an existing membership; a full correction (needed once,
    to fix memberships this exact bug already wrote before it was found)
    is `app.scripts.reclassify_system_universes`'s job, not this one's.
    """
    effective = effective_reviews(db, evidence)
    expected = compute_expected_memberships(evidence, effective)

    for slug, (status, item) in expected.items():
        _upsert_membership(
            db,
            universe_slug=slug,
            issuer_id=issuer_id,
            verification_status=status,
            evidence=item,
            as_of_date=as_of_date,
        )


def apply_correction(
    db: Session,
    issuer_id: UUID,
    expected: dict[str, tuple[VerificationStatus, ResearchEvidence]],
) -> list[str]:
    """Applies `expected` (from `compute_expected_memberships`, computed
    against an issuer's *full* evidence history and the corrected
    classification rules) as the ground truth for that issuer's
    evidence-driven Research Universe memberships — including downgrades
    and removals `classify_issuer`'s upgrade-only live path never performs.
    Reserved for `app.scripts.reclassify_system_universes`'s controlled,
    auditable correction pass (PLAN.md Milestone 7.5.1 section 9).

    Only ever touches the 8 `system_seeded` evidence-driven collections —
    `expected`'s keys are a closed set of slugs from `_EVIDENCE_DRIVEN_UNIVERSES`,
    and any existing membership found at one of those slugs that is *not*
    `system_seeded` is left completely untouched (should be architecturally
    impossible per `seed_evidence_driven_universes`'s collision guard, but
    checked defensively — an analyst-curated membership is never corrected
    or removed by this function under any circumstance).

    Idempotent and safe to call repeatedly: returns a list of
    human-readable change descriptions, empty when the issuer's current
    memberships already match `expected` exactly.
    """
    changes: list[str] = []
    for slug, name, _description, _priority in _EVIDENCE_DRIVEN_UNIVERSES:
        collection = collection_repository.get_collection_by_slug(db, slug)
        if collection is None:
            continue
        current = collection_repository.get_membership(db, collection.id, issuer_id)
        target = expected.get(slug)

        if target is None:
            if current is not None and current.system_seeded:
                collection_repository.remove_membership(db, collection.id, issuer_id)
                changes.append(f"{name}: removed ({current.verification_status.value} -> none)")
            continue

        status, evidence = target
        if current is None:
            _upsert_membership(
                db,
                universe_slug=slug,
                issuer_id=issuer_id,
                verification_status=status,
                evidence=evidence,
                as_of_date=evidence.created_at.date(),
            )
            changes.append(f"{name}: added ({status.value})")
            continue

        if not current.system_seeded:
            continue

        current_rank = _STATUS_RANK.get(current.verification_status, -1)
        target_rank = _STATUS_RANK[status]
        if target_rank > current_rank:
            _upsert_membership(
                db,
                universe_slug=slug,
                issuer_id=issuer_id,
                verification_status=status,
                evidence=evidence,
                as_of_date=evidence.created_at.date(),
            )
            changes.append(
                f"{name}: upgraded ({current.verification_status.value} -> {status.value})"
            )
        elif target_rank < current_rank:
            collection_repository.set_membership_verification(
                db,
                collection.id,
                issuer_id,
                verification_status=status,
                rationale=_rationale(evidence),
                rationale_as_of_date=evidence.created_at.date(),
                supporting_provenance_ids=[evidence.provenance_id],
            )
            changes.append(
                f"{name}: downgraded ({current.verification_status.value} -> {status.value})"
            )

    return changes
