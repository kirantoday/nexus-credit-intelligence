"""Real `StorageClient` implementation against Supabase Storage's REST API
(Milestone 10B).

Plain `httpx` (already a project dependency, used the same way every
provider adapter — SEC/FRED/CourtListener/OpenFIGI — already calls its own
external API), not the `supabase-py` SDK, per the explicit decision to keep
this project's dependency footprint and calling style consistent.

Every endpoint used here was verified live against the real, empty
`nexus-research-documents` bucket before this module was written (upload,
sign, download-via-signed-URL, delete, list all round-tripped a real test
object) — not implemented from memory of the API shape.

Auth: `SUPABASE_SERVICE_KEY` only, sent as both `Authorization: Bearer` and
`apikey` — backend-only, never exposed to the frontend/Vercel (see
`app.config.Settings`'s docstring and CLAUDE.md's environment-variable
rules). There is no anon-key/browser-facing path in this module at all.
"""

from __future__ import annotations

import httpx

from app.storage.base import StorageError


class SupabaseStorageClient:
    def __init__(
        self,
        *,
        base_url: str,
        service_key: str,
        bucket: str,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._bucket = bucket
        self._storage_base = f"{base_url.rstrip('/')}/storage/v1"
        self._client = http_client or httpx.Client(
            headers={
                "Authorization": f"Bearer {service_key}",
                "apikey": service_key,
            },
            timeout=30.0,
        )

    def upload(self, *, key: str, content: bytes, content_type: str) -> None:
        try:
            response = self._client.post(
                f"{self._storage_base}/object/{self._bucket}/{key}",
                content=content,
                headers={"Content-Type": content_type},
            )
        except httpx.HTTPError as exc:
            raise StorageError(f"upload request failed for key {key!r}: {exc}") from exc
        if response.status_code >= 400:
            raise StorageError(
                f"upload failed for key {key!r}: {response.status_code} {response.text[:500]}"
            )

    def download(self, *, key: str) -> bytes:
        try:
            response = self._client.get(f"{self._storage_base}/object/{self._bucket}/{key}")
        except httpx.HTTPError as exc:
            raise StorageError(f"download request failed for key {key!r}: {exc}") from exc
        if response.status_code >= 400:
            raise StorageError(
                f"download failed for key {key!r}: {response.status_code} {response.text[:500]}"
            )
        return response.content

    def delete(self, *, key: str) -> None:
        try:
            response = self._client.delete(f"{self._storage_base}/object/{self._bucket}/{key}")
        except httpx.HTTPError as exc:
            raise StorageError(f"delete request failed for key {key!r}: {exc}") from exc
        if response.status_code >= 400:
            raise StorageError(
                f"delete failed for key {key!r}: {response.status_code} {response.text[:500]}"
            )

    def create_signed_url(self, *, key: str, expires_in_seconds: int) -> str:
        try:
            response = self._client.post(
                f"{self._storage_base}/object/sign/{self._bucket}/{key}",
                json={"expiresIn": expires_in_seconds},
            )
        except httpx.HTTPError as exc:
            raise StorageError(f"sign request failed for key {key!r}: {exc}") from exc
        if response.status_code >= 400:
            raise StorageError(
                f"sign failed for key {key!r}: {response.status_code} {response.text[:500]}"
            )
        signed_path = response.json().get("signedURL")
        if not signed_path:
            raise StorageError(f"sign response for key {key!r} had no signedURL: {response.text}")
        # Supabase returns a relative path (e.g. "/object/sign/{bucket}/{key}?token=...") —
        # verified live; always prefix with the storage base to get a usable URL.
        return f"{self._storage_base}{signed_path}"

    def close(self) -> None:
        self._client.close()
