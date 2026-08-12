"""Request/response schemas for Universal Search (PLAN.md 4.13, 8;
Milestone 12A).
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.core.types import SearchEntityType
from app.repositories.search_repository import SearchHit


class SearchResultItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    entity_type: SearchEntityType
    entity_id: UUID
    title: str
    snippet: str | None
    issuer_id: UUID | None
    collection_type: str | None
    context_date: date | None
    matched_field: str | None

    @staticmethod
    def from_hit(hit: SearchHit) -> SearchResultItem:
        return SearchResultItem(
            entity_type=hit.entity_type,
            entity_id=hit.entity_id,
            title=hit.title,
            snippet=hit.snippet,
            issuer_id=hit.issuer_id,
            collection_type=hit.collection_type,
            context_date=hit.context_date,
            matched_field=hit.matched_field,
        )


class SearchResultGroup(BaseModel):
    model_config = ConfigDict(frozen=True)

    entity_type: SearchEntityType
    results: list[SearchResultItem]


class SearchResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    query: str
    exact_matches: list[SearchResultItem]
    groups: list[SearchResultGroup]
