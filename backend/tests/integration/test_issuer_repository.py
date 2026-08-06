"""Integration tests for issuer_repository against the live nexus schema."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.issuer import IssuerCreate
from app.repositories import issuer_repository as repo
from app.repositories import provenance_repository
from tests.integration.conftest import reported_public_provenance


def _issuer_create(db: Session, **overrides: object) -> IssuerCreate:
    """Default `cik` is deliberately far outside any real SEC CIK range
    (currently well under 2,000,000) — a prior Milestone 3 test run collided
    with a genuinely-committed real Apple issuer row (CIK 0000320193) left in
    the live database as evidence of the SEC ingestion pipeline, so every
    test-owned CIK in this file now uses the unambiguously-fake 9999900xxx
    range instead of a real company's identity.
    """
    provenance = provenance_repository.create_provenance(db, reported_public_provenance())
    defaults: dict[str, object] = dict(
        legal_name="Test Issuer Co",
        cik="9999900001",
        lei=None,
        ticker="TEST",
        sic="9999",
        sector=None,
        provenance_id=provenance.id,
    )
    defaults.update(overrides)
    return IssuerCreate(**defaults)  # type: ignore[arg-type]


def test_create_and_get_issuer(db_session: Session) -> None:
    created = repo.create_issuer(db_session, _issuer_create(db_session))
    assert created.id is not None

    fetched = repo.get_issuer(db_session, created.id)
    assert fetched is not None
    assert fetched.legal_name == "Test Issuer Co"
    assert fetched.cik == "9999900001"
    assert fetched.ticker == "TEST"


def test_get_issuer_missing_returns_none(db_session: Session) -> None:
    assert repo.get_issuer(db_session, uuid.uuid4()) is None


def test_get_issuer_by_cik_finds_existing(db_session: Session) -> None:
    repo.create_issuer(db_session, _issuer_create(db_session, cik="9999900002"))

    found = repo.get_issuer_by_cik(db_session, "9999900002")

    assert found is not None
    assert found.cik == "9999900002"


def test_get_issuer_by_cik_not_found_returns_none(db_session: Session) -> None:
    assert repo.get_issuer_by_cik(db_session, "9999999999") is None


def test_cik_uniqueness_enforced_at_db_level(db_session: Session) -> None:
    """Defense-in-depth: ix_issuer_cik is a unique index — two issuers can't
    claim the same real-world CIK."""
    repo.create_issuer(db_session, _issuer_create(db_session, cik="9999900003"))

    with pytest.raises(IntegrityError):
        repo.create_issuer(db_session, _issuer_create(db_session, cik="9999900003"))


def test_multiple_issuers_with_null_cik_are_allowed(db_session: Session) -> None:
    """Synthetic/no-SEC-filer issuers can all have cik=None without conflict."""
    first = repo.create_issuer(
        db_session, _issuer_create(db_session, cik=None, legal_name="Synthetic Co A")
    )
    second = repo.create_issuer(
        db_session, _issuer_create(db_session, cik=None, legal_name="Synthetic Co B")
    )
    assert first.id != second.id
