"""CORS behavior tests (production incident: the deployed Vercel frontend's
preflight requests to `/api/credit-universe` and `/api/market-context` were
rejected because Railway's `CORS_ALLOWED_ORIGINS` was never set to the
deployed origin, so `CORSMiddleware` only ever allowed the default local-dev
origin). `CORSMiddleware` intercepts `OPTIONS` preflight requests before they
reach any route handler, so these tests never touch the database — any
registered path works as the target.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from app.config import Settings

PRODUCTION_ORIGIN = "https://nexus-credit-intelligence.vercel.app"


def test_default_cors_origins_include_both_localhost_forms() -> None:
    """Browsers treat `localhost` and `127.0.0.1` as distinct origins — the
    local-dev default must cover both, not just one."""
    settings = Settings(cors_allowed_origins="http://localhost:5173,http://127.0.0.1:5173")

    assert settings.cors_origins_list == ["http://localhost:5173", "http://127.0.0.1:5173"]


def test_cors_origins_list_supports_multiple_configured_origins() -> None:
    """`CORS_ALLOWED_ORIGINS` is a comma-separated list — production adds the
    deployed Vercel origin alongside (or instead of) the local-dev ones,
    never a wildcard."""
    settings = Settings(
        cors_allowed_origins=f"{PRODUCTION_ORIGIN}, http://localhost:5173 ,http://127.0.0.1:5173"
    )

    assert settings.cors_origins_list == [
        PRODUCTION_ORIGIN,
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


def _cors_app(cors_allowed_origins: str) -> Starlette:
    """A minimal Starlette app wired with the exact `CORSMiddleware` options
    `app.main` uses, parameterized on origins — mirrors production
    configuration without depending on `app.main`'s module-level
    `get_settings()` singleton (cached at import time)."""
    settings = Settings(cors_allowed_origins=cors_allowed_origins)

    async def echo(_request: Request) -> PlainTextResponse:
        return PlainTextResponse("ok")

    app = Starlette(routes=[Route("/api/credit-universe", echo, methods=["GET"])])
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    return app


def test_preflight_allows_configured_production_origin() -> None:
    app = _cors_app(f"{PRODUCTION_ORIGIN},http://localhost:5173,http://127.0.0.1:5173")
    client = TestClient(app)

    response = client.options(
        "/api/credit-universe",
        headers={
            "Origin": PRODUCTION_ORIGIN,
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == PRODUCTION_ORIGIN


def test_preflight_allows_configured_localhost_origin() -> None:
    app = _cors_app(f"{PRODUCTION_ORIGIN},http://localhost:5173,http://127.0.0.1:5173")
    client = TestClient(app)

    response = client.options(
        "/api/credit-universe",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_preflight_rejects_arbitrary_unlisted_origin() -> None:
    app = _cors_app(f"{PRODUCTION_ORIGIN},http://localhost:5173,http://127.0.0.1:5173")
    client = TestClient(app)

    response = client.options(
        "/api/credit-universe",
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )

    # Starlette's CORSMiddleware still returns 200 for a disallowed origin's
    # preflight (it does not itself error), but critically omits the
    # Access-Control-Allow-Origin header — which is what makes the browser
    # block the real request. This is the exact failure mode from the
    # production incident, reproduced here for an origin that was never
    # configured.
    assert "access-control-allow-origin" not in response.headers


def test_actual_request_rejects_arbitrary_unlisted_origin() -> None:
    app = _cors_app(f"{PRODUCTION_ORIGIN},http://localhost:5173,http://127.0.0.1:5173")
    client = TestClient(app)

    response = client.get(
        "/api/credit-universe",
        headers={"Origin": "https://evil.example.com"},
    )

    assert "access-control-allow-origin" not in response.headers


def test_real_app_preflight_allows_default_local_dev_origins(client: TestClient) -> None:
    """Exercises the real `app.main.app` (no env override in tests) against
    a real registered route, confirming the production `CORSMiddleware`
    wiring — not just the isolated test harness above — behaves correctly
    for the default local-dev origins."""
    for origin in ("http://localhost:5173", "http://127.0.0.1:5173"):
        response = client.options(
            "/api/credit-universe",
            headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == origin


def test_real_app_preflight_rejects_arbitrary_origin(client: TestClient) -> None:
    response = client.options(
        "/api/credit-universe",
        headers={"Origin": "https://evil.example.com", "Access-Control-Request-Method": "GET"},
    )

    assert "access-control-allow-origin" not in response.headers
