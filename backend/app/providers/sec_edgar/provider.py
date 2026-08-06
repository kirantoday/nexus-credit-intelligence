"""SEC EDGAR provider orchestration: fetch -> persist raw payload -> normalize -> persist canonical.

The full pipeline PLAN.md section 18 step 3 requires proven end-to-end:
Provider (this module) -> Provider DTO (`dto.py`) -> Normalizer
(`normalizer.py`) -> Canonical Domain Object (`app/domain/**`) -> Repository
(`app/repositories/**`) -> Postgres. This is still the only SEC-specific
module that touches persistence, and even it never opens a session or calls
the ORM directly — every write goes through `app/repositories/**`, per
PLAN.md section 3's domain-layer boundary.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.types import ProviderName
from app.domain.financial_fact import FinancialFact
from app.domain.issuer import Issuer
from app.domain.raw_provider_payload import RawProviderPayload
from app.domain.sec_filing import SecFiling
from app.domain.security import Security
from app.providers.base import raw_payload_store
from app.providers.base.http_client import ThrottledHttpClient
from app.providers.sec_edgar import normalizer
from app.providers.sec_edgar.client import FetchResult, SecEdgarClient, format_cik10
from app.providers.sec_edgar.dto import (
    SecCompanyFactsDTO,
    SecSubmissionsDTO,
    SecXbrlUnitDatapoint,
    recent_filing_entries,
)
from app.repositories import (
    financial_fact_repository,
    issuer_repository,
    provenance_repository,
    raw_provider_payload_repository,
    sec_filing_repository,
    security_repository,
)


@dataclass(frozen=True, slots=True)
class IngestResult:
    issuer: Issuer
    financial_fact: FinancialFact
    issuer_created: bool
    financial_fact_created: bool


@dataclass(frozen=True, slots=True)
class BondIngestResult:
    security: Security
    security_created: bool


@dataclass(frozen=True, slots=True)
class FilingIngestResult:
    filing: SecFiling
    filing_created: bool
    # Raw, comma-separated 8-K item numbers from this ingestion's fetch
    # (e.g. "1.03,2.03") — transient, not persisted on `sec_filing`: the
    # overnight monitor (PLAN.md 24.5) uses it immediately for Layer 1 rule
    # matching in the same run that discovered the filing; re-deriving it
    # for an already-processed filing is never needed.
    item_codes: str | None


def _select_most_recent_datapoint(
    datapoints: list[SecXbrlUnitDatapoint],
) -> SecXbrlUnitDatapoint:
    """Most recent datapoint with complete fiscal metadata.

    Older SEC datapoints (roughly pre-2011) can have null `fy`/`fp`
    (`dto.py`'s `SecXbrlUnitDatapoint` docstring) — those can't populate a
    `financial_fact` row (`fiscal_year`/`fiscal_period` are required) and are
    excluded here rather than earlier, so a concept with only historical,
    incomplete data still fails with a clear "no usable datapoints" error
    instead of a silent domain-validation failure deeper in the pipeline.
    """
    usable = [d for d in datapoints if d.fy is not None and d.fp is not None]
    if not usable:
        raise ValueError("no datapoints with complete fiscal-year/period metadata")
    return max(usable, key=lambda d: d.end)


def _fetch_and_store_submissions(
    db: Session, client: SecEdgarClient, cik10: str
) -> tuple[FetchResult[SecSubmissionsDTO], RawProviderPayload]:
    """Shared by every caller that needs an issuer's submissions payload
    (identity ingestion, financial-fact ingestion, filing-list ingestion) —
    one fetch, one raw-payload audit row."""
    submissions = client.fetch_submissions(cik10)
    payload = raw_payload_store.store_raw_payload(
        db,
        provider=ProviderName.SEC_EDGAR,
        source_record_id=cik10,
        url=submissions.url,
        raw_bytes=submissions.raw_bytes,
        payload_json=json.loads(submissions.raw_bytes),
        content_type=submissions.content_type,
        retrieved_at=submissions.retrieved_at,
    )
    return submissions, payload


def _fetch_and_store_company_facts(
    db: Session, client: SecEdgarClient, cik10: str
) -> tuple[FetchResult[SecCompanyFactsDTO], RawProviderPayload]:
    """Shared by every concept extracted from company-facts (financial facts,
    aggregate bond data, and future concepts) — one fetch, one raw-payload
    audit row, reused for whichever concept(s) the caller then extracts."""
    company_facts = client.fetch_company_facts(cik10)
    payload = raw_payload_store.store_raw_payload(
        db,
        provider=ProviderName.SEC_EDGAR,
        source_record_id=cik10,
        url=company_facts.url,
        # Re-parsed with plain json.loads (not parse_float=Decimal) for
        # archival storage: JSONB doesn't need the Decimal precision guard
        # that app/domain/financial_fact.py's typed `value: Decimal` field
        # does, and Decimal isn't directly JSON-serializable.
        payload_json=json.loads(company_facts.raw_bytes),
        raw_bytes=company_facts.raw_bytes,
        content_type=company_facts.content_type,
        retrieved_at=company_facts.retrieved_at,
    )
    return company_facts, payload


def _extract_datapoint(
    dto: SecCompanyFactsDTO, cik10: str, concept: str, unit: str
) -> SecXbrlUnitDatapoint:
    concept_data = dto.facts.us_gaap.get(concept)
    if concept_data is None:
        raise ValueError(f"concept {concept!r} not found in company facts for CIK {cik10}")
    datapoints = concept_data.units.get(unit)
    if not datapoints:
        raise ValueError(f"unit {unit!r} not found for concept {concept!r} (CIK {cik10})")
    return _select_most_recent_datapoint(datapoints)


def ingest_issuer_and_one_financial_fact(
    db: Session,
    http_client: ThrottledHttpClient,
    *,
    cik: int | str,
    concept: str,
    unit: str = "USD",
) -> IngestResult:
    """Ingest one issuer's identity and its most recent value for `concept`.

    Idempotent on the canonical side: re-running with the same `cik`/`concept`
    reuses the existing `issuer`/`financial_fact` rows rather than duplicating
    them. Every call still fetches fresh and logs a new `raw_provider_payload`
    + `provenance` row per fetch — each retrieval is its own audit event, even
    when the canonical data it confirms hasn't changed.
    """
    cik10 = format_cik10(cik)
    client = SecEdgarClient(http_client)

    submissions, submissions_payload = _fetch_and_store_submissions(db, client, cik10)
    issuer_provenance = provenance_repository.create_provenance(
        db,
        normalizer.normalize_issuer_provenance(
            submissions.dto,
            source_url=submissions.url,
            retrieved_at=submissions.retrieved_at,
            raw_payload_id=submissions_payload.id,
        ),
    )
    raw_provider_payload_repository.link_provenance(
        db, submissions_payload.id, issuer_provenance.id
    )

    existing_issuer = issuer_repository.get_issuer_by_cik(db, cik10)
    if existing_issuer is not None:
        issuer = existing_issuer
        issuer_created = False
    else:
        issuer = issuer_repository.create_issuer(
            db, normalizer.normalize_issuer(submissions.dto, provenance_id=issuer_provenance.id)
        )
        issuer_created = True

    company_facts, company_facts_payload = _fetch_and_store_company_facts(db, client, cik10)
    datapoint = _extract_datapoint(company_facts.dto, cik10, concept, unit)
    # _select_most_recent_datapoint already filters to datapoints with both
    # set; asserted here so the type checker knows it for the dedup lookup
    # below (normalizer.normalize_financial_fact re-checks independently).
    assert datapoint.fy is not None and datapoint.fp is not None

    fact_provenance = provenance_repository.create_provenance(
        db,
        normalizer.normalize_financial_fact_provenance(
            datapoint,
            source_url=company_facts.url,
            retrieved_at=company_facts.retrieved_at,
            raw_payload_id=company_facts_payload.id,
        ),
    )
    raw_provider_payload_repository.link_provenance(
        db, company_facts_payload.id, fact_provenance.id
    )

    existing_fact = financial_fact_repository.get_by_dedup_key(
        db, issuer.id, concept, datapoint.accn, datapoint.fy, datapoint.fp
    )
    if existing_fact is not None:
        financial_fact = existing_fact
        financial_fact_created = False
    else:
        financial_fact = financial_fact_repository.create_financial_fact(
            db,
            normalizer.normalize_financial_fact(
                datapoint,
                issuer_id=issuer.id,
                concept=concept,
                unit=unit,
                provenance_id=fact_provenance.id,
            ),
        )
        financial_fact_created = True

    return IngestResult(
        issuer=issuer,
        financial_fact=financial_fact,
        issuer_created=issuer_created,
        financial_fact_created=financial_fact_created,
    )


def ingest_aggregate_bond(
    db: Session,
    http_client: ThrottledHttpClient,
    *,
    cik: int | str,
    concept: str = "LongTermDebtNoncurrent",
    unit: str = "USD",
) -> BondIngestResult:
    """Ingest one real, aggregate SEC-reported debt figure as a `security`
    row (PLAN.md section 18 step 4's "real SEC-sourced bonds").

    Requires the issuer to already exist (via
    `ingest_issuer_and_one_financial_fact`) — this function only adds a
    `security` row to it, it doesn't create issuers. See
    `normalizer.normalize_bond_security`'s docstring for why this is an
    honestly-described aggregate figure, not a specific bond issue.
    """
    cik10 = format_cik10(cik)
    issuer = issuer_repository.get_issuer_by_cik(db, cik10)
    if issuer is None:
        raise ValueError(
            f"no issuer with CIK {cik10} exists yet — call "
            "ingest_issuer_and_one_financial_fact first"
        )

    client = SecEdgarClient(http_client)
    company_facts, company_facts_payload = _fetch_and_store_company_facts(db, client, cik10)
    datapoint = _extract_datapoint(company_facts.dto, cik10, concept, unit)

    bond_provenance = provenance_repository.create_provenance(
        db,
        normalizer.normalize_bond_provenance(
            datapoint,
            source_url=company_facts.url,
            retrieved_at=company_facts.retrieved_at,
            raw_payload_id=company_facts_payload.id,
        ),
    )
    raw_provider_payload_repository.link_provenance(
        db, company_facts_payload.id, bond_provenance.id
    )

    existing = security_repository.list_securities_by_issuer(db, issuer.id)
    already_seeded = next(
        (s for s in existing if s.description.startswith(f"{issuer.legal_name} — Long-Term Debt")),
        None,
    )
    if already_seeded is not None:
        return BondIngestResult(security=already_seeded, security_created=False)

    security = security_repository.create_security(
        db,
        normalizer.normalize_bond_security(
            datapoint,
            issuer_id=issuer.id,
            issuer_legal_name=issuer.legal_name,
            provenance_id=bond_provenance.id,
        ),
    )
    return BondIngestResult(security=security, security_created=True)


def ingest_issuer_identity_only(
    db: Session, http_client: ThrottledHttpClient, *, cik: int | str
) -> tuple[Issuer, bool]:
    """Ensure an issuer's identity row exists, live-verified via a real
    submissions fetch — no financial fact, no bond security. Backs the
    Research Universe seed script (PLAN.md 24.2): a universe candidate only
    needs real identity confirmed, not any particular financial concept.

    Idempotent against issuers already created by an earlier milestone (e.g.
    Apple Inc. from Milestone 3) — checks `get_issuer_by_cik` first and skips
    the network call entirely when already known, per "avoid duplicate
    canonical issuers."
    """
    cik10 = format_cik10(cik)
    existing = issuer_repository.get_issuer_by_cik(db, cik10)
    if existing is not None:
        return existing, False

    client = SecEdgarClient(http_client)
    submissions, submissions_payload = _fetch_and_store_submissions(db, client, cik10)
    issuer_provenance = provenance_repository.create_provenance(
        db,
        normalizer.normalize_issuer_provenance(
            submissions.dto,
            source_url=submissions.url,
            retrieved_at=submissions.retrieved_at,
            raw_payload_id=submissions_payload.id,
        ),
    )
    raw_provider_payload_repository.link_provenance(
        db, submissions_payload.id, issuer_provenance.id
    )
    issuer = issuer_repository.create_issuer(
        db, normalizer.normalize_issuer(submissions.dto, provenance_id=issuer_provenance.id)
    )
    return issuer, True


def ingest_recent_filings(
    db: Session,
    http_client: ThrottledHttpClient,
    *,
    cik: int | str,
    forms: frozenset[str],
    since: date | None,
) -> list[FilingIngestResult]:
    """Fetch an issuer's recent filings and persist any not already known
    (PLAN.md 24.5 — the overnight monitor's per-issuer ingestion step).

    `since`: only filings with `filing_date > since` are ingested (the
    delta/backfill windowing the caller computes from the watermark). `None`
    means every filing in SEC's `filings.recent` window matching `forms` —
    the caller (`filing_monitor_service`) is responsible for never calling
    this unbounded in baseline mode, where PLAN.md 24.5 requires establishing
    a watermark without ingesting any filings at all.

    Idempotent: `sec_filing_repository.create_filing`'s get-or-create by
    `accession_no` means a re-processed filing is a no-op, never a duplicate.
    """
    cik10 = format_cik10(cik)
    issuer = issuer_repository.get_issuer_by_cik(db, cik10)
    if issuer is None:
        raise ValueError(f"no issuer with CIK {cik10} exists yet")

    client = SecEdgarClient(http_client)
    submissions, submissions_payload = _fetch_and_store_submissions(db, client, cik10)

    results: list[FilingIngestResult] = []
    for entry in recent_filing_entries(submissions.dto):
        if entry.form not in forms:
            continue
        entry_date = date.fromisoformat(entry.filing_date)
        if since is not None and entry_date <= since:
            continue

        filing_provenance = provenance_repository.create_provenance(
            db,
            normalizer.normalize_sec_filing_provenance(
                entry,
                source_url=submissions.url,
                retrieved_at=submissions.retrieved_at,
                raw_payload_id=submissions_payload.id,
            ),
        )
        raw_provider_payload_repository.link_provenance(
            db, submissions_payload.id, filing_provenance.id
        )

        primary_document_url = None
        if entry.primary_document:
            accession_nodash = entry.accession_no.replace("-", "")
            primary_document_url = (
                f"https://www.sec.gov/Archives/edgar/data/{int(cik10)}/"
                f"{accession_nodash}/{entry.primary_document}"
            )

        filing, created = sec_filing_repository.create_filing(
            db,
            normalizer.normalize_sec_filing(
                entry,
                issuer_id=issuer.id,
                primary_document_url=primary_document_url,
                provenance_id=filing_provenance.id,
            ),
        )
        results.append(
            FilingIngestResult(filing=filing, filing_created=created, item_codes=entry.items)
        )
    return results


@dataclass(frozen=True, slots=True)
class FilingTextResult:
    text: str
    raw_payload_id: UUID
    source_url: str
    retrieved_at: datetime


def fetch_filing_text(
    db: Session, http_client: ThrottledHttpClient, *, cik: int | str, filing: SecFiling
) -> FilingTextResult:
    """Fetch + store a filing's raw document, extract plain text for Layer 1
    rule matching (PLAN.md 24.4).

    Deliberately does **not** create a `provenance` row itself: a single
    filing can produce several distinct `research_evidence` rows (one per
    matched rule), and each derived fact needs its *own* provenance row
    (the same "one raw payload, many provenance rows" pattern Milestone 3
    established for financial facts) — reusing one provenance row across
    multiple evidence rows is a real bug this milestone hit live (a
    `calculation_input` composite-key collision once two evidence items from
    the same filing shared one provenance id in one alert's lineage). The
    caller creates one provenance per match via
    `normalize_filing_document_provenance`, all referencing this one
    `raw_payload_id`.
    """
    if filing.primary_document is None:
        raise ValueError(f"filing {filing.accession_no} has no primary_document to fetch")

    cik10 = format_cik10(cik)
    client = SecEdgarClient(http_client)
    document = client.fetch_filing_document(cik10, filing.accession_no, filing.primary_document)
    text = normalizer.extract_filing_text(document.raw_bytes.decode("utf-8", errors="replace"))
    payload = raw_payload_store.store_raw_payload(
        db,
        provider=ProviderName.SEC_EDGAR,
        source_record_id=filing.accession_no,
        url=document.url,
        raw_bytes=document.raw_bytes,
        # `raw_provider_payload.payload_json` requires *some* JSON-shaped
        # storage location (Supabase Storage isn't wired up yet — TD-006).
        # A filing document is HTML, not naturally JSON, so it's wrapped in
        # a small object rather than left as `None`, extending TD-006's
        # already-accepted "store inline for now" precedent to this new
        # payload type. `extracted_text` — not the raw HTML — is what's
        # stored, since the raw markup itself has no independent value here
        # (rule matching only ever needs the plain text, and the HTML is
        # already fully recoverable from `source_url` if ever needed).
        payload_json={"extracted_text": text},
        content_type=document.content_type,
        retrieved_at=document.retrieved_at,
    )
    return FilingTextResult(
        text=text,
        raw_payload_id=payload.id,
        source_url=document.url,
        retrieved_at=document.retrieved_at,
    )
