"""Route-level (FastAPI request/response shape) tests for the Research
Notes API's cross-issuer listing (Research Notes workspace
discoverability follow-up to Milestone 10A).

`GET /api/research-notes` is read-only, so — like `tests/
test_search_routes.py` — these tests can safely hit the route with real
queries against the live `nexus` schema, no mutation risk.
"""

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient


def test_list_notes_without_issuer_id_returns_200_with_issuer_fields(client: TestClient) -> None:
    response = client.get("/api/research-notes")
    assert response.status_code == 200
    body = response.json()
    assert "notes" in body
    for note in body["notes"]:
        assert "issuer_legal_name" in note
        assert "issuer_ticker" in note
        assert "issuer_id" in note


def test_list_notes_with_issuer_id_scopes_results(client: TestClient) -> None:
    unscoped = client.get("/api/research-notes").json()["notes"]
    if not unscoped:
        return  # Nothing to scope-check against in an empty environment.
    issuer_id = unscoped[0]["issuer_id"]

    response = client.get("/api/research-notes", params={"issuer_id": issuer_id})
    assert response.status_code == 200
    body = response.json()
    assert all(note["issuer_id"] == issuer_id for note in body["notes"])


def test_list_notes_with_unknown_issuer_id_returns_empty_list(client: TestClient) -> None:
    response = client.get("/api/research-notes", params={"issuer_id": str(uuid4())})
    assert response.status_code == 200
    assert response.json()["notes"] == []


def test_list_notes_invalid_issuer_id_is_rejected(client: TestClient) -> None:
    response = client.get("/api/research-notes", params={"issuer_id": "not-a-uuid"})
    assert response.status_code == 422
