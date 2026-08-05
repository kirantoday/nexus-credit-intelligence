"""Liveness check for Railway's health check.

Deliberately makes no external calls (no DB, no provider) — per PLAN.md
section 2, `/health` is a cheap liveness check, not a dependency check.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter

from app.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict[str, str]:
    settings = get_settings()
    return {
        "status": "healthy",
        "service": "nexus-credit-intelligence-api",
        "environment": settings.environment,
        "timestamp": datetime.now(UTC).isoformat(),
    }
