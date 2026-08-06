"""OpenFIGI DTO -> canonical domain object mapping.

The only place OpenFIGI-specific shapes get translated into PLAN.md's
provider-neutral canonical schema (`app/domain/security.py`).
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from app.core.types import DataClassification, InstrumentType, ProviderName, TransformationType
from app.domain.provenance import ProvenanceCreate
from app.domain.security import SecurityCreate
from app.providers.openfigi.dto import OpenFigiSearchResult

# OpenFIGI's own free-text ticker convention for a corporate bond
# (`marketSector = "Corp"`), e.g. "AAPL 3.85 05/04/43" or, for a floating-rate
# note, "AAPL F 08/28/19 MTn" (coupon token "F", no numeric rate). Verified
# against live search results before writing this, not assumed. A trailing
# suffix (" EMTN", " MTn", ...) is common and deliberately not captured.
_COUPON_AND_MATURITY = re.compile(
    r"(?P<coupon>\d+(?:\.\d+)?)\s+(?P<mm>\d{2})/(?P<dd>\d{2})/(?P<yy>\d{2})\b"
)
_MATURITY_ONLY = re.compile(r"(?P<mm>\d{2})/(?P<dd>\d{2})/(?P<yy>\d{2})\b")


def _year_from_two_digit(yy: str) -> int:
    """No bond in scope here predates 1950 — the standard pivot-at-50
    convention for a 2-digit year is unambiguous in this domain."""
    year = int(yy)
    return 2000 + year if year < 50 else 1900 + year


def parse_coupon_and_maturity(ticker: str) -> tuple[Decimal | None, date | None]:
    """Extract coupon/maturity from OpenFIGI's ticker convention when it's
    the recognizable "COUPON MM/DD/YY" shape; maturity alone when the coupon
    token isn't numeric (e.g. floating-rate notes, ticker'd "F" not a rate).
    Returns `(None, None)`, never a guess, when neither pattern matches —
    matching this project's "leave genuinely unknown fields None" rule
    (see `normalize_bond_security`).
    """
    match = _COUPON_AND_MATURITY.search(ticker)
    if match:
        coupon = Decimal(match.group("coupon"))
        maturity = date(
            _year_from_two_digit(match.group("yy")), int(match.group("mm")), int(match.group("dd"))
        )
        return coupon, maturity
    match = _MATURITY_ONLY.search(ticker)
    if match:
        maturity = date(
            _year_from_two_digit(match.group("yy")), int(match.group("mm")), int(match.group("dd"))
        )
        return None, maturity
    return None, None


def normalize_bond_provenance(
    result: OpenFigiSearchResult,
    *,
    source_url: str,
    retrieved_at: datetime,
    raw_payload_id: UUID,
) -> ProvenanceCreate:
    return ProvenanceCreate(
        provider=ProviderName.OPENFIGI,
        source_record_id=result.figi,
        source_url=source_url,
        # OpenFIGI's search response carries no "as of" date for a reference
        # assignment (a FIGI, once assigned, doesn't have a reported
        # effective date via this endpoint) — the fact "this FIGI identifies
        # this instrument" is true as of when we retrieved it, which is the
        # honest as_of_date here, not a guess at an assignment date.
        as_of_date=retrieved_at.date(),
        retrieved_at=retrieved_at,
        transformation=TransformationType.REPORTED,
        classification=DataClassification.PUBLIC,
        raw_payload_id=raw_payload_id,
    )


def normalize_bond_security(
    result: OpenFigiSearchResult,
    *,
    issuer_id: UUID,
    issuer_legal_name: str,
    provenance_id: UUID,
) -> SecurityCreate:
    """A real, specific bond issue identified by OpenFIGI — unlike
    `sec_edgar.normalizer.normalize_bond_security`'s aggregate figure, this
    row identifies one actual instrument (real FIGI, real maturity/coupon
    parsed from OpenFIGI's own ticker convention).

    `cusip`/`isin` are left `None`: OpenFIGI's public search/mapping API
    genuinely does not return either (Bloomberg/ANNA license those
    separately from FIGI) — confirmed live, not assumed. `seniority`,
    `lien_position`, `secured`, `amount_outstanding`, `benchmark`, `spread`
    are also left `None` — OpenFIGI is a security-identification service, not
    a terms/pricing one, and none of those are in its response.
    """
    coupon, maturity_date = parse_coupon_and_maturity(result.ticker)
    return SecurityCreate(
        issuer_id=issuer_id,
        instrument_type=InstrumentType.BOND,
        seniority=None,
        lien_position=None,
        secured=None,
        cusip=None,
        isin=None,
        figi=result.figi,
        description=f"{issuer_legal_name} — {result.ticker}",
        maturity_date=maturity_date,
        coupon=coupon,
        amount_outstanding=None,
        benchmark=None,
        spread=None,
        is_synthetic=False,
        synthetic_reason=None,
        provenance_id=provenance_id,
    )
