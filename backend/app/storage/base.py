"""`StorageClient` Protocol (Milestone 10B) — no application code depends on
a vendor storage SDK directly, mirroring `app.ai.providers.base.LLMProvider`'s
already-established shape (ADR-010).

Only two implementations exist: `SupabaseStorageClient` (real, plain `httpx`
against Supabase Storage's REST API — no `supabase-py` dependency, per the
explicit decision to match this project's existing per-provider `httpx`
style) and `FakeStorageClient` (in-memory, used by tests so no test run ever
touches a real bucket).

Every uploaded object is private — `create_signed_url` is the only read
path this protocol exposes; there is no `get_public_url` and never will be
for this bucket.
"""

from __future__ import annotations

from typing import Protocol


class StorageError(Exception):
    """A Storage operation (upload/delete/sign) failed. Callers distinguish
    this from a validation error (e.g. `InvalidPdfError`) — a `StorageError`
    means the file may or may not have reached durable storage, which is
    exactly the ambiguity `research_document_service`'s compensating-delete
    logic exists to handle."""


class StorageClient(Protocol):
    def upload(self, *, key: str, content: bytes, content_type: str) -> None:
        """Uploads `content` to `key`. Raises `StorageError` on failure.
        Callers always generate a fresh, never-before-used `key` (a UUID-
        based path) — this method never needs upsert semantics."""
        ...

    def delete(self, *, key: str) -> None:
        """Deletes the object at `key`. Raises `StorageError` on failure —
        callers using this for compensating cleanup must catch and log
        distinctly rather than let a double-failure vanish silently."""
        ...

    def create_signed_url(self, *, key: str, expires_in_seconds: int) -> str:
        """Returns a short-lived, fully-qualified signed URL for `key`.
        Raises `StorageError` if the object doesn't exist or signing fails."""
        ...
