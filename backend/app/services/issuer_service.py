"""Assembles the Issuer Detail API response (Milestone 6).

The Issuer Detail workspace is organized around the questions a
distressed-credit analyst actually asks, not around database tables (see
`app/schemas/issuer.py`'s module docstring). This service is the one place
that joins `issuer`, `security`, `financial_fact`, and
`capital_structure_position` data together for a single issuer — cross-
repository orchestration belongs here, not in the route (PLAN.md section 3)
or in any one repository (single-table concern).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.entitlement import PolicyContext, policy_check
from app.core.freshness import compute_freshness
from app.core.types import DataClassification, EntitlementAction, ProviderName
from app.domain.provenance import Provenance
from app.repositories import (
    capital_structure_repository,
    financial_fact_repository,
    issuer_repository,
    provenance_repository,
    security_repository,
)
from app.schemas.issuer import (
    IssuerActivityItem,
    IssuerDataSource,
    IssuerDetail,
    IssuerFinancialFactRow,
    IssuerSecurityRow,
)
from app.services import research_universe_service

_RECENT_ACTIVITY_LIMIT = 15


def _allowed(provenance: Provenance | None, context: PolicyContext) -> bool:
    if provenance is None:
        return False
    decision = policy_check(
        EntitlementAction.DISPLAY, DataClassification(provenance.classification), None, context
    )
    return decision.allowed


def get_issuer_detail(db: Session, issuer_id: UUID) -> IssuerDetail | None:
    """`None` when the issuer itself doesn't exist — the route maps that to a 404."""
    issuer = issuer_repository.get_issuer(db, issuer_id)
    if issuer is None:
        return None

    context = PolicyContext(environment=get_settings().environment)

    securities = security_repository.list_securities_by_issuer(db, issuer_id)
    financial_facts = financial_fact_repository.list_financial_facts_by_issuer(db, issuer_id)
    positions = capital_structure_repository.list_positions_by_issuer(db, issuer_id)

    # provider -> (record_count, latest_retrieved_at). Every fact this issuer
    # page shows anywhere (its own identity, each security, each financial
    # fact, each capital structure layer) counts toward "where did this
    # information come from" — not just the securities list.
    source_counts: dict[ProviderName, int] = defaultdict(int)
    source_latest: dict[ProviderName, datetime] = {}

    def _track_source(provenance: Provenance) -> None:
        provider = ProviderName(provenance.provider)
        source_counts[provider] += 1
        current_latest = source_latest.get(provider)
        if current_latest is None or provenance.retrieved_at > current_latest:
            source_latest[provider] = provenance.retrieved_at

    activity: list[IssuerActivityItem] = []

    issuer_provenance = provenance_repository.get_provenance(db, issuer.provenance_id)
    if issuer_provenance is not None:
        _track_source(issuer_provenance)

    security_rows: list[IssuerSecurityRow] = []
    for security in securities:
        provenance = provenance_repository.get_provenance(db, security.provenance_id)
        if not _allowed(provenance, context):
            continue
        assert provenance is not None
        _track_source(provenance)
        provider = ProviderName(provenance.provider)
        security_rows.append(
            IssuerSecurityRow(
                security_id=security.id,
                instrument_type=security.instrument_type,
                description=security.description,
                seniority=security.seniority,
                lien_position=security.lien_position,
                secured=security.secured,
                cusip=security.cusip,
                isin=security.isin,
                figi=security.figi,
                maturity_date=security.maturity_date,
                coupon=security.coupon,
                amount_outstanding=security.amount_outstanding,
                benchmark=security.benchmark,
                spread=security.spread,
                is_synthetic=security.is_synthetic,
                synthetic_reason=security.synthetic_reason,
                provider=provider,
                classification=DataClassification(provenance.classification),
                transformation=provenance.transformation,
                as_of_date=provenance.as_of_date,
                retrieved_at=provenance.retrieved_at,
                freshness=compute_freshness(provenance.retrieved_at, provider),
            )
        )
        activity.append(
            IssuerActivityItem(
                occurred_on=provenance.as_of_date,
                category="security_identified",
                headline=f"Security identified: {security.description}",
                provider=provider,
                source_url=provenance.source_url,
                as_of_date=provenance.as_of_date,
            )
        )

    financial_fact_rows: list[IssuerFinancialFactRow] = []
    for fact in financial_facts:
        provenance = provenance_repository.get_provenance(db, fact.provenance_id)
        if not _allowed(provenance, context):
            continue
        assert provenance is not None
        _track_source(provenance)
        provider = ProviderName(provenance.provider)
        financial_fact_rows.append(
            IssuerFinancialFactRow(
                financial_fact_id=fact.id,
                concept=fact.concept,
                value=fact.value,
                unit=fact.unit,
                fiscal_period=fact.fiscal_period,
                fiscal_year=fact.fiscal_year,
                form_type=fact.form_type,
                filing_date=fact.filing_date,
                accession_no=fact.accession_no,
                provider=provider,
                classification=DataClassification(provenance.classification),
                as_of_date=provenance.as_of_date,
                retrieved_at=provenance.retrieved_at,
                freshness=compute_freshness(provenance.retrieved_at, provider),
                source_url=provenance.source_url,
            )
        )
        headline = f"{fact.form_type.value} filed — {fact.concept} = {fact.value:,} {fact.unit}"
        activity.append(
            IssuerActivityItem(
                occurred_on=fact.filing_date,
                category="filing",
                headline=headline,
                provider=provider,
                source_url=provenance.source_url,
                as_of_date=provenance.as_of_date,
            )
        )

    for position in positions:
        provenance = provenance_repository.get_provenance(db, position.provenance_id)
        if not _allowed(provenance, context):
            continue
        assert provenance is not None
        _track_source(provenance)
        activity.append(
            IssuerActivityItem(
                occurred_on=provenance.as_of_date,
                category="capital_structure_update",
                headline=f"Capital structure layer recorded: {position.layer_name}",
                provider=ProviderName(provenance.provider),
                source_url=provenance.source_url,
                as_of_date=provenance.as_of_date,
            )
        )

    activity.sort(key=lambda item: item.occurred_on, reverse=True)

    data_sources = [
        IssuerDataSource(
            provider=provider,
            record_count=count,
            latest_retrieved_at=source_latest[provider],
        )
        for provider, count in sorted(source_counts.items(), key=lambda kv: kv[0].value)
    ]

    universe_memberships = research_universe_service.get_issuer_universe_memberships(db, issuer_id)

    return IssuerDetail(
        issuer_id=issuer.id,
        legal_name=issuer.legal_name,
        cik=issuer.cik,
        lei=issuer.lei,
        ticker=issuer.ticker,
        sic=issuer.sic,
        sector=issuer.sector,
        is_synthetic=issuer.is_synthetic,
        synthetic_reason=issuer.synthetic_reason,
        securities=security_rows,
        financial_facts=financial_fact_rows,
        data_sources=data_sources,
        recent_activity=activity[:_RECENT_ACTIVITY_LIMIT],
        universe_memberships=universe_memberships,
    )
