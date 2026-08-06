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


def group_evidence_into_bundles(evidence: list[ResearchEvidence]) -> list[EvidenceBundle]:
    """Group evidence into bundles keyed by (issuer, provider, source_type, source).

    Today `filing_id` is the only real source-specific key, so this produces
    one bundle per filing. The grouping key itself is generic — a future
    evidence source contributes its own key component without changing this
    function's shape.
    """
    groups: dict[tuple[UUID, str, str, str], list[ResearchEvidence]] = {}
    for item in evidence:
        source_key = str(item.filing_id) if item.filing_id is not None else "none"
        key = (item.issuer_id, item.evidence_provider, item.source_type, source_key)
        groups.setdefault(key, []).append(item)

    bundles: list[EvidenceBundle] = []
    for (issuer_id, provider, source_type, source_key), items in groups.items():
        bundle_key = f"{provider}:{source_type}:{source_key}"
        bundles.append(
            EvidenceBundle(issuer_id=issuer_id, bundle_key=bundle_key, evidence=tuple(items))
        )
    return bundles
