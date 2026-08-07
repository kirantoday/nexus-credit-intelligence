"""Response schema for the Issuer Detail API.

The Issuer Detail workspace (PLAN.md section 18 step 6, per Milestone 6's
brief) is organized around how a distressed-credit analyst actually thinks
about a company, not around database tables: what debt exists (`securities`,
plus the Capital Structure API for "which instrument sits where"), what
filings support this (`financial_facts`), where did this information come
from (`data_sources`), and what changed recently (`recent_activity`). Every
row still carries its own provenance/freshness — this schema aggregates
several repositories' worth of already-provenanced facts, it never
introduces a new unprovenanced one.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.core.freshness import FreshnessTier
from app.core.types import (
    DataClassification,
    FormType,
    InstrumentType,
    ProviderName,
    Seniority,
    TransformationType,
)
from app.schemas.court_docket import CourtDocketRow
from app.schemas.research_universe import IssuerUniverseMembership


class IssuerSecurityRow(BaseModel):
    """What debt exists, and what's secured/unsecured — one row per `security`."""

    model_config = ConfigDict(frozen=True)

    security_id: UUID
    instrument_type: InstrumentType
    description: str
    seniority: Seniority | None
    lien_position: str | None
    secured: bool | None
    cusip: str | None
    isin: str | None
    figi: str | None
    maturity_date: date | None
    coupon: Decimal | None
    amount_outstanding: Decimal | None
    benchmark: str | None
    spread: Decimal | None
    is_synthetic: bool
    synthetic_reason: str | None
    provider: ProviderName
    classification: DataClassification
    transformation: TransformationType
    as_of_date: date
    retrieved_at: datetime
    freshness: FreshnessTier


class IssuerFinancialFactRow(BaseModel):
    """What filings support this — one row per `financial_fact`."""

    model_config = ConfigDict(frozen=True)

    financial_fact_id: UUID
    concept: str
    value: Decimal
    unit: str
    fiscal_period: str
    fiscal_year: int
    form_type: FormType
    filing_date: date
    accession_no: str
    provider: ProviderName
    classification: DataClassification
    as_of_date: date
    retrieved_at: datetime
    freshness: FreshnessTier
    source_url: str | None


class IssuerDataSource(BaseModel):
    """Where did this information come from — one row per distinct provider
    touching this issuer (its own identity record, any security, any
    financial fact, any capital structure position)."""

    model_config = ConfigDict(frozen=True)

    provider: ProviderName
    record_count: int
    latest_retrieved_at: datetime


class IssuerActivityItem(BaseModel):
    """What changed recently — a computed read over already-provenanced
    records' own dates, sorted newest first (never a new `credit_event`
    table; PLAN.md section 23.1 explicitly keeps that out of Version 1)."""

    model_config = ConfigDict(frozen=True)

    occurred_on: date
    category: Literal["filing", "security_identified", "capital_structure_update"]
    headline: str
    provider: ProviderName
    source_url: str | None
    as_of_date: date


class IssuerDetail(BaseModel):
    model_config = ConfigDict(frozen=True)

    issuer_id: UUID
    legal_name: str
    cik: str | None
    lei: str | None
    ticker: str | None
    sic: str | None
    sector: str | None
    is_synthetic: bool
    synthetic_reason: str | None
    securities: list[IssuerSecurityRow]
    financial_facts: list[IssuerFinancialFactRow]
    data_sources: list[IssuerDataSource]
    recent_activity: list[IssuerActivityItem]
    # Milestone 6.5 (PLAN.md 24.9) — curated Research Universe/Watchlist/
    # Benchmark membership, clearly separate from the factual-status
    # sections above: membership is a coverage decision, never itself a
    # current-status assertion (PLAN.md 24.1).
    universe_memberships: list[IssuerUniverseMembership]
    # Milestone 7 — real, linked CourtListener dockets for this issuer
    # ("what happened in court?"), empty for the common case of an issuer
    # with no known bankruptcy/litigation docket on file.
    court_dockets: list[CourtDocketRow]
