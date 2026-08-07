"""Canonical domain objects for `market_discovery_run` / `market_discovery_candidate`
(PLAN.md Milestone 7.5).

`MarketDiscoveryRunCreate` starts a run (mirrors `FilingMonitorRunCreate`);
the repository's `complete_run` takes closing counts directly, same pattern
as `filing_monitor_run_repository`.

`MarketDiscoveryCandidateCreate`/`MarketDiscoveryCandidate` record one
`(cik, accession_no)` full-text-search hit's resolution outcome.
`rule_version` is what keeps historical reprocessing possible without
duplicating rows — see the ORM model's docstring for the full rationale.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.core.types import (
    FilingMonitorRunMode,
    FilingMonitorRunStatus,
    MarketDiscoveryResolutionOutcome,
)


class MarketDiscoveryRunCreate(BaseModel):
    """Everything needed to start a `market_discovery_run` row."""

    model_config = ConfigDict(frozen=True)

    mode: FilingMonitorRunMode
    window_start_date: date
    window_end_date: date
    previous_watermark: datetime | None = None


class MarketDiscoveryRun(BaseModel):
    """A persisted `market_discovery_run` row."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    started_at: datetime
    completed_at: datetime | None
    status: FilingMonitorRunStatus
    mode: FilingMonitorRunMode
    window_start_date: date
    window_end_date: date
    previous_watermark: datetime | None
    resulting_watermark: datetime | None
    queries_executed: int
    filings_examined: int
    candidate_filings: int
    issuers_resolved_existing: int
    issuers_resolved_new: int
    issuers_ambiguous: int
    issuers_rejected: int
    evidence_created: int
    alerts_created: int
    errors_count: int
    error_summary: str | None
    created_at: datetime


class MarketDiscoveryCandidateCreate(BaseModel):
    """Everything needed to create/update a `market_discovery_candidate` row."""

    model_config = ConfigDict(frozen=True)

    discovery_run_id: UUID
    cik: str
    accession_no: str
    form_type: str
    file_date: date
    matched_query: str
    sec_items: list[str] | None = None
    resolution_outcome: MarketDiscoveryResolutionOutcome
    resolution_reason: str
    issuer_id: UUID | None = None
    layer1_matched: bool = False
    evidence_created: bool = False
    provenance_id: UUID | None = None
    rule_version: str


class MarketDiscoveryCandidate(MarketDiscoveryCandidateCreate):
    """A persisted `market_discovery_candidate` row."""

    id: UUID
    created_at: datetime
    updated_at: datetime
