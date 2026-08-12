"""Universal Search orchestration (PLAN.md 4.13, 8; Milestone 12A).

Assembles `search_repository`'s per-entity-type `SearchHit`s into the
API's grouped `SearchResponse`. Group order is fixed (issuer first, per
the "issuer-first ranking where appropriate" requirement) — it is
structural, not score-driven, so there is no need to normalize
`ts_rank_cd` scores across tables with different tsvector configurations
(a real problem this design deliberately sidesteps: rank is only ever
compared *within* one entity type's own results, never across types).

A result already shown in `exact_matches` (Tier 0) is excluded from its
own group below, so nothing appears twice on the same page.
"""

from __future__ import annotations

from typing import Protocol

from sqlalchemy.orm import Session

from app.core.types import SearchEntityType
from app.repositories import search_repository
from app.repositories.search_repository import SearchHit
from app.schemas.search import SearchResponse, SearchResultGroup, SearchResultItem


class _SearchFn(Protocol):
    def __call__(self, db: Session, query: str, *, limit: int) -> list[SearchHit]: ...


# Fixed, issuer-first group order — not derived from any per-result score.
_GROUP_FUNCTIONS: list[tuple[SearchEntityType, _SearchFn]] = [
    (SearchEntityType.ISSUER, search_repository.search_issuers),
    (SearchEntityType.SECURITY, search_repository.search_securities),
    (SearchEntityType.ALERT_EVENT, search_repository.search_alerts),
    (SearchEntityType.COURT_DOCKET, search_repository.search_court_dockets),
    (SearchEntityType.COURT_DOCKET_ENTRY, search_repository.search_court_docket_entries),
    (SearchEntityType.COLLECTION, search_repository.search_collections),
    (SearchEntityType.RESEARCH_NOTE, search_repository.search_research_notes),
    (SearchEntityType.SEC_FILING, search_repository.search_sec_filings),
]


def search(db: Session, query: str, *, per_group_limit: int = 5) -> SearchResponse:
    q = query.strip()
    if not q:
        return SearchResponse(query=query, exact_matches=[], groups=[])

    exact_hits = search_repository.search_exact_matches(db, q, limit=per_group_limit)
    exact_keys = {(hit.entity_type, hit.entity_id) for hit in exact_hits}

    groups: list[SearchResultGroup] = []
    for entity_type, fn in _GROUP_FUNCTIONS:
        hits = fn(db, q, limit=per_group_limit)
        hits = [h for h in hits if (h.entity_type, h.entity_id) not in exact_keys]
        if hits:
            groups.append(
                SearchResultGroup(
                    entity_type=entity_type,
                    results=[SearchResultItem.from_hit(h) for h in hits],
                )
            )

    return SearchResponse(
        query=q,
        exact_matches=[SearchResultItem.from_hit(h) for h in exact_hits],
        groups=groups,
    )
