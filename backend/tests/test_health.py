from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_check_returns_200(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200


def test_health_check_payload_shape(client: TestClient) -> None:
    response = client.get("/health")
    data = response.json()

    assert data["status"] == "healthy"
    assert data["service"] == "nexus-credit-intelligence-api"
    assert "environment" in data
    assert "timestamp" in data
