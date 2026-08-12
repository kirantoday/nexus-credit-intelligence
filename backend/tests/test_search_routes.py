"""Route-level (FastAPI request/response shape) tests for the Universal
Search API (PLAN.md 4.13, 8; Milestone 12A).

`GET /api/search` is read-only, so unlike `tests/test_alerts_routes.py`
(which has to stay read-only by targeting a nonexistent id), these tests
can safely hit the route with real, arbitrary queries against the live
`nexus` schema — no mutation risk either way.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_search_returns_200_with_expected_shape(client: TestClient) -> None:
    response = client.get("/api/search", params={"q": "Trinseo", "limit": 5})
    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "Trinseo"
    assert "exact_matches" in body
    assert "groups" in body
    assert isinstance(body["groups"], list)


def test_search_empty_query_returns_empty_result_shape(client: TestClient) -> None:
    response = client.get("/api/search", params={"q": ""})
    assert response.status_code == 200
    body = response.json()
    assert body["exact_matches"] == []
    assert body["groups"] == []


def test_search_missing_q_param_defaults_to_empty(client: TestClient) -> None:
    """`q` has a default, so a request with no query param at all must not
    422 — it should behave like an empty search."""
    response = client.get("/api/search")
    assert response.status_code == 200
    assert response.json()["groups"] == []


def test_search_limit_out_of_range_is_rejected(client: TestClient) -> None:
    response = client.get("/api/search", params={"q": "Trinseo", "limit": 100})
    assert response.status_code == 422


def test_search_group_entity_types_are_within_the_approved_set(client: TestClient) -> None:
    """Locks in the exclusions from the architecture review: no group in a
    real response may ever be research_evidence, research_note_version,
    audit_event, or docket_document — those have no repository function
    and no `SearchEntityType` member at all, but this test proves it end
    to end through the real route, not just by code inspection.
    `research_document` was added (title/metadata only) in Milestone
    10B-5."""
    allowed = {
        "issuer",
        "security",
        "alert_event",
        "court_docket",
        "court_docket_entry",
        "collection",
        "research_note",
        "research_document",
        "sec_filing",
    }
    response = client.get("/api/search", params={"q": "the", "limit": 5})
    assert response.status_code == 200
    body = response.json()
    for group in body["groups"]:
        assert group["entity_type"] in allowed
    for hit in body["exact_matches"]:
        assert hit["entity_type"] in allowed
