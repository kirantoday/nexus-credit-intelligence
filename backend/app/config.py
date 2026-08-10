"""Application configuration.

Reads the environment-variable contract documented in PLAN.md's Environment
Variables section. Every field is optional except sensible defaults for feature
flags, so the app can boot in a bare environment (Milestone 1) and gain real
capability as each provider/integration is wired up in later milestones.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: Literal["local", "test", "staging", "production"] = "local"
    log_level: str = "INFO"

    # Supabase / database.
    #
    # This project shares a single Supabase project with another application.
    # Nexus owns nothing outside the `nexus` Postgres schema (see app/db/base.py's
    # NEXUS_SCHEMA and alembic/env.py) — it never reads, writes, or migrates the
    # other application's tables. DATABASE_URL is the pooled/runtime connection;
    # DIRECT_DATABASE_URL is the non-pooled connection Alembic requires.
    database_url: str | None = None
    direct_database_url: str | None = None
    supabase_url: str | None = None
    supabase_anon_key: str | None = None
    supabase_service_key: str | None = None
    supabase_storage_bucket: str | None = None

    # Public data providers
    sec_user_agent: str | None = None
    fred_api_key: str | None = None
    openfigi_api_key: str | None = None
    courtlistener_api_token: str | None = None

    # FINRA TRACE (marketplace OAuth2 — real flow, unused in demo path)
    finra_client_id: str | None = None
    finra_client_secret: str | None = None

    # PACER — inactive/optional, see PLAN.md section 15. Never required to boot.
    pacer_username: str | None = None
    pacer_password: str | None = None
    pacer_enabled: bool = False

    # Disabled/licensed providers — interfaces only
    sp_global_enabled: bool = False
    octus_enabled: bool = False
    bloomberg_enabled: bool = False
    lseg_lpc_enabled: bool = False

    # AI / LLM gate (Milestone 6.5, PLAN.md section 24.7). Provider-specific
    # credentials, never a shared generic secret — `app/ai/factory.py` reads
    # llm_provider and validates only that provider's own fields, so an
    # unconfigured OPENAI_API_KEY never blocks booting with LLM_PROVIDER=anthropic
    # and a provider is never silently substituted for another.
    llm_provider: str = "anthropic"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-5"
    openai_api_key: str | None = None
    openai_model: str | None = None
    azure_openai_api_key: str | None = None
    azure_openai_endpoint: str | None = None
    azure_openai_model: str | None = None
    # Reserved, unused until a future milestone implements embeddings — chat/
    # tool-calling and embeddings may end up sourced from different vendors.
    embedding_provider: str | None = None

    # Model routing (PLAN.md Milestone 7.5.3 AI cost-control correction).
    # `anthropic_model` above stays the Sonnet identity (unchanged, still the
    # single-model default for any caller not going through the router, e.g.
    # `app.scripts.reclassify_system_universes`). These are read exclusively
    # by `app.ai.model_router` — no other module should embed a model id.
    ai_haiku_model_id: str = "claude-haiku-4-5-20251001"
    ai_sonnet_model_id: str = "claude-sonnet-5"
    ai_routing_enabled: bool = True
    # Below this Haiku-reported confidence, escalate to Sonnet once.
    # Never applied to definitive/high-impact categories (Chapter 11,
    # bankruptcy/receivership, plan-confirmed) — those always go straight
    # to Sonnet regardless of any Haiku confidence, per PLAN.md Milestone
    # 7.5.3's live quality-validation finding: Haiku's self-reported
    # confidence is not a reliable enough signal for that category.
    ai_haiku_confidence_threshold: float = 0.75
    # Below this Layer-1 rule confidence (the *strongest* candidate in the
    # bundle), no AI call is made at all — the bundle is genuinely too weak
    # a signal to spend anything reviewing. Layer 1's real calibrated rules
    # today all sit at >= 0.5, so this is a deliberately conservative floor
    # that is a no-op against current rule data, not a lever tuned to cut
    # real recall — see PLAN.md Milestone 7.5.3's AI cost-control report.
    ai_deterministic_confidence_floor: float = 0.5
    # Hard per-run budgets. `None` = unlimited (this module's own default —
    # a batch/backfill caller, e.g. `run_market_discovery.py`, always passes
    # explicit values; nothing here silently caps interactive/low-volume
    # callers like the nightly monitor unless configured to).
    ai_max_calls_per_run: int | None = None
    ai_max_cost_usd_per_run: float | None = None
    ai_max_sonnet_calls_per_run: int | None = None
    # Bounded retry on a transient provider failure (network/5xx/429) before
    # a single routed call is treated as failed and the router falls back to
    # escalation-or-deterministic. Deliberately small and fixed — see the
    # CourtListener Retry-After incident this same milestone fixed for why
    # an unbounded wait is never acceptable in this codebase again.
    ai_call_max_attempts: int = 2
    ai_call_retry_delay_seconds: float = 2.0

    # CourtListener Retry-After ceiling (PLAN.md Milestone 7.5.3): the
    # maximum this codebase will ever `time.sleep()` for a single retry,
    # regardless of what a provider's `Retry-After` header requests. Beyond
    # this, the operation is marked retryable/deferred instead of blocking.
    courtlistener_retry_after_max_seconds: float = 60.0

    # Auth (disabled for first demo; architecture supports Supabase Auth JWT later)
    auth_enabled: bool = False

    # Web / CORS. `cors_allowed_origins` is a comma-separated list of exact
    # origins (scheme + host + optional port, no path, no trailing slash) —
    # never a wildcard, so credentialed cross-origin requests from the
    # deployed frontend work correctly. The local-dev default covers both
    # localhost and 127.0.0.1 since browsers treat them as distinct origins;
    # production sets this via the Railway service's own environment
    # variable to the deployed Vercel origin(s), never committed here.
    frontend_url: str | None = None
    cors_allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
