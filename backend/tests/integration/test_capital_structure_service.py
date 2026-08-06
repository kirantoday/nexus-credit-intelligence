"""Integration tests for capital_structure_service against the live nexus schema."""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.types import CapitalStructureInstrumentType, Seniority
from app.domain.capital_structure import CapitalStructurePositionCreate
from app.domain.issuer import IssuerCreate
from app.repositories import capital_structure_repository, issuer_repository, provenance_repository
from app.services import capital_structure_service
from tests.integration.conftest import reported_public_provenance


def test_get_capital_structure_returns_none_for_missing_issuer(db_session: Session) -> None:
    assert capital_structure_service.get_capital_structure(db_session, uuid.uuid4()) is None


def test_get_capital_structure_returns_empty_positions_when_none_seeded(
    db_session: Session,
) -> None:
    issuer_provenance = provenance_repository.create_provenance(
        db_session, reported_public_provenance()
    )
    issuer = issuer_repository.create_issuer(
        db_session,
        IssuerCreate(
            legal_name="Capstruct Service Test Empty Co", provenance_id=issuer_provenance.id
        ),
    )

    result = capital_structure_service.get_capital_structure(db_session, issuer.id)

    assert result is not None
    assert result.issuer_legal_name == "Capstruct Service Test Empty Co"
    assert result.positions == []


def test_get_capital_structure_returns_positions_in_rank_order_with_provenance(
    db_session: Session,
) -> None:
    issuer_provenance = provenance_repository.create_provenance(
        db_session, reported_public_provenance()
    )
    issuer = issuer_repository.create_issuer(
        db_session,
        IssuerCreate(
            legal_name="Capstruct Service Test Stack Co", provenance_id=issuer_provenance.id
        ),
    )
    for rank, name, instrument_type in (
        (2, "Second Lien Notes", CapitalStructureInstrumentType.SECOND_LIEN),
        (1, "First Lien Term Loan B", CapitalStructureInstrumentType.FIRST_LIEN_LOAN),
    ):
        position_provenance = provenance_repository.create_provenance(
            db_session, reported_public_provenance(source_record_id=f"capstruct-{rank}")
        )
        capital_structure_repository.create_position(
            db_session,
            CapitalStructurePositionCreate(
                issuer_id=issuer.id,
                layer_name=name,
                rank_order=rank,
                instrument_type=instrument_type,
                seniority=Seniority.FIRST_LIEN if rank == 1 else Seniority.SECOND_LIEN,
                secured=True,
                amount_outstanding=Decimal("100000000"),
                provenance_id=position_provenance.id,
            ),
        )

    result = capital_structure_service.get_capital_structure(db_session, issuer.id)

    assert result is not None
    assert [p.layer_name for p in result.positions] == [
        "First Lien Term Loan B",
        "Second Lien Notes",
    ]
    assert result.positions[0].provider is not None
    assert result.positions[0].freshness is not None
