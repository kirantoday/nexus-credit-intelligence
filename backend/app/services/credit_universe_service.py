"""Assembles Credit Universe API responses from canonical repository data.

Cross-repository orchestration lives here, not in the route (kept thin per
PLAN.md section 3) or the repository (single-table concern) — this is
PLAN.md section 17's `services/` layer.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.entitlement import PolicyContext, policy_check
from app.core.freshness import compute_freshness
from app.core.types import EntitlementAction, InstrumentType
from app.repositories import security_repository
from app.repositories.security_repository import SortDirection, SortField
from app.schemas.credit_universe import CreditUniversePage, CreditUniverseRow


def get_credit_universe_page(
    db: Session,
    *,
    instrument_type: InstrumentType | None = None,
    is_synthetic: bool | None = None,
    search: str | None = None,
    sort_by: SortField = "legal_name",
    sort_dir: SortDirection = "asc",
    page: int = 1,
    page_size: int = 50,
) -> CreditUniversePage:
    rows, total = security_repository.list_credit_universe(
        db,
        instrument_type=instrument_type,
        is_synthetic=is_synthetic,
        search=search,
        sort_by=sort_by,
        sort_dir=sort_dir,
        page=page,
        page_size=page_size,
    )

    context = PolicyContext(environment=get_settings().environment)

    # No licensed provider is connected yet (Milestone 14), so `entitlement`
    # is always None and `policy_check` always allows public/synthetic rows
    # — but every row still goes through the real choke point rather than
    # skipping it, so nothing has to change here once a licensed provider
    # exists. `total` intentionally isn't adjusted for rows a future
    # entitlement denies: that's a repository-level filtering concern to
    # revisit once `policy_check` can actually return False for a real row.
    visible_rows: list[CreditUniverseRow] = []
    for row in rows:
        decision = policy_check(
            EntitlementAction.DISPLAY, row.provenance_classification, None, context
        )
        if not decision.allowed:
            continue
        visible_rows.append(
            CreditUniverseRow(
                security_id=row.security.id,
                issuer_id=row.security.issuer_id,
                issuer_legal_name=row.issuer_legal_name,
                issuer_ticker=row.issuer_ticker,
                issuer_sector=row.issuer_sector,
                instrument_type=row.security.instrument_type,
                description=row.security.description,
                seniority=row.security.seniority,
                lien_position=row.security.lien_position,
                secured=row.security.secured,
                cusip=row.security.cusip,
                isin=row.security.isin,
                figi=row.security.figi,
                maturity_date=row.security.maturity_date,
                coupon=row.security.coupon,
                amount_outstanding=row.security.amount_outstanding,
                benchmark=row.security.benchmark,
                spread=row.security.spread,
                is_synthetic=row.security.is_synthetic,
                synthetic_reason=row.security.synthetic_reason,
                provider=row.provenance_provider,
                classification=row.provenance_classification,
                transformation=row.provenance_transformation,
                as_of_date=row.provenance_as_of_date,
                retrieved_at=row.provenance_retrieved_at,
                freshness=compute_freshness(row.provenance_retrieved_at, row.provenance_provider),
            )
        )

    return CreditUniversePage(rows=visible_rows, total=total, page=page, page_size=page_size)
