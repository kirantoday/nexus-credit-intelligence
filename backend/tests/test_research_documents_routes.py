"""Route-level (FastAPI request/response shape) tests for the Research
Documents API (PLAN.md 4.10, 4.12, 15; Milestone 10B).

Distinct from `tests/integration/test_research_document_service.py`, which
exercises the service layer directly with `FakeStorageClient` against the
live `nexus` schema — these tests instead go through the real HTTP route
via `TestClient`, catching request-parsing/validation mismatches (the same
class of bug `tests/test_alerts_routes.py` documents). Following that same
file's established convention, every test here uses an unknown/nonexistent
id or a request malformed enough to be rejected before reaching the
database, so no test here mutates the live shared `nexus` schema.

`_get_storage_client` is overridden with `FakeStorageClient` for every test
that exercises the download route, so no test here can ever make a real
network call to Supabase Storage, regardless of how the route's internal
code path evolves.
"""

from __future__ import annotations

from collections.abc import Iterator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.routes.research_documents import _get_storage_client
from app.main import app
from app.storage.fake_storage_client import FakeStorageClient

_UNKNOWN_ID = str(uuid4())


@pytest.fixture
def client_with_fake_storage() -> Iterator[TestClient]:
    fake = FakeStorageClient()
    app.dependency_overrides[_get_storage_client] = lambda: fake
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        del app.dependency_overrides[_get_storage_client]


def test_get_unknown_document_returns_404(client: TestClient) -> None:
    response = client.get(f"/api/research-documents/{_UNKNOWN_ID}")
    assert response.status_code == 404


def test_get_download_url_for_unknown_document_returns_404(
    client_with_fake_storage: TestClient,
) -> None:
    response = client_with_fake_storage.get(f"/api/research-documents/{_UNKNOWN_ID}/download")
    assert response.status_code == 404


def test_archive_unknown_document_returns_404(client: TestClient) -> None:
    response = client.post(
        f"/api/research-documents/{_UNKNOWN_ID}/archive", json={"archived_by": None}
    )
    assert response.status_code == 404


def test_update_metadata_of_unknown_document_returns_404(client: TestClient) -> None:
    response = client.patch(f"/api/research-documents/{_UNKNOWN_ID}", json={"title": "New Title"})
    assert response.status_code == 404


def test_list_documents_returns_200_with_summary_fields(client: TestClient) -> None:
    response = client.get("/api/research-documents")
    assert response.status_code == 200
    body = response.json()
    assert "documents" in body
    for document in body["documents"]:
        assert "issuer_legal_name" in document
        assert "issuer_ticker" in document
        assert "document_type" in document


def test_list_documents_invalid_document_type_is_rejected(client: TestClient) -> None:
    response = client.get("/api/research-documents", params={"document_type": "not_a_real_type"})
    assert response.status_code == 422


def test_upload_missing_required_form_fields_is_rejected(client: TestClient) -> None:
    """No `issuer_id`/`document_type`/`title`/`file` supplied at all —
    rejected before ever reaching the service layer or Storage."""
    response = client.post("/api/research-documents", data={})
    assert response.status_code == 422


def test_upload_invalid_issuer_id_shape_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/research-documents",
        data={
            "issuer_id": "not-a-uuid",
            "document_type": "credit_agreement",
            "title": "Test",
        },
        files={"file": ("test.pdf", b"%PDF-1.4\n", "application/pdf")},
    )
    assert response.status_code == 422


def test_upload_invalid_document_type_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/research-documents",
        data={
            "issuer_id": _UNKNOWN_ID,
            "document_type": "not_a_real_type",
            "title": "Test",
        },
        files={"file": ("test.pdf", b"%PDF-1.4\n", "application/pdf")},
    )
    assert response.status_code == 422
