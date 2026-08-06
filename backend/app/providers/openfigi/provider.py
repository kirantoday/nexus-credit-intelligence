"""OpenFIGI provider orchestration: search -> persist raw payload -> normalize -> persist canonical.

Same pipeline shape as `sec_edgar/provider.py`: Provider (this module) ->
Provider DTO (`dto.py`) -> Normalizer (`normalizer.py`) -> Canonical Domain
Object (`app/domain/security.py`) -> Repository (`app/repositories/**`) ->
Postgres. Never opens a session or calls the ORM directly.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.types import ProviderName
from app.domain.security import Security
from app.providers.base import raw_payload_store
from app.providers.base.http_client import ThrottledHttpClient
from app.providers.openfigi import normalizer
from app.providers.openfigi.client import OpenFigiClient
from app.providers.openfigi.dto import OpenFigiSearchResult
from app.repositories import issuer_repository, provenance_repository, security_repository


@dataclass(frozen=True, slots=True)
class BondSearchResult:
    security: Security
    security_created: bool


@dataclass(frozen=True, slots=True)
class BondSearchIngestResult:
    bonds: list[BondSearchResult]


def search_and_ingest_issuer_bonds(
    db: Session,
    http_client: ThrottledHttpClient,
    *,
    issuer_id: UUID,
    query: str,
    exch_code: str = "TRACE",
    limit: int = 5,
) -> BondSearchIngestResult:
    """Search OpenFIGI for `query`'s real corporate bonds and ingest up to
    `limit` of them as `security` rows (PLAN.md section 18 step 5's "what
    security is this?").

    Requires the issuer to already exist (mirrors
    `sec_edgar.provider.ingest_aggregate_bond`) — this function only adds
    `security` rows to it, never creates issuers.

    Filtered to `exch_code = "TRACE"` (default): OpenFIGI's real search
    results for a US issuer include foreign-currency/foreign-market MTNs
    (Swiss, German exchanges) alongside genuine USD domestic bonds — `TRACE`
    is OpenFIGI's own marker for USD corporate bonds eligible for FINRA's
    TRACE tape, the clearest honest signal of "the US domestic bond market
    this platform covers" (and the same universe Milestone 11's TRACE
    adapter will eventually price).

    Idempotent per bond via `security.figi`'s unique index: a bond already
    ingested by an earlier call is returned as-is, not duplicated. Every call
    still fetches fresh and logs a new `raw_provider_payload` + `provenance`
    row per search, matching `sec_edgar.provider`'s audit-trail convention.
    """
    issuer = issuer_repository.get_issuer(db, issuer_id)
    if issuer is None:
        raise ValueError(f"no issuer {issuer_id} exists yet")

    client = OpenFigiClient(http_client)
    search_result = client.search(query, market_sec_des="Corp")
    payload = raw_payload_store.store_raw_payload(
        db,
        provider=ProviderName.OPENFIGI,
        source_record_id=query,
        url=search_result.url,
        raw_bytes=search_result.raw_bytes,
        payload_json=json.loads(search_result.raw_bytes),
        content_type=search_result.content_type,
        retrieved_at=search_result.retrieved_at,
        request_body=search_result.request_body,
    )

    candidates: list[OpenFigiSearchResult] = [
        result for result in search_result.dto.data if result.exchCode == exch_code
    ][:limit]

    bonds: list[BondSearchResult] = []
    for result in candidates:
        existing = security_repository.get_security_by_figi(db, result.figi)
        if existing is not None:
            bonds.append(BondSearchResult(security=existing, security_created=False))
            continue

        bond_provenance = provenance_repository.create_provenance(
            db,
            normalizer.normalize_bond_provenance(
                result,
                source_url=search_result.url,
                retrieved_at=search_result.retrieved_at,
                raw_payload_id=payload.id,
            ),
        )
        security = security_repository.create_security(
            db,
            normalizer.normalize_bond_security(
                result,
                issuer_id=issuer.id,
                issuer_legal_name=issuer.legal_name,
                provenance_id=bond_provenance.id,
            ),
        )
        bonds.append(BondSearchResult(security=security, security_created=True))

    return BondSearchIngestResult(bonds=bonds)
