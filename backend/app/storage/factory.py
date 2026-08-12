"""Resolves configured Supabase Storage settings to a concrete
`SupabaseStorageClient` (Milestone 10B) — mirrors `app.ai.factory.
get_llm_provider`'s shape.

Never falls back to a fake/no-op client in production; raises a clear,
specific error naming exactly which setting is missing rather than a
confusing failure deep inside an upload request.
"""

from __future__ import annotations

from app.config import Settings
from app.storage.supabase_storage_client import SupabaseStorageClient


class StorageConfigurationError(Exception):
    """Required Supabase Storage configuration is missing."""


def get_storage_client(settings: Settings) -> SupabaseStorageClient:
    missing = [
        name
        for name, value in (
            ("SUPABASE_URL", settings.supabase_url),
            ("SUPABASE_SERVICE_KEY", settings.supabase_service_key),
            ("SUPABASE_STORAGE_BUCKET", settings.supabase_storage_bucket),
        )
        if not value
    ]
    if missing:
        raise StorageConfigurationError(
            "Research document upload requires the following environment "
            f"variable(s) to be configured: {', '.join(missing)}"
        )
    assert settings.supabase_url is not None
    assert settings.supabase_service_key is not None
    assert settings.supabase_storage_bucket is not None
    return SupabaseStorageClient(
        base_url=settings.supabase_url,
        service_key=settings.supabase_service_key,
        bucket=settings.supabase_storage_bucket,
    )
