"""Integration tests for the synthetic leveraged loan generator against the
live nexus schema.

Milestone 4 permanently committed the real seed run's fictional issuers to
the live database (see BUILD_LOG.md) — so, like Milestone 3's live SEC
ingestion tests, these deliberately don't assert `issuer_created` to a fixed
True/False on a single call: whether a *specific* run creates the issuers or
finds them already seeded depends on prior runs, not on anything this test
controls. What's actually being proven is data correctness and that two
calls within the same transaction agree with each other (idempotency).
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.types import DataClassification, ProviderName
from app.repositories import provenance_repository
from app.synthetic.leveraged_loan_generator import SYNTHETIC_REASON, seed_synthetic_loans


def test_seed_synthetic_loans_data_is_correctly_tagged(db_session: Session) -> None:
    results = seed_synthetic_loans(db_session)

    assert len(results) > 0
    for result in results:
        assert result.issuer.is_synthetic is True
        assert result.issuer.synthetic_reason == SYNTHETIC_REASON
        assert result.issuer.cik is None, "synthetic issuers must never claim a real CIK"
        assert len(result.securities) >= 1
        for security in result.securities:
            assert security.is_synthetic is True
            assert security.synthetic_reason == SYNTHETIC_REASON
            assert security.cusip is None, "synthetic securities must never fabricate a CUSIP"
            assert security.isin is None
            assert security.issuer_id == result.issuer.id


def test_seed_synthetic_loans_provenance_is_classified_synthetic(db_session: Session) -> None:
    results = seed_synthetic_loans(db_session)
    issuer = results[0].issuer

    provenance = provenance_repository.get_provenance(db_session, issuer.provenance_id)

    assert provenance is not None
    assert provenance.provider is ProviderName.SYNTHETIC
    assert provenance.classification is DataClassification.SYNTHETIC
    assert (
        provenance.raw_payload_id is None
    ), "no raw payload exists for generated, not fetched, data"


def test_seed_synthetic_loans_is_idempotent_within_a_run(db_session: Session) -> None:
    first_run = seed_synthetic_loans(db_session)
    second_run = seed_synthetic_loans(db_session)

    # Whatever the first call's created/found mix was, the second call must
    # agree with it exactly and never mark anything newly created.
    assert all(not r.issuer_created for r in second_run)

    first_ids = {r.issuer.id for r in first_run}
    second_ids = {r.issuer.id for r in second_run}
    assert first_ids == second_ids, "re-running must reuse the same issuers, not duplicate them"


def test_seed_synthetic_loans_issuer_names_are_unique(db_session: Session) -> None:
    results = seed_synthetic_loans(db_session)
    names = [r.issuer.legal_name for r in results]
    assert len(names) == len(set(names))
