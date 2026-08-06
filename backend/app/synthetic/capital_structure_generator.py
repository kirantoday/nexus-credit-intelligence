"""Synthetic capital structure seed data (PLAN.md section 7, section 4.6).

Two parts, both clearly tagged `SYNTHETIC_DEMO_DATA` like every other module
in `app/synthetic/`:

1. **Reported layers for the eight existing leveraged-loan issuers**
   (`app/synthetic/leveraged_loan_generator.py`) — each issuer's already-seeded
   loan tranche(s) get a matching `capital_structure_position` row so they
   render in the Capital Structure section of the Issuer Detail workspace.
   No enterprise-value scenario is asserted for these issuers: nothing in
   this codebase has modeled a real or illustrative EV for them, so
   `enterprise_value_coverage`/`illustrative_recovery` stay `None` rather
   than inventing a scenario nobody asked for.

2. **One new, fully-modeled distressed issuer** ("Cobalt Ridge Energy Corp",
   entirely fictional) with a complete eight-layer stack — revolver through
   common equity — and a real illustrative recovery waterfall against a
   stated base-case Enterprise Value. This is the first real caller of
   `calculation`/`calculation_input` with genuine multiplicity (PLAN.md
   section 4.2/4.3): each layer's `enterprise_value_coverage`/
   `illustrative_recovery` traces, via `calculation_input`, to every
   strictly-senior layer's principal amount plus the shared EV assumption —
   so the lineage view can show exactly which facts a given recovery number
   depends on, not just a bare number with a footnote.

Real issuers (Apple Inc., sourced from SEC EDGAR/OpenFIGI) deliberately get
no `capital_structure_position` rows in this milestone: neither SEC's
company-facts API nor OpenFIGI's search endpoint reports seniority, lien
position, or ranking for a specific instrument (see TD-008,
`app/providers/sec_edgar/normalizer.py`, `app/providers/openfigi/normalizer.py`)
— asserting a stack position for real debt this platform hasn't actually
sourced that fact for would violate the same provenance discipline every
other adapter in this codebase follows. Tracked as TD-010 in PLAN.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.types import (
    CapitalStructureInstrumentType,
    DataClassification,
    InstrumentType,
    ProviderName,
    Seniority,
    TransformationType,
)
from app.domain.capital_structure import CapitalStructurePosition, CapitalStructurePositionCreate
from app.domain.issuer import Issuer, IssuerCreate
from app.domain.provenance import CalculationCreate, CalculationInputCreate, ProvenanceCreate
from app.domain.security import SecurityCreate
from app.repositories import (
    capital_structure_repository,
    issuer_repository,
    provenance_repository,
    security_repository,
)
from app.synthetic.leveraged_loan_generator import _ISSUERS as _LOAN_ISSUER_SPECS
from app.synthetic.leveraged_loan_generator import SYNTHETIC_REASON

_TWO_PLACES = Decimal("0.01")


def _round2(value: Decimal) -> Decimal:
    return value.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)


@dataclass(frozen=True, slots=True)
class WaterfallLayer:
    """One layer's recovery result: how much of Enterprise Value covers it,
    and what fraction of its own principal that leaves recoverable."""

    coverage: Decimal
    recovery_pct: Decimal


def compute_recovery_waterfall(
    amounts_outstanding: list[Decimal], enterprise_value: Decimal
) -> list[WaterfallLayer]:
    """A standard priority waterfall: layers are paid in the order given
    (most senior first) up to `enterprise_value`, each layer paid in full
    before any layer after it receives anything.

    `coverage` = enterprise_value / cumulative principal through and
    including this layer (how many times Enterprise Value covers everything
    ranked this senior or more senior). `recovery_pct` = the percentage of
    *this layer's own* principal that Enterprise Value actually reaches,
    clamped to [0, 100]. Pure function, no I/O — independently unit-testable
    from the database-touching seed function below.
    """
    results: list[WaterfallLayer] = []
    cumulative_before = Decimal("0")
    for amount in amounts_outstanding:
        cumulative_after = cumulative_before + amount
        coverage = (
            _round2(enterprise_value / cumulative_after) if cumulative_after > 0 else Decimal("0")
        )
        if amount > 0:
            recoverable = max(Decimal("0"), min(amount, enterprise_value - cumulative_before))
            recovery_pct = _round2((recoverable / amount) * Decimal("100"))
        else:
            recovery_pct = Decimal("0.00")
        results.append(WaterfallLayer(coverage=coverage, recovery_pct=recovery_pct))
        cumulative_before = cumulative_after
    return results


# ---------------------------------------------------------------------------
# Part 1: reported layers for the existing leveraged-loan issuers
# ---------------------------------------------------------------------------

_LOAN_SENIORITY_TO_CAPSTRUCT_TYPE: dict[Seniority, CapitalStructureInstrumentType] = {
    Seniority.FIRST_LIEN: CapitalStructureInstrumentType.FIRST_LIEN_LOAN,
    Seniority.SECOND_LIEN: CapitalStructureInstrumentType.SECOND_LIEN,
}
_LOAN_SENIORITY_TO_RANK: dict[Seniority, int] = {
    Seniority.FIRST_LIEN: 1,
    Seniority.SECOND_LIEN: 2,
}


def _seed_reported_layers_for_loan_issuers(
    db: Session, *, now: datetime
) -> list[CapitalStructurePosition]:
    """One reported `capital_structure_position` per already-seeded loan
    tranche of the eight `leveraged_loan_generator` issuers. Idempotent per
    issuer: if that issuer already has any positions, its existing rows are
    returned untouched rather than duplicated."""
    created: list[CapitalStructurePosition] = []
    for spec in _LOAN_ISSUER_SPECS:
        issuer = issuer_repository.get_issuer_by_legal_name(db, spec.legal_name)
        if issuer is None:
            # The loan generator hasn't been run yet for this issuer — this
            # generator only adds capital-structure rows on top of already-
            # seeded securities, it never creates the issuer/loans itself.
            continue

        existing = capital_structure_repository.list_positions_by_issuer(db, issuer.id)
        if existing:
            created.extend(existing)
            continue

        for security in security_repository.list_securities_by_issuer(db, issuer.id):
            if security.seniority not in _LOAN_SENIORITY_TO_CAPSTRUCT_TYPE:
                continue
            position_provenance = provenance_repository.create_provenance(
                db,
                ProvenanceCreate(
                    provider=ProviderName.SYNTHETIC,
                    source_record_id=f"synthetic-capstruct-position:{issuer.legal_name}:{security.description}",
                    source_url=None,
                    as_of_date=now.date(),
                    retrieved_at=now,
                    transformation=TransformationType.REPORTED,
                    classification=DataClassification.SYNTHETIC,
                    raw_payload_id=None,
                ),
            )
            position = capital_structure_repository.create_position(
                db,
                CapitalStructurePositionCreate(
                    issuer_id=issuer.id,
                    security_id=security.id,
                    layer_name=security.description,
                    rank_order=_LOAN_SENIORITY_TO_RANK[security.seniority],
                    instrument_type=_LOAN_SENIORITY_TO_CAPSTRUCT_TYPE[security.seniority],
                    seniority=security.seniority,
                    lien_position=security.lien_position,
                    secured=bool(security.secured),
                    guarantor_scope=None,
                    amount_outstanding=security.amount_outstanding or Decimal("0"),
                    currency="USD",
                    maturity_date=security.maturity_date,
                    price=None,
                    enterprise_value_coverage=None,
                    illustrative_recovery=None,
                    recovery_scenario=None,
                    is_synthetic=True,
                    synthetic_reason=SYNTHETIC_REASON,
                    provenance_id=position_provenance.id,
                ),
            )
            created.append(position)
    return created


# ---------------------------------------------------------------------------
# Part 2: the full eight-layer distressed demo issuer
# ---------------------------------------------------------------------------

COBALT_RIDGE_LEGAL_NAME = "Cobalt Ridge Energy Corp"
COBALT_RIDGE_ENTERPRISE_VALUE = Decimal("650000000")
_COBALT_RIDGE_RECOVERY_SCENARIO = (
    "Illustrative base-case Enterprise Value of $650,000,000 (calculated, "
    "scenario-based, illustrative — not a market fact). Waterfall: each "
    "layer is paid in full, in rank order, before any junior layer receives "
    "anything; recovery is capped at the layer's own principal."
)


@dataclass(frozen=True, slots=True)
class _TrancheSpec:
    layer_name: str
    rank_order: int
    instrument_type: CapitalStructureInstrumentType
    seniority: Seniority
    secured: bool
    amount_outstanding: Decimal
    maturity_date: date | None
    coupon: Decimal | None
    benchmark: str | None
    spread: Decimal | None
    has_security: bool


_COBALT_RIDGE_TRANCHES: tuple[_TrancheSpec, ...] = (
    _TrancheSpec(
        "Revolving Credit Facility (drawn)",
        1,
        CapitalStructureInstrumentType.REVOLVER,
        Seniority.FIRST_LIEN,
        True,
        Decimal("45000000"),
        date(2027, 3, 1),
        None,
        "SOFR",
        Decimal("4.50"),
        False,
    ),
    _TrancheSpec(
        "First Lien Term Loan B",
        2,
        CapitalStructureInstrumentType.FIRST_LIEN_LOAN,
        Seniority.FIRST_LIEN,
        True,
        Decimal("320000000"),
        date(2029, 3, 1),
        None,
        "SOFR",
        Decimal("5.25"),
        True,
    ),
    _TrancheSpec(
        "First Lien Notes due 2029",
        3,
        CapitalStructureInstrumentType.FIRST_LIEN_NOTES,
        Seniority.FIRST_LIEN,
        True,
        Decimal("150000000"),
        date(2029, 9, 1),
        Decimal("9.00"),
        None,
        None,
        True,
    ),
    _TrancheSpec(
        "Second Lien Notes due 2030",
        4,
        CapitalStructureInstrumentType.SECOND_LIEN,
        Seniority.SECOND_LIEN,
        True,
        Decimal("175000000"),
        date(2030, 6, 1),
        Decimal("11.50"),
        None,
        None,
        True,
    ),
    _TrancheSpec(
        "Senior Unsecured Notes due 2031",
        5,
        CapitalStructureInstrumentType.UNSECURED,
        Seniority.SENIOR_UNSECURED,
        False,
        Decimal("225000000"),
        date(2031, 4, 1),
        Decimal("8.25"),
        None,
        None,
        True,
    ),
    _TrancheSpec(
        "Subordinated Notes due 2032",
        6,
        CapitalStructureInstrumentType.SUBORDINATED,
        Seniority.SUBORDINATED,
        False,
        Decimal("100000000"),
        date(2032, 1, 15),
        Decimal("12.00"),
        None,
        None,
        True,
    ),
    _TrancheSpec(
        "Preferred Equity (liquidation preference)",
        7,
        CapitalStructureInstrumentType.PREFERRED_EQUITY,
        Seniority.PREFERRED,
        False,
        Decimal("75000000"),
        None,
        None,
        None,
        None,
        False,
    ),
    _TrancheSpec(
        "Common Equity (par value)",
        8,
        CapitalStructureInstrumentType.COMMON_EQUITY,
        Seniority.COMMON,
        False,
        Decimal("500000"),
        None,
        None,
        None,
        None,
        False,
    ),
)

# Coverage isn't a meaningful concept for equity residual claims (there's no
# "asset coverage multiple" for a claim with no fixed principal repayment
# right) — only debt layers get it. Recovery is shown for every layer,
# including 0.00% for wiped-out equity, since that *is* a meaningful,
# honestly-computed answer to "what does this layer get back."
_COVERAGE_APPLIES_TO = {
    CapitalStructureInstrumentType.REVOLVER,
    CapitalStructureInstrumentType.FIRST_LIEN_LOAN,
    CapitalStructureInstrumentType.FIRST_LIEN_NOTES,
    CapitalStructureInstrumentType.SECOND_LIEN,
    CapitalStructureInstrumentType.UNSECURED,
    CapitalStructureInstrumentType.SUBORDINATED,
}


def _synthetic_provenance(source_record_id: str, *, now: datetime) -> ProvenanceCreate:
    return ProvenanceCreate(
        provider=ProviderName.SYNTHETIC,
        source_record_id=source_record_id,
        source_url=None,
        as_of_date=now.date(),
        retrieved_at=now,
        transformation=TransformationType.REPORTED,
        classification=DataClassification.SYNTHETIC,
        raw_payload_id=None,
    )


@dataclass(frozen=True, slots=True)
class SeededCapitalStructureDemo:
    issuer: Issuer
    positions: list[CapitalStructurePosition]
    issuer_created: bool


def _seed_cobalt_ridge(db: Session, *, now: datetime) -> SeededCapitalStructureDemo:
    existing_issuer = issuer_repository.get_issuer_by_legal_name(db, COBALT_RIDGE_LEGAL_NAME)
    if existing_issuer is not None:
        return SeededCapitalStructureDemo(
            issuer=existing_issuer,
            positions=capital_structure_repository.list_positions_by_issuer(db, existing_issuer.id),
            issuer_created=False,
        )

    issuer_provenance = provenance_repository.create_provenance(
        db, _synthetic_provenance(f"synthetic-issuer:{COBALT_RIDGE_LEGAL_NAME}", now=now)
    )
    issuer = issuer_repository.create_issuer(
        db,
        IssuerCreate(
            legal_name=COBALT_RIDGE_LEGAL_NAME,
            sector="Oilfield Services",
            is_synthetic=True,
            synthetic_reason=SYNTHETIC_REASON,
            provenance_id=issuer_provenance.id,
        ),
    )

    ev_assumption_provenance = provenance_repository.create_provenance(
        db,
        _synthetic_provenance(
            f"synthetic-capstruct-ev-assumption:{COBALT_RIDGE_LEGAL_NAME}", now=now
        ),
    )

    waterfall = compute_recovery_waterfall(
        [t.amount_outstanding for t in _COBALT_RIDGE_TRANCHES], COBALT_RIDGE_ENTERPRISE_VALUE
    )

    positions: list[CapitalStructurePosition] = []
    # Running list of every strictly-senior layer's own principal-fact
    # provenance, oldest (most senior) first — feeds each subsequent layer's
    # calculation_input so the lineage view can show exactly which senior
    # claims a given layer's recovery figure was computed against.
    senior_principal_provenances: list[tuple[int, UUID]] = []

    for tranche, result in zip(_COBALT_RIDGE_TRANCHES, waterfall, strict=True):
        principal_provenance = provenance_repository.create_provenance(
            db,
            _synthetic_provenance(
                f"synthetic-capstruct-principal:{COBALT_RIDGE_LEGAL_NAME}:{tranche.layer_name}",
                now=now,
            ),
        )

        security_id: UUID | None = None
        if tranche.has_security:
            security = security_repository.create_security(
                db,
                SecurityCreate(
                    issuer_id=issuer.id,
                    instrument_type=(
                        InstrumentType.LOAN
                        if tranche.instrument_type
                        in (
                            CapitalStructureInstrumentType.REVOLVER,
                            CapitalStructureInstrumentType.FIRST_LIEN_LOAN,
                        )
                        else InstrumentType.BOND
                    ),
                    seniority=tranche.seniority,
                    lien_position=None,
                    secured=tranche.secured,
                    description=f"{COBALT_RIDGE_LEGAL_NAME} — {tranche.layer_name}",
                    maturity_date=tranche.maturity_date,
                    coupon=tranche.coupon,
                    amount_outstanding=tranche.amount_outstanding,
                    benchmark=tranche.benchmark,
                    spread=tranche.spread,
                    is_synthetic=True,
                    synthetic_reason=SYNTHETIC_REASON,
                    provenance_id=principal_provenance.id,
                ),
            )
            security_id = security.id

        calc_inputs = [
            CalculationInputCreate(
                provenance_id=ev_assumption_provenance.id,
                input_role="enterprise_value_assumption",
                sequence_number=0,
            ),
            CalculationInputCreate(
                provenance_id=principal_provenance.id,
                input_role="tranche_principal",
                sequence_number=tranche.rank_order,
            ),
        ]
        calc_inputs.extend(
            CalculationInputCreate(
                provenance_id=senior_provenance_id,
                input_role="senior_principal",
                sequence_number=senior_rank,
            )
            for senior_rank, senior_provenance_id in senior_principal_provenances
        )

        calculation = provenance_repository.create_calculation(
            db,
            CalculationCreate(
                method="illustrative_recovery_waterfall",
                formula_note=(
                    f"enterprise_value_coverage = enterprise_value / cumulative principal "
                    f"through and including this layer; illustrative_recovery = this "
                    f"layer's share of enterprise_value remaining after all strictly-senior "
                    f"layers are paid in full, capped at 100% of this layer's own principal. "
                    f"Base-case enterprise_value assumption: "
                    f"${COBALT_RIDGE_ENTERPRISE_VALUE:,.0f}. {_COBALT_RIDGE_RECOVERY_SCENARIO}"
                ),
            ),
            inputs=calc_inputs,
        )

        position_provenance = provenance_repository.create_provenance(
            db,
            ProvenanceCreate(
                provider=ProviderName.SYNTHETIC,
                source_record_id=(
                    f"synthetic-capstruct-position:{COBALT_RIDGE_LEGAL_NAME}:{tranche.layer_name}"
                ),
                source_url=None,
                as_of_date=now.date(),
                retrieved_at=now,
                transformation=TransformationType.CALCULATED,
                classification=DataClassification.SYNTHETIC,
                calculation_id=calculation.id,
                raw_payload_id=None,
            ),
        )

        position = capital_structure_repository.create_position(
            db,
            CapitalStructurePositionCreate(
                issuer_id=issuer.id,
                security_id=security_id,
                layer_name=tranche.layer_name,
                rank_order=tranche.rank_order,
                instrument_type=tranche.instrument_type,
                seniority=tranche.seniority,
                lien_position=None,
                secured=tranche.secured,
                guarantor_scope=None,
                amount_outstanding=tranche.amount_outstanding,
                currency="USD",
                maturity_date=tranche.maturity_date,
                price=None,
                enterprise_value_coverage=(
                    result.coverage if tranche.instrument_type in _COVERAGE_APPLIES_TO else None
                ),
                illustrative_recovery=result.recovery_pct,
                recovery_scenario=_COBALT_RIDGE_RECOVERY_SCENARIO,
                is_synthetic=True,
                synthetic_reason=SYNTHETIC_REASON,
                provenance_id=position_provenance.id,
            ),
        )
        positions.append(position)
        senior_principal_provenances.append((tranche.rank_order, principal_provenance.id))

    return SeededCapitalStructureDemo(issuer=issuer, positions=positions, issuer_created=True)


def seed_capital_structure_demo(
    db: Session, *, now: datetime | None = None
) -> SeededCapitalStructureDemo:
    """Seeds both parts described in this module's docstring. Returns the
    full-stack demo issuer's result; the reported loan-issuer layers are
    seeded as a side effect (idempotent, same as `seed_synthetic_loans`)."""
    current = now or datetime.now(UTC)
    _seed_reported_layers_for_loan_issuers(db, now=current)
    return _seed_cobalt_ridge(db, now=current)
