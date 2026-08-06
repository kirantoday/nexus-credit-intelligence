"""FastAPI application entrypoint."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.alerts import router as alerts_router
from app.api.routes.capital_structure import router as capital_structure_router
from app.api.routes.credit_universe import router as credit_universe_router
from app.api.routes.filing_monitor import router as filing_monitor_router
from app.api.routes.health import router as health_router
from app.api.routes.issuer import router as issuer_router
from app.api.routes.market_context import router as market_context_router
from app.api.routes.morning_brief import router as morning_brief_router
from app.api.routes.research_evidence import router as research_evidence_router
from app.api.routes.research_universes import router as research_universes_router
from app.config import get_settings
from app.logging_config import configure_logging

configure_logging()
settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    yield


app = FastAPI(
    title="Nexus Credit Intelligence API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(credit_universe_router)
app.include_router(market_context_router)
app.include_router(issuer_router)
app.include_router(capital_structure_router)
app.include_router(research_universes_router)
app.include_router(filing_monitor_router)
app.include_router(research_evidence_router)
app.include_router(alerts_router)
app.include_router(morning_brief_router)
