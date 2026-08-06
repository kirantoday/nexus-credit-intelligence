"""Live, end-to-end proof of Milestone 5's OpenFIGI slice (PLAN.md section 18
step 5): "what security is this?" — real, specific Apple corporate bonds
(real FIGI, real maturity/coupon) identified via a genuine live call to
api.openfigi.com and carried through the full canonical pipeline.

Skipped gracefully (not failed) if SEC_USER_AGENT or DATABASE_URL isn't
configured, matching this project's established gating pattern. Runs inside
the same rolled-back transaction as every other integration test — nothing
*new* persists afterward, but the fetch itself is genuinely live, and reads
here see whatever was already genuinely committed too (Milestone 5 left five
real Apple bonds permanently in the database — see BUILD_LOG.md). Because of
that, these tests deliberately don't assert `security_created` to a fixed
True/False for a specific FIGI: whether this run created the row or found it
already there is not the thing being proven — that the data is correct, and
that a repeated search never duplicates a bond, is.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session

from app.core.types import DataClassification, InstrumentType, ProviderName, TransformationType
from app.providers.base.http_client import ThrottledHttpClient
from app.providers.openfigi.provider import search_and_ingest_issuer_bonds
from app.providers.sec_edgar.provider import ingest_issuer_and_one_financial_fact
from app.repositories import provenance_repository, security_repository

_APPLE_CIK = 320193
_CONCEPT = "RevenueFromContractWithCustomerExcludingAssessedTax"


def _existing_apple_issuer_id(db_session: Session, sec_http_client: ThrottledHttpClient) -> UUID:
    """Apple's issuer row already exists live (Milestone 3) — ingesting it
    again here is the same idempotent call the real seed script made, not a
    second creation, and gives every test in this module a real issuer id
    without depending on external test ordering."""
    result = ingest_issuer_and_one_financial_fact(
        db_session, sec_http_client, cik=_APPLE_CIK, concept=_CONCEPT
    )
    return result.issuer.id


def test_live_search_and_ingest_apple_bonds(
    db_session: Session,
    sec_http_client: ThrottledHttpClient,
    openfigi_http_client: ThrottledHttpClient,
) -> None:
    issuer_id = _existing_apple_issuer_id(db_session, sec_http_client)

    result = search_and_ingest_issuer_bonds(
        db_session, openfigi_http_client, issuer_id=issuer_id, query="APPLE INC", limit=5
    )

    assert len(result.bonds) > 0
    for bond in result.bonds:
        security = bond.security
        assert security.issuer_id == issuer_id
        assert security.instrument_type is InstrumentType.BOND
        assert security.figi is not None
        assert security.figi.startswith("BBG")
        assert security.is_synthetic is False
        # Honestly missing, never fabricated: OpenFIGI's free API doesn't
        # return either (see normalizer.normalize_bond_security's docstring).
        assert security.cusip is None
        assert security.isin is None

        fetched = security_repository.get_security(db_session, security.id)
        assert fetched is not None
        assert fetched.figi == security.figi


def test_live_search_and_ingest_is_idempotent_on_figi(
    db_session: Session,
    sec_http_client: ThrottledHttpClient,
    openfigi_http_client: ThrottledHttpClient,
) -> None:
    issuer_id = _existing_apple_issuer_id(db_session, sec_http_client)

    first = search_and_ingest_issuer_bonds(
        db_session, openfigi_http_client, issuer_id=issuer_id, query="APPLE INC", limit=5
    )
    second = search_and_ingest_issuer_bonds(
        db_session, openfigi_http_client, issuer_id=issuer_id, query="APPLE INC", limit=5
    )

    first_figis = {b.security.figi for b in first.bonds}
    second_figis = {b.security.figi for b in second.bonds}
    assert first_figis == second_figis

    first_ids_by_figi = {b.security.figi: b.security.id for b in first.bonds}
    for bond in second.bonds:
        assert bond.security.id == first_ids_by_figi[bond.security.figi]

    # A bond found via `get_security_by_figi` (already existed from the first
    # call in this transaction) must never be reported as newly created.
    for bond in second.bonds:
        assert bond.security_created is False


def test_live_bond_provenance_is_public_reported_openfigi(
    db_session: Session,
    sec_http_client: ThrottledHttpClient,
    openfigi_http_client: ThrottledHttpClient,
) -> None:
    issuer_id = _existing_apple_issuer_id(db_session, sec_http_client)

    result = search_and_ingest_issuer_bonds(
        db_session, openfigi_http_client, issuer_id=issuer_id, query="APPLE INC", limit=1
    )
    assert len(result.bonds) == 1
    security = result.bonds[0].security

    provenance = provenance_repository.get_provenance(db_session, security.provenance_id)
    assert provenance is not None
    assert provenance.provider is ProviderName.OPENFIGI
    assert provenance.classification is DataClassification.PUBLIC
    assert provenance.transformation is TransformationType.REPORTED
    assert provenance.raw_payload_id is not None


def test_live_ingest_requires_existing_issuer(
    db_session: Session, openfigi_http_client: ThrottledHttpClient
) -> None:
    with pytest.raises(ValueError, match="no issuer"):
        search_and_ingest_issuer_bonds(
            db_session, openfigi_http_client, issuer_id=uuid4(), query="APPLE INC"
        )
