"""In-memory `StorageClient` fake (Milestone 10B) — used by unit/integration
tests so no test run ever touches a real Supabase Storage bucket. Mirrors
this project's existing pattern of testing against real live external calls
only where explicitly gated/skippable (see `tests/integration/conftest.py`'s
`sec_http_client`-style fixtures) — Storage, unlike those read-only public
APIs, would incur real writes/deletes against shared infrastructure, so it
gets a fake instead, not a skip-if-unconfigured live client.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.storage.base import StorageError


@dataclass
class FakeStorageClient:
    objects: dict[str, bytes] = field(default_factory=dict)
    # Test hooks: set to True to make the next call to that method raise
    # StorageError, simulating a real Storage-side failure.
    fail_next_upload: bool = False
    fail_next_delete: bool = False
    fail_next_sign: bool = False
    deleted_keys: list[str] = field(default_factory=list)

    def upload(self, *, key: str, content: bytes, content_type: str) -> None:
        if self.fail_next_upload:
            self.fail_next_upload = False
            raise StorageError(f"simulated upload failure for key {key!r}")
        self.objects[key] = content

    def delete(self, *, key: str) -> None:
        if self.fail_next_delete:
            self.fail_next_delete = False
            raise StorageError(f"simulated delete failure for key {key!r}")
        self.objects.pop(key, None)
        self.deleted_keys.append(key)

    def create_signed_url(self, *, key: str, expires_in_seconds: int) -> str:
        if self.fail_next_sign:
            self.fail_next_sign = False
            raise StorageError(f"simulated sign failure for key {key!r}")
        if key not in self.objects:
            raise StorageError(f"cannot sign missing key {key!r}")
        return f"https://fake-storage.test/{key}?expires_in={expires_in_seconds}"
