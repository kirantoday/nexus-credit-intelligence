"""Live, end-to-end proof of Milestone 3's primary objective (PLAN.md section 18 step 3):

one real issuer, one real SEC filing, one real XBRL financial fact, carried
through the full canonical pipeline — Provider -> DTO -> Normalizer ->
Canonical Domain Object -> Repository -> Postgres — against the actual
data.sec.gov API and the actual live, shared Supabase project.

Skipped gracefully (not failed) if SEC_USER_AGENT or DATABASE_URL isn't
configured, matching this project's established gating pattern. Runs inside
the same rolled-back transaction as every other integration test — nothing
*new* persists afterward, but the fetch itself is genuinely live, and reads
here see whatever was already genuinely committed too (Milestone 3 left one
real Apple issuer/financial_fact permanently in the database as tangible
evidence — see BUILD_LOG.md). Because of that, and because SEC periodically
publishes new real filings, these tests deliberately don't assert
`issuer_created`/`financial_fact_created` to a fixed True/False: whether this
specific run created the canonical rows or found them already there (from an
earlier run, real or test) is not the thing being proven — that the data is
correct, and that a repeated ingest never duplicates it, is.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.types import DataClassification, FormType, ProviderName, TransformationType
from app.providers.base.http_client import ThrottledHttpClient
from app.providers.sec_edgar.provider import ingest_issuer_and_one_financial_fact
from app.repositories import financial_fact_repository, issuer_repository, provenance_repository

_APPLE_CIK = 320193
_CONCEPT = "RevenueFromContractWithCustomerExcludingAssessedTax"


def test_live_ingest_apple_revenue(
    db_session: Session, sec_http_client: ThrottledHttpClient
) -> None:
    result = ingest_issuer_and_one_financial_fact(
        db_session, sec_http_client, cik=_APPLE_CIK, concept=_CONCEPT
    )

    # One real issuer.
    assert result.issuer.legal_name == "Apple Inc."
    assert result.issuer.cik == "0000320193"
    assert result.issuer.ticker == "AAPL"

    # One real XBRL financial fact, from one real SEC filing.
    assert result.financial_fact.concept == _CONCEPT
    assert result.financial_fact.value > Decimal(0)
    assert result.financial_fact.form_type in FormType
    assert result.financial_fact.accession_no.startswith("0000320193-")
    assert result.financial_fact.issuer_id == result.issuer.id

    # Round-trip through the repositories, proving Postgres actually has it.
    fetched_issuer = issuer_repository.get_issuer(db_session, result.issuer.id)
    assert fetched_issuer is not None
    assert fetched_issuer.legal_name == "Apple Inc."

    fetched_fact = financial_fact_repository.get_financial_fact(
        db_session, result.financial_fact.id
    )
    assert fetched_fact is not None
    assert fetched_fact.value == result.financial_fact.value

    # Provenance carries real, non-fabricated lineage.
    assert result.issuer.provenance_id is not None
    assert result.financial_fact.provenance_id is not None


def test_live_ingest_is_idempotent_on_canonical_rows(
    db_session: Session, sec_http_client: ThrottledHttpClient
) -> None:
    first = ingest_issuer_and_one_financial_fact(
        db_session, sec_http_client, cik=_APPLE_CIK, concept=_CONCEPT
    )
    second = ingest_issuer_and_one_financial_fact(
        db_session, sec_http_client, cik=_APPLE_CIK, concept=_CONCEPT
    )

    # Both calls in *this* transaction must agree with each other — the
    # actual proof of idempotency — regardless of what may already exist
    # from earlier runs (see module docstring).
    assert second.issuer.id == first.issuer.id
    assert second.financial_fact.id == first.financial_fact.id

    # Exactly one row for this specific datapoint's dedup key, not a global
    # count (SEC periodically files new real filings, which legitimately
    # adds a *different* dedup key over time — that's not a duplicate).
    matching = financial_fact_repository.get_by_dedup_key(
        db_session,
        first.issuer.id,
        first.financial_fact.concept,
        first.financial_fact.accession_no,
        first.financial_fact.fiscal_year,
        first.financial_fact.fiscal_period,
    )
    assert matching is not None
    assert matching.id == first.financial_fact.id


def test_live_ingest_provenance_is_public_reported(
    db_session: Session, sec_http_client: ThrottledHttpClient
) -> None:
    result = ingest_issuer_and_one_financial_fact(
        db_session, sec_http_client, cik=_APPLE_CIK, concept=_CONCEPT
    )

    issuer_provenance = provenance_repository.get_provenance(
        db_session, result.issuer.provenance_id
    )
    fact_provenance = provenance_repository.get_provenance(
        db_session, result.financial_fact.provenance_id
    )

    assert issuer_provenance is not None
    assert issuer_provenance.provider is ProviderName.SEC_EDGAR
    assert issuer_provenance.classification is DataClassification.PUBLIC
    assert issuer_provenance.transformation is TransformationType.REPORTED
    assert issuer_provenance.raw_payload_id is not None

    assert fact_provenance is not None
    assert fact_provenance.provider is ProviderName.SEC_EDGAR
    assert fact_provenance.classification is DataClassification.PUBLIC
    assert fact_provenance.raw_payload_id is not None
