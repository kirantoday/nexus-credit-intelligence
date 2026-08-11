"""Route-level (FastAPI request/response shape) tests for the Alerts API.

Distinct from `tests/integration/test_filing_monitor_api_service.py`,
which exercises the service layer directly against the live `nexus`
schema — these tests instead go through the real HTTP route via
`TestClient`, catching a class of bug the service-layer tests structurally
cannot: FastAPI request-body parsing/validation mismatches between what
the frontend actually sends and what a route's parameter signature
expects. A nonexistent alert id keeps every test here read-only (no real
data mutated) while still proving the request body was accepted and
routed through to the service layer (404 "not found") rather than
rejected before it ever got there (422 validation error).
"""

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

_UNKNOWN_ALERT_ID = str(uuid4())


def test_acknowledge_accepts_the_frontend_s_request_body_shape(client: TestClient) -> None:
    """Live-caught Milestone 9 production regression: `acknowledge_alert`'s
    single un-embedded `Body()` parameter expected the raw request body to
    *be* the `acted_by` string directly, but the frontend (and
    `dismiss_alert`'s own two-`Body()`-parameter shape) has always sent
    `{"acted_by": ...}` — so every real acknowledge click in production
    was silently rejected with a 422 before ever reaching the service
    layer. Fixed with `Body(embed=True)`. A 404 here (not 422) proves the
    body was accepted and the request reached the "does this alert exist"
    check."""
    response = client.post(
        f"/api/alerts/{_UNKNOWN_ALERT_ID}/acknowledge",
        json={"acted_by": None},
    )
    assert response.status_code == 404


def test_dismiss_accepts_the_frontend_s_request_body_shape(client: TestClient) -> None:
    """`dismiss_alert` already has two `Body()` parameters, which FastAPI
    auto-embeds under their own keys — this test locks that behavior in
    so a future refactor can't silently reintroduce the acknowledge bug
    here too."""
    response = client.post(
        f"/api/alerts/{_UNKNOWN_ALERT_ID}/dismiss",
        json={"acted_by": None, "reason": None},
    )
    assert response.status_code == 404
