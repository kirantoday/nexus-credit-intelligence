"""Bridges a provider's fetched raw response into `raw_provider_payload`.

Computes the request fingerprint and content checksum and calls the
repository — the only persistence-adjacent thing a provider adapter does, and
even this doesn't open a session itself (the caller's session is passed
through). Every actual `session.add`/`flush` still happens exclusively inside
`app/repositories/**`, keeping PLAN.md section 3's domain-layer boundary
intact: provider code never imports `app.db.session` or opens a session.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.types import ProviderName
from app.domain.raw_provider_payload import RawProviderPayload, RawProviderPayloadCreate
from app.repositories import raw_provider_payload_repository


def fingerprint_request(url: str, *, body: object | None = None) -> str:
    """Hash of the request, for idempotent re-fetch checks (PLAN.md 4.4).

    `body` matters for POST-based APIs (e.g. OpenFIGI's search/mapping
    endpoints): the URL alone is the same for every query, so two distinct
    queries against it would otherwise collide on the same fingerprint.
    Omitted (the common GET case) for identical behavior to before.
    """
    fingerprint_input = url if body is None else f"{url}|{json.dumps(body, sort_keys=True)}"
    return hashlib.sha256(fingerprint_input.encode("utf-8")).hexdigest()


def checksum(raw_bytes: bytes) -> str:
    """Content hash of the raw response, to detect drift/corruption on replay."""
    return hashlib.sha256(raw_bytes).hexdigest()


def store_raw_payload(
    db: Session,
    *,
    provider: ProviderName,
    source_record_id: str,
    url: str,
    raw_bytes: bytes,
    payload_json: dict[str, Any] | list[Any] | None,
    content_type: str,
    retrieved_at: datetime,
    request_body: object | None = None,
) -> RawProviderPayload:
    return raw_provider_payload_repository.create_payload(
        db,
        RawProviderPayloadCreate(
            provider=provider,
            source_record_id=source_record_id,
            request_fingerprint=fingerprint_request(url, body=request_body),
            payload_json=payload_json,
            retrieved_at=retrieved_at,
            checksum=checksum(raw_bytes),
            content_type=content_type,
        ),
    )
