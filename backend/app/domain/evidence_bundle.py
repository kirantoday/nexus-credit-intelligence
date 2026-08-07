"""Evidence Bundle — internal grouping concept, not a persisted table (PLAN.md 24.3, ADR-018).

Groups `ResearchEvidence` for one issuer into the unit that becomes a single
`alert_event`. Today this means "one bundle per filing" (the only real
grouping key that exists), but `group_evidence_into_bundles` has no
SEC-specific logic in it — a future milestone can change the grouping key
(e.g. same issuer + overlapping time window across two providers) without
touching the alert-synthesis code downstream, which only ever sees
`EvidenceBundle` objects.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.domain.research_evidence import ResearchEvidence


class EvidenceBundle(BaseModel):
    """One or more `ResearchEvidence` records grouped for a single alert."""

    model_config = ConfigDict(frozen=True)

    issuer_id: UUID
    bundle_key: str
    evidence: tuple[ResearchEvidence, ...]

    @property
    def primary_evidence(self) -> ResearchEvidence:
        """The evidence item used to build the alert's headline/source label.

        Highest severity first, then earliest-created, so the bundle's
        headline reflects its most serious signal rather than an arbitrary
        one.
        """
        severity_rank = {"high": 0, "medium": 1, "low": 2}
        return sorted(
            self.evidence,
            key=lambda e: (severity_rank.get(e.severity.value, 3), e.created_at),
        )[0]


def _source_key(item: ResearchEvidence) -> str:
    """Each provider's own concrete source pointer (`filing_id` for SEC EDGAR,
    `docket_entry_id` for CourtListener) — checked in a fixed, provider-neutral
    order, exactly the "a future evidence source contributes its own key
    component" extension this function's docstring already anticipated
    before Milestone 7 existed."""
    if item.filing_id is not None:
        return str(item.filing_id)
    if item.docket_entry_id is not None:
        return str(item.docket_entry_id)
    return "none"


def group_evidence_into_bundles(evidence: list[ResearchEvidence]) -> list[EvidenceBundle]:
    """Group evidence into bundles keyed by (issuer, provider, source_type, source).

    Today `filing_id`/`docket_entry_id` are the only real source-specific
    keys, so this produces one bundle per filing or per docket entry. The
    grouping key itself is generic — a future evidence source contributes
    its own key component (`_source_key`) without changing this function's
    shape.
    """
    groups: dict[tuple[UUID, str, str, str], list[ResearchEvidence]] = {}
    for item in evidence:
        key = (item.issuer_id, item.evidence_provider, item.source_type, _source_key(item))
        groups.setdefault(key, []).append(item)

    bundles: list[EvidenceBundle] = []
    for (issuer_id, provider, source_type, source_key), items in groups.items():
        bundle_key = f"{provider}:{source_type}:{source_key}"
        bundles.append(
            EvidenceBundle(issuer_id=issuer_id, bundle_key=bundle_key, evidence=tuple(items))
        )
    return bundles
