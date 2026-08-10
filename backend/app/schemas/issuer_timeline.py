"""Response schema for the Issuer Distress Timeline (PLAN.md Milestone 7.5.4).

Built entirely from already-persisted, already-classified `alert_event` rows
— never a new `credit_event` table, never a raw filing log. Each
`alert_event` already represents one meaningful, deterministic-or-AI-
reviewed distress signal (ADR-018); this schema's job is purely to collapse
same-day/same-category duplicates across providers into one narrative
milestone and present it chronologically, reusing each alert's own
`headline`/`explanation` wording rather than inventing new copy.
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.core.types import EvidenceSeverity


class TimelineSource(BaseModel):
    """One alert's own source citation — reused verbatim from `alert_event`."""

    model_config = ConfigDict(frozen=True)

    provider: str
    label: str
    url: str | None


class TimelineEvent(BaseModel):
    """One collapsed narrative milestone — one or more same-day,
    same-category `alert_event` rows describing the same real-world event."""

    model_config = ConfigDict(frozen=True)

    event_date: date
    event_type: str
    title: str
    short_summary: str
    why_it_matters: str
    severity: EvidenceSeverity
    confidence: float | None
    primary_source: TimelineSource
    supporting_sources: list[TimelineSource]
    is_historical_discovery: bool
    evidence_count: int


class IssuerTimeline(BaseModel):
    model_config = ConfigDict(frozen=True)

    issuer_id: UUID
    events: list[TimelineEvent]
    total_events: int
    date_range_start: date | None
    date_range_end: date | None
    # Names of Research Universes this issuer currently belongs to — an
    # honest, already-derived read of existing membership state (PLAN.md
    # 24.1), never a fabricated "status" the timeline computes on its own.
    current_status: list[str]
    most_recent_event_title: str | None
