"""Integration tests for `app/services/synthetic_cleanup_service.py`
(PLAN.md Milestone 7.5.3 CFO-demo cleanup) against the live shared
`nexus` schema.

Covers the explicit data-safety requirements: a real issuer that had a
synthetic security is preserved (only the synthetic security is
removed); a synthetic-only issuer with zero real dependencies is fully
deleted; a nominally-synthetic issuer with any real canonical data
(SEC filing, in this test) is never touched, proving the cleanup cannot
cascade-delete legitimate data.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.types import DataClassification, InstrumentType
from app.domain.issuer import IssuerCreate
from app.domain.sec_filing import SecFilingCreate
from app.domain.security import SecurityCreate
from app.repositories import (
    issuer_repository,
    provenance_repository,
    sec_filing_repository,
    security_repository,
)
from app.services import synthetic_cleanup_service
from tests.integration.conftest import reported_public_provenance


def _seed_real_issuer(db: Session, *, legal_name: str):
    provenance = provenance_repository.create_provenance(db, reported_public_provenance())
    return issuer_repository.create_issuer(
        db, IssuerCreate(legal_name=legal_name, provenance_id=provenance.id)
    )


def _seed_synthetic_issuer(db: Session, *, legal_name: str):
    provenance = provenance_repository.create_provenance(
        db, reported_public_provenance(classification=DataClassification.SYNTHETIC)
    )
    return issuer_repository.create_issuer(
        db,
        IssuerCreate(
            legal_name=legal_name,
            provenance_id=provenance.id,
            is_synthetic=True,
            synthetic_reason="SYNTHETIC_DEMO_DATA",
        ),
    )


def _seed_security(db: Session, *, issuer_id, legal_name: str, is_synthetic: bool):
    provenance = provenance_repository.create_provenance(
        db,
        reported_public_provenance(
            classification=(
                DataClassification.SYNTHETIC if is_synthetic else DataClassification.PUBLIC
            )
        ),
    )
    return security_repository.create_security(
        db,
        SecurityCreate(
            issuer_id=issuer_id,
            instrument_type=InstrumentType.BOND,
            description=f"{legal_name} — Test Bond",
            maturity_date=date(2030, 1, 1),
            amount_outstanding=Decimal("100000000"),
            provenance_id=provenance.id,
            is_synthetic=is_synthetic,
            synthetic_reason="SYNTHETIC_DEMO_DATA" if is_synthetic else None,
        ),
    )


def test_remove_synthetic_securities_preserves_real_issuer_and_real_security(
    db_session: Session,
) -> None:
    """A real issuer that previously had a synthetic security must be
    preserved — only the synthetic security is removed."""
    issuer = _seed_real_issuer(db_session, legal_name="Cleanup Test Real Issuer")
    real_security = _seed_security(
        db_session, issuer_id=issuer.id, legal_name=issuer.legal_name, is_synthetic=False
    )
    synthetic_security = _seed_security(
        db_session, issuer_id=issuer.id, legal_name=issuer.legal_name, is_synthetic=True
    )

    deleted_count = synthetic_cleanup_service.remove_synthetic_securities_for_issuer(
        db_session, issuer.id
    )

    assert deleted_count == 1
    assert issuer_repository.get_issuer(db_session, issuer.id) is not None
    remaining = security_repository.list_securities_by_issuer(db_session, issuer.id)
    remaining_ids = {s.id for s in remaining}
    assert real_security.id in remaining_ids
    assert synthetic_security.id not in remaining_ids


def test_delete_synthetic_only_issuer_removes_a_clean_synthetic_issuer(
    db_session: Session,
) -> None:
    issuer = _seed_synthetic_issuer(db_session, legal_name="Cleanup Test Synthetic-Only Issuer")
    _seed_security(db_session, issuer_id=issuer.id, legal_name=issuer.legal_name, is_synthetic=True)

    result = synthetic_cleanup_service.delete_synthetic_only_issuer(db_session, issuer.id)

    assert result.deleted is True
    assert result.securities_deleted == 1
    assert issuer_repository.get_issuer(db_session, issuer.id) is None


def test_delete_synthetic_only_issuer_refuses_a_real_issuer(db_session: Session) -> None:
    issuer = _seed_real_issuer(db_session, legal_name="Cleanup Test Real Issuer Not Deletable")

    result = synthetic_cleanup_service.delete_synthetic_only_issuer(db_session, issuer.id)

    assert result.deleted is False
    assert result.reason == "issuer_is_not_synthetic"
    assert issuer_repository.get_issuer(db_session, issuer.id) is not None


def test_delete_synthetic_only_issuer_never_cascades_over_real_canonical_data(
    db_session: Session,
) -> None:
    """A synthetic-flagged issuer that nonetheless has real canonical
    research history (a SEC filing, here) must never be deleted — proves
    the cleanup cannot cascade-delete legitimate data even if the
    `is_synthetic` flag alone would otherwise make it eligible."""
    issuer = _seed_synthetic_issuer(
        db_session, legal_name="Cleanup Test Synthetic-Flagged But Has Real Data"
    )
    provenance = provenance_repository.create_provenance(db_session, reported_public_provenance())
    filing, _created = sec_filing_repository.create_filing(
        db_session,
        SecFilingCreate(
            issuer_id=issuer.id,
            accession_no=f"test-{uuid4()}",
            form_type="8-K",
            filing_date=date(2026, 1, 1),
            provenance_id=provenance.id,
        ),
    )

    result = synthetic_cleanup_service.delete_synthetic_only_issuer(db_session, issuer.id)

    assert result.deleted is False
    assert result.reason == "has_real_dependency:sec_filing"
    assert issuer_repository.get_issuer(db_session, issuer.id) is not None
    assert sec_filing_repository.get_filing(db_session, filing.id) is not None


def test_delete_synthetic_only_issuer_refuses_when_a_real_security_exists(
    db_session: Session,
) -> None:
    """Belt-and-suspenders: even if every dependency table is clean, an
    issuer with a real (non-synthetic) security is never eligible for the
    full cascade delete."""
    issuer = _seed_synthetic_issuer(
        db_session, legal_name="Cleanup Test Synthetic Issuer With A Real Security"
    )
    _seed_security(
        db_session, issuer_id=issuer.id, legal_name=issuer.legal_name, is_synthetic=False
    )

    result = synthetic_cleanup_service.delete_synthetic_only_issuer(db_session, issuer.id)

    assert result.deleted is False
    assert result.reason == "has_real_security"
    assert issuer_repository.get_issuer(db_session, issuer.id) is not None
