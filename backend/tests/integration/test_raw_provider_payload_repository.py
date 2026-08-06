"""Integration tests for raw_provider_payload_repository against the live nexus schema."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from app.core.types import ProviderName
from app.domain.raw_provider_payload import RawProviderPayloadCreate
from app.repositories import provenance_repository
from app.repositories import raw_provider_payload_repository as repo
from tests.integration.conftest import reported_public_provenance

_NOW = datetime.now(UTC)


def _payload(**overrides: object) -> RawProviderPayloadCreate:
    defaults: dict[str, object] = dict(
        provider=ProviderName.SEC_EDGAR,
        source_record_id="0000320193-24-000123",
        request_fingerprint="fingerprint-1",
        payload_json={"foo": "bar"},
        retrieved_at=_NOW,
        checksum="deadbeef",
        content_type="application/json",
    )
    defaults.update(overrides)
    return RawProviderPayloadCreate(**defaults)  # type: ignore[arg-type]


def test_create_and_get_payload(db_session: Session) -> None:
    created = repo.create_payload(db_session, _payload())
    assert created.id is not None

    fetched = repo.get_payload(db_session, created.id)
    assert fetched is not None
    assert fetched.checksum == "deadbeef"
    assert fetched.payload_json == {"foo": "bar"}


def test_get_payload_missing_returns_none(db_session: Session) -> None:
    assert repo.get_payload(db_session, uuid.uuid4()) is None


def test_get_by_request_fingerprint_found(db_session: Session) -> None:
    repo.create_payload(
        db_session,
        _payload(source_record_id="fp-test", request_fingerprint="unique-fingerprint-abc"),
    )
    found = repo.get_by_request_fingerprint(
        db_session, ProviderName.SEC_EDGAR.value, "unique-fingerprint-abc"
    )
    assert found is not None
    assert found.request_fingerprint == "unique-fingerprint-abc"


def test_get_by_request_fingerprint_not_found(db_session: Session) -> None:
    found = repo.get_by_request_fingerprint(db_session, ProviderName.SEC_EDGAR.value, "no-such-fp")
    assert found is None


def test_link_provenance_sets_back_reference(db_session: Session) -> None:
    payload = repo.create_payload(db_session, _payload())
    provenance = provenance_repository.create_provenance(
        db_session, reported_public_provenance(raw_payload_id=payload.id)
    )

    linked = repo.link_provenance(db_session, payload.id, provenance.id)
    assert linked.provenance_id == provenance.id

    refetched = repo.get_payload(db_session, payload.id)
    assert refetched is not None
    assert refetched.provenance_id == provenance.id


def test_link_provenance_missing_payload_raises(db_session: Session) -> None:
    with pytest.raises(ValueError, match="not found"):
        repo.link_provenance(db_session, uuid.uuid4(), uuid.uuid4())


def test_storage_object_path_only_payload(db_session: Session) -> None:
    created = repo.create_payload(
        db_session,
        _payload(payload_json=None, storage_object_path="filings/aapl/10k.pdf"),
    )
    fetched = repo.get_payload(db_session, created.id)
    assert fetched is not None
    assert fetched.storage_object_path == "filings/aapl/10k.pdf"
    assert fetched.payload_json is None
