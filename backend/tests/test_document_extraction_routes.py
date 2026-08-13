"""Route-level (FastAPI request/response shape) tests for the Document
Intelligence API (Milestone 10C).

Following `tests/test_research_documents_routes.py`'s and
`tests/test_alerts_routes.py`'s established convention: every test here
uses an unknown/nonexistent id, so no test mutates the live shared
`nexus` schema at this layer — full success-path behavior (real
extraction/chunking/promotion) is already covered thoroughly by
`tests/integration/test_document_extraction_service.py`, which uses
`FakeStorageClient` against real seeded data.
"""

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

_UNKNOWN_ID = str(uuid4())


def test_process_unknown_document_returns_404(client: TestClient) -> None:
    response = client.post(f"/api/research-documents/{_UNKNOWN_ID}/process", json={})
    assert response.status_code == 404


def test_list_extractions_for_unknown_document_returns_empty_list(client: TestClient) -> None:
    """No existence check on the list route (matches `research_documents`'
    own list-by-issuer precedent) — an unknown id is simply an empty
    result set, not an error."""
    response = client.get(f"/api/research-documents/{_UNKNOWN_ID}/extractions")
    assert response.status_code == 200
    assert response.json() == {"extractions": []}


def test_get_current_extraction_for_unknown_document_returns_404(client: TestClient) -> None:
    response = client.get(f"/api/research-documents/{_UNKNOWN_ID}/extractions/current")
    assert response.status_code == 404


def test_get_unknown_extraction_returns_404(client: TestClient) -> None:
    response = client.get(f"/api/document-extractions/{_UNKNOWN_ID}")
    assert response.status_code == 404


def test_list_chunks_for_unknown_extraction_returns_404(client: TestClient) -> None:
    response = client.get(f"/api/document-extractions/{_UNKNOWN_ID}/chunks")
    assert response.status_code == 404


def test_search_chunks_for_unknown_extraction_returns_404(client: TestClient) -> None:
    response = client.get(
        f"/api/document-extractions/{_UNKNOWN_ID}/chunks/search", params={"q": "covenant"}
    )
    assert response.status_code == 404


def test_search_chunks_requires_query_param(client: TestClient) -> None:
    response = client.get(f"/api/document-extractions/{_UNKNOWN_ID}/chunks/search")
    assert response.status_code == 422
