"""CourtListener provider orchestration: fetch -> raw payload -> normalize -> persist.

The same fixed pipeline every other provider in this codebase follows
(PLAN.md section 3): Provider (this module) -> Provider DTO (`dto.py`) ->
Normalizer (`normalizer.py`) -> Canonical Domain Object (`app/domain/**`) ->
Repository (`app/repositories/**`) -> Postgres. Never opens a session or
calls the ORM directly.

Docket discovery is deliberately **not** an automatic, watermark-driven feed
the way SEC's per-CIK `filings.recent` is (`app.services.filing_monitor_service`).
There is no reliable "list every new PACER case for issuer X" endpoint
without either a paid PACER account or a maintained party-name index this
project doesn't have — CourtListener's real, live-verified Search API
(`search_dockets` below) is free-text and requires a human/script to confirm
a match is actually the right issuer, the same live-verification discipline
`app.scripts.seed_research_universes` already established for SEC issuer
identity. Once a real docket is confirmed and linked to a real `issuer_id`
(`link_docket`), its entries sync idempotently and safely re-run
(`sync_docket_entries`) — no separate watermark table is needed because
idempotency is per-entry via CourtListener's own stable `courtlistener_entry_id`,
the same role `sec_filing.accession_no` plays for SEC filings.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.types import ProviderName
from app.domain.court_docket import CourtDocket
from app.domain.court_docket_entry import CourtDocketEntry
from app.domain.docket_document import DocketDocument
from app.providers.base import raw_payload_store
from app.providers.base.http_client import ThrottledHttpClient
from app.providers.courtlistener import normalizer
from app.providers.courtlistener.client import CourtListenerClient
from app.providers.courtlistener.dto import CourtListenerSearchResultDTO
from app.repositories import (
    court_docket_entry_repository,
    court_docket_repository,
    docket_document_repository,
    provenance_repository,
    raw_provider_payload_repository,
)

# Real, live-observed pagination safety cap — a single complex Chapter 11
# case can run to hundreds of docket entries; this bounds one sync call so a
# single unusually large docket can't stall the whole ingestion run. A
# capped sync is still fully idempotent and safe to re-run to pick up the
# remainder.
_MAX_ENTRY_PAGES = 25


@dataclass(frozen=True, slots=True)
class DocketSearchCandidate:
    dto: CourtListenerSearchResultDTO
    raw_payload_id: UUID
    source_url: str
    retrieved_at: datetime


def search_dockets(
    db: Session, http_client: ThrottledHttpClient, *, query: str, court: str | None = None
) -> list[DocketSearchCandidate]:
    """Real-time RECAP docket search — the only discovery mechanism this
    milestone has (see module docstring). Stores one raw-payload audit row
    per search call; does **not** create any `court_docket` row itself —
    the caller (a human reviewing candidates, or a seed script matching a
    known real case) decides which result, if any, is the right issuer via
    `link_docket`.
    """
    client = CourtListenerClient(http_client)
    result = client.search_dockets(query, court=court)
    payload = raw_payload_store.store_raw_payload(
        db,
        provider=ProviderName.COURTLISTENER,
        source_record_id=f"search:{query}",
        url=result.url,
        raw_bytes=result.raw_bytes,
        payload_json=json.loads(result.raw_bytes),
        content_type=result.content_type,
        retrieved_at=result.retrieved_at,
    )
    return [
        DocketSearchCandidate(
            dto=dto,
            raw_payload_id=payload.id,
            source_url=result.url,
            retrieved_at=result.retrieved_at,
        )
        for dto in result.dto.results
    ]


def link_docket(
    db: Session, *, issuer_id: UUID | None, candidate: DocketSearchCandidate
) -> tuple[CourtDocket, bool]:
    """Create (or reuse) a `court_docket` row for a search candidate the
    caller has confirmed is the right case for `issuer_id`. Idempotent by
    `courtlistener_docket_id`."""
    docket_provenance = provenance_repository.create_provenance(
        db,
        normalizer.normalize_court_docket_provenance(
            candidate.dto,
            source_url=candidate.source_url,
            retrieved_at=candidate.retrieved_at,
            raw_payload_id=candidate.raw_payload_id,
        ),
    )
    raw_provider_payload_repository.link_provenance(
        db, candidate.raw_payload_id, docket_provenance.id
    )
    return court_docket_repository.create_docket(
        db,
        normalizer.normalize_court_docket(
            candidate.dto, issuer_id=issuer_id, provenance_id=docket_provenance.id
        ),
    )


@dataclass(frozen=True, slots=True)
class DocketEntryIngestResult:
    entry: CourtDocketEntry
    entry_created: bool
    documents: list[DocketDocument]
    # The entry's own description plus any attached, non-sealed document's
    # already-extracted plain text (CourtListener returns it inline — never
    # a re-fetch, unlike SEC's separate filing-document fetch). What Layer 1
    # distress rules (`app.core.distress_rules.match_rules`) run against.
    match_text: str
    # The raw payload this entry came from — carried through so the caller
    # (`app.services.court_docket_service`) can create one fresh `provenance`
    # row per matched distress rule, all pointing at this same payload,
    # without a re-query. Mirrors `FilingTextResult`'s shape from the SEC
    # adapter (same "one raw payload, many provenance rows" pattern).
    raw_payload_id: UUID
    source_url: str
    retrieved_at: datetime


def sync_docket_entries(
    db: Session, http_client: ThrottledHttpClient, *, docket: CourtDocket
) -> list[DocketEntryIngestResult]:
    """Fetch and persist every *new* entry (and its non-sealed, available
    documents) for one already-linked docket. Idempotent: re-running is a
    safe no-op for entries already ingested (get-or-create by
    `courtlistener_entry_id`/`courtlistener_document_id`).

    **TD-012 incremental sync** (PLAN.md Milestone 7.5): a docket that has
    already been synced at least once uses
    `client.docket_entries_incremental_url` (`id__gt=<max already-synced
    courtlistener_entry_id>&order_by=id`) instead of re-walking the full
    pagination from page 1 — verified live via a real `OPTIONS` request
    against the docket-entries endpoint before this was implemented,
    confirming `id` supports `gt`/`gte` filters and `order_by=id`. A
    docket's first-ever sync (no entries on file yet) still uses the
    original full-pagination walk (`client.docket_entries_url`,
    `order_by=entry_number`) — historical backfill is unaffected. `id` is
    CourtListener's own globally monotonic identifier, so this incremental
    filter needs no overlap margin the way a timestamp-based cursor would:
    `id__gt` can never re-fetch or skip an entry.

    Requires `COURTLISTENER_API_TOKEN` — the docket-entries endpoint
    returns 401 anonymously (confirmed live, unlike the Search API used by
    `search_dockets`). The caller (`app.services.court_docket_service`)
    checks for a configured token before calling this and reports a clear,
    non-crashing reason when one isn't configured, matching this project's
    "stays operational without an optional credential" pattern.
    """
    client = CourtListenerClient(http_client)
    docket_source_url = f"https://www.courtlistener.com/docket/{docket.courtlistener_docket_id}/"

    max_synced_entry_id = court_docket_entry_repository.get_max_courtlistener_entry_id(
        db, docket.id
    )
    results: list[DocketEntryIngestResult] = []
    url: str | None = (
        client.docket_entries_incremental_url(
            docket.courtlistener_docket_id, since_entry_id=max_synced_entry_id
        )
        if max_synced_entry_id is not None
        else client.docket_entries_url(docket.courtlistener_docket_id)
    )
    pages_fetched = 0
    while url is not None and pages_fetched < _MAX_ENTRY_PAGES:
        page = client.fetch_docket_entries_page(url)
        pages_fetched += 1
        payload = raw_payload_store.store_raw_payload(
            db,
            provider=ProviderName.COURTLISTENER,
            source_record_id=f"docket-entries:{docket.courtlistener_docket_id}:page{pages_fetched}",
            url=page.url,
            raw_bytes=page.raw_bytes,
            payload_json=json.loads(page.raw_bytes),
            content_type=page.content_type,
            retrieved_at=page.retrieved_at,
        )

        for entry_dto in page.dto.results:
            entry_provenance = provenance_repository.create_provenance(
                db,
                normalizer.normalize_docket_entry_provenance(
                    entry_dto,
                    docket_source_url=docket_source_url,
                    retrieved_at=page.retrieved_at,
                    raw_payload_id=payload.id,
                ),
            )
            raw_provider_payload_repository.link_provenance(db, payload.id, entry_provenance.id)

            entry, entry_created = court_docket_entry_repository.create_entry(
                db,
                normalizer.normalize_docket_entry(
                    entry_dto, docket_id=docket.id, provenance_id=entry_provenance.id
                ),
            )

            documents: list[DocketDocument] = []
            if entry_created:
                for document_dto in entry_dto.recap_documents:
                    document_provenance = provenance_repository.create_provenance(
                        db,
                        normalizer.normalize_docket_document_provenance(
                            document_dto,
                            entry_source_url=docket_source_url,
                            entry_date=entry.entry_date,
                            retrieved_at=page.retrieved_at,
                            raw_payload_id=payload.id,
                        ),
                    )
                    raw_provider_payload_repository.link_provenance(
                        db, payload.id, document_provenance.id
                    )
                    document, _created = docket_document_repository.create_document(
                        db,
                        normalizer.normalize_docket_document(
                            document_dto,
                            docket_entry_id=entry.id,
                            provenance_id=document_provenance.id,
                            raw_payload_id=payload.id,
                        ),
                    )
                    documents.append(document)

            document_texts = [
                doc.plain_text
                for doc in entry_dto.recap_documents
                if doc.plain_text and not doc.is_sealed_or_unknown
            ]
            match_text = " ".join([entry.description, *document_texts]).strip()

            results.append(
                DocketEntryIngestResult(
                    entry=entry,
                    entry_created=entry_created,
                    documents=documents,
                    match_text=match_text,
                    raw_payload_id=payload.id,
                    source_url=docket_source_url,
                    retrieved_at=page.retrieved_at,
                )
            )

        url = page.dto.next

    return results
