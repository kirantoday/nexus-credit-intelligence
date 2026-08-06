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

    # Auth (disabled for first demo; architecture supports Supabase Auth JWT later)
    auth_enabled: bool = False

    # Web / CORS
    frontend_url: str | None = None
    cors_allowed_origins: str = "http://localhost:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
