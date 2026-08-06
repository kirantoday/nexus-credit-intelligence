"""Synthetic leveraged loan generator (PLAN.md ADR-008, section 4.5's `synthetic_flag`).

Loan-level pricing/terms have no public data source — real leveraged loan
data (S&P Global LCD, Octus, LSEG LPC) is licensed and none of those
providers are connected yet (PLAN.md section 14). To make the Credit
Universe demonstrable at a realistic scale before a licensed provider
exists, this module seeds clearly-labeled synthetic loan securities for
entirely fictional issuers — never a real company name, ticker, or CIK, and
never presented as anything other than demo data.

Every row this creates sets `classification = synthetic` on its provenance
and `is_synthetic = True` + `synthetic_reason = SYNTHETIC_REASON` on both the
`issuer` and `security` rows (PLAN.md 4.5's synthetic_flag pattern) — the
same fields `policy_check`/the UI's synthetic-data badge already key off.

Fixed, hand-written figures rather than randomly generated: a reviewable,
auditable demo dataset beats a seeded-RNG one for data a real analyst will
actually look at, even labeled as synthetic.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.types import (
    DataClassification,
    InstrumentType,
    ProviderName,
    Seniority,
    TransformationType,
)
from app.domain.issuer import Issuer, IssuerCreate
from app.domain.provenance import ProvenanceCreate
from app.domain.security import Security, SecurityCreate
from app.repositories import issuer_repository, provenance_repository, security_repository

SYNTHETIC_REASON = "SYNTHETIC_DEMO_DATA"


@dataclass(frozen=True, slots=True)
class _LoanSpec:
    tranche_name: str
    seniority: Seniority
    amount_outstanding: Decimal
    spread: Decimal
    maturity_date: date


@dataclass(frozen=True, slots=True)
class _IssuerSpec:
    legal_name: str
    sector: str
    loans: tuple[_LoanSpec, ...]


_ISSUERS: tuple[_IssuerSpec, ...] = (
    _IssuerSpec(
        "Ridgeline Industrial Holdings LLC",
        "Industrial Manufacturing",
        (
            _LoanSpec(
                "First Lien Term Loan B",
                Seniority.FIRST_LIEN,
                Decimal("325000000"),
                Decimal("4.50"),
                date(2029, 6, 15),
            ),
        ),
    ),
    _IssuerSpec(
        "Meridian Specialty Products Corp",
        "Specialty Chemicals",
        (
            _LoanSpec(
                "First Lien Term Loan B",
                Seniority.FIRST_LIEN,
                Decimal("410000000"),
                Decimal("4.25"),
                date(2030, 3, 1),
            ),
            _LoanSpec(
                "Second Lien Term Loan",
                Seniority.SECOND_LIEN,
                Decimal("120000000"),
                Decimal("7.75"),
                date(2030, 9, 1),
            ),
        ),
    ),
    _IssuerSpec(
        "Cascade Foodservice Group LLC",
        "Restaurants & Foodservice",
        (
            _LoanSpec(
                "First Lien Term Loan B",
                Seniority.FIRST_LIEN,
                Decimal("210000000"),
                Decimal("5.00"),
                date(2028, 11, 30),
            ),
        ),
    ),
    _IssuerSpec(
        "Summit Building Products Inc",
        "Building Products",
        (
            _LoanSpec(
                "First Lien Term Loan B",
                Seniority.FIRST_LIEN,
                Decimal("475000000"),
                Decimal("4.00"),
                date(2031, 1, 15),
            ),
        ),
    ),
    _IssuerSpec(
        "Harborview Logistics Partners LLC",
        "Transportation & Logistics",
        (
            _LoanSpec(
                "First Lien Term Loan B",
                Seniority.FIRST_LIEN,
                Decimal("265000000"),
                Decimal("4.75"),
                date(2029, 8, 20),
            ),
            _LoanSpec(
                "Second Lien Term Loan",
                Seniority.SECOND_LIEN,
                Decimal("85000000"),
                Decimal("8.25"),
                date(2030, 2, 20),
            ),
        ),
    ),
    _IssuerSpec(
        "Northbrook Healthcare Services LLC",
        "Healthcare Services",
        (
            _LoanSpec(
                "First Lien Term Loan B",
                Seniority.FIRST_LIEN,
                Decimal("540000000"),
                Decimal("3.75"),
                date(2030, 12, 1),
            ),
        ),
    ),
    _IssuerSpec(
        "Vantage Media Holdings Corp",
        "Media & Entertainment",
        (
            _LoanSpec(
                "First Lien Term Loan B",
                Seniority.FIRST_LIEN,
                Decimal("190000000"),
                Decimal("5.50"),
                date(2028, 5, 10),
            ),
        ),
    ),
    _IssuerSpec(
        "Cornerstone Packaging Solutions LLC",
        "Packaging",
        (
            _LoanSpec(
                "First Lien Term Loan B",
                Seniority.FIRST_LIEN,
                Decimal("355000000"),
                Decimal("4.50"),
                date(2029, 10, 5),
            ),
        ),
    ),
)


@dataclass(frozen=True, slots=True)
class SeededIssuerLoans:
    issuer: Issuer
    securities: list[Security]
    issuer_created: bool


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


def seed_synthetic_loans(db: Session, *, now: datetime | None = None) -> list[SeededIssuerLoans]:
    """Seed every fictional issuer + its loan tranches.

    Idempotent at the issuer level: if an issuer with a given synthetic
    `legal_name` already exists, it (and its previously-seeded loans) are
    left untouched and simply returned — re-running this doesn't duplicate
    issuers or securities.
    """
    current = now or datetime.now(UTC)
    results: list[SeededIssuerLoans] = []

    for issuer_spec in _ISSUERS:
        existing_issuer = issuer_repository.get_issuer_by_legal_name(db, issuer_spec.legal_name)
        if existing_issuer is not None:
            results.append(
                SeededIssuerLoans(
                    issuer=existing_issuer,
                    securities=security_repository.list_securities_by_issuer(
                        db, existing_issuer.id
                    ),
                    issuer_created=False,
                )
            )
            continue

        issuer_provenance = provenance_repository.create_provenance(
            db,
            _synthetic_provenance(f"synthetic-issuer:{issuer_spec.legal_name}", now=current),
        )
        issuer = issuer_repository.create_issuer(
            db,
            IssuerCreate(
                legal_name=issuer_spec.legal_name,
                cik=None,
                lei=None,
                ticker=None,
                sic=None,
                sector=issuer_spec.sector,
                is_synthetic=True,
                synthetic_reason=SYNTHETIC_REASON,
                provenance_id=issuer_provenance.id,
            ),
        )

        securities: list[Security] = []
        for loan in issuer_spec.loans:
            loan_provenance = provenance_repository.create_provenance(
                db,
                _synthetic_provenance(
                    f"synthetic-loan:{issuer_spec.legal_name}:{loan.tranche_name}", now=current
                ),
            )
            security = security_repository.create_security(
                db,
                SecurityCreate(
                    issuer_id=issuer.id,
                    instrument_type=InstrumentType.LOAN,
                    seniority=loan.seniority,
                    lien_position=None,
                    secured=True,
                    cusip=None,
                    isin=None,
                    figi=None,
                    description=(
                        f"{issuer_spec.legal_name} — {loan.tranche_name} "
                        f"due {loan.maturity_date.year}"
                    ),
                    maturity_date=loan.maturity_date,
                    coupon=None,
                    amount_outstanding=loan.amount_outstanding,
                    benchmark="SOFR",
                    spread=loan.spread,
                    is_synthetic=True,
                    synthetic_reason=SYNTHETIC_REASON,
                    provenance_id=loan_provenance.id,
                ),
            )
            securities.append(security)

        results.append(SeededIssuerLoans(issuer=issuer, securities=securities, issuer_created=True))

    return results
