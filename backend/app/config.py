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

    # Supabase / database
    database_url: str | None = None
    direct_database_url: str | None = None
    supabase_url: str | None = None
    supabase_service_role_key: str | None = None
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

    # AI / LLM gate
    llm_provider: str = "anthropic"
    llm_api_key: str | None = None

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
