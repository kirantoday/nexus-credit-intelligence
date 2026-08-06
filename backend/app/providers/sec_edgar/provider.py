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

from sqlalchemy.orm import Session

from app.core.types import ProviderName
from app.domain.financial_fact import FinancialFact
from app.domain.issuer import Issuer
from app.providers.base import raw_payload_store
from app.providers.base.http_client import ThrottledHttpClient
from app.providers.sec_edgar import normalizer
from app.providers.sec_edgar.client import SecEdgarClient, format_cik10
from app.providers.sec_edgar.dto import SecXbrlUnitDatapoint
from app.repositories import (
    financial_fact_repository,
    issuer_repository,
    provenance_repository,
    raw_provider_payload_repository,
)


@dataclass(frozen=True, slots=True)
class IngestResult:
    issuer: Issuer
    financial_fact: FinancialFact
    issuer_created: bool
    financial_fact_created: bool


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

    submissions = client.fetch_submissions(cik10)
    submissions_payload = raw_payload_store.store_raw_payload(
        db,
        provider=ProviderName.SEC_EDGAR,
        source_record_id=cik10,
        url=submissions.url,
        raw_bytes=submissions.raw_bytes,
        payload_json=json.loads(submissions.raw_bytes),
        content_type=submissions.content_type,
        retrieved_at=submissions.retrieved_at,
    )
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

    company_facts = client.fetch_company_facts(cik10)
    company_facts_payload = raw_payload_store.store_raw_payload(
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

    concept_data = company_facts.dto.facts.us_gaap.get(concept)
    if concept_data is None:
        raise ValueError(f"concept {concept!r} not found in company facts for CIK {cik10}")
    datapoints = concept_data.units.get(unit)
    if not datapoints:
        raise ValueError(f"unit {unit!r} not found for concept {concept!r} (CIK {cik10})")
    datapoint = _select_most_recent_datapoint(datapoints)
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
