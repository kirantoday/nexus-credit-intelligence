"""SEC EDGAR HTTP client: fetches and parses the two endpoints Milestone 3 needs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Generic, TypeVar
from urllib.parse import urlencode

from app.providers.base.http_client import ThrottledHttpClient
from app.providers.sec_edgar.dto import (
    SecCompanyFactsDTO,
    SecFullTextSearchResponseDTO,
    SecSubmissionsDTO,
)

_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik10}.json"
_COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10}.json"
# Archives (filing document) URLs use the *unpadded* numeric CIK, unlike
# data.sec.gov's zero-padded CIK10 — a real, easy-to-miss inconsistency
# between SEC's two URL families.
_ARCHIVES_DOCUMENT_URL = (
    "https://www.sec.gov/Archives/edgar/data/{cik}/{accession_nodash}/{primary_document}"
)
# efts.sec.gov is a distinct SEC-owned host from data.sec.gov/www.sec.gov —
# same fair-access User-Agent policy applies (enforced by whatever
# `ThrottledHttpClient` the caller constructs, not by this URL itself).
# `size` is capped at 100 by SEC's own API (verified live before this was
# implemented, not assumed from documentation alone).
_FULL_TEXT_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"
FULL_TEXT_SEARCH_MAX_PAGE_SIZE = 100

_DtoT = TypeVar("_DtoT")


def format_cik10(cik: int | str) -> str:
    """SEC's canonical zero-padded 10-digit CIK, used in every EDGAR URL and as `issuer.cik`."""
    return str(int(cik)).zfill(10)


@dataclass(frozen=True, slots=True)
class FetchResult(Generic[_DtoT]):
    dto: _DtoT
    raw_bytes: bytes
    content_type: str
    url: str
    retrieved_at: datetime


@dataclass(frozen=True, slots=True)
class FilingDocumentFetchResult:
    """A fetched filing document's raw bytes — no DTO, since this is an HTML/
    text document, not a JSON API response `FetchResult[_DtoT]` is shaped for.
    """

    raw_bytes: bytes
    content_type: str
    url: str
    retrieved_at: datetime


class SecEdgarClient:
    def __init__(self, http_client: ThrottledHttpClient) -> None:
        self._http = http_client

    def fetch_submissions(self, cik10: str) -> FetchResult[SecSubmissionsDTO]:
        url = _SUBMISSIONS_URL.format(cik10=cik10)
        response = self._http.get(url)
        retrieved_at = datetime.now(UTC)
        dto = SecSubmissionsDTO.model_validate(json.loads(response.raw_bytes))
        return FetchResult(
            dto=dto,
            raw_bytes=response.raw_bytes,
            content_type=response.content_type,
            url=url,
            retrieved_at=retrieved_at,
        )

    def fetch_company_facts(self, cik10: str) -> FetchResult[SecCompanyFactsDTO]:
        url = _COMPANY_FACTS_URL.format(cik10=cik10)
        response = self._http.get(url)
        retrieved_at = datetime.now(UTC)
        # parse_float=Decimal avoids binary-float precision loss on financial
        # values (e.g. EPS) before pydantic ever sees them — plain
        # json.loads()/float would round-trip some values inexactly.
        dto = SecCompanyFactsDTO.model_validate(json.loads(response.raw_bytes, parse_float=Decimal))
        return FetchResult(
            dto=dto,
            raw_bytes=response.raw_bytes,
            content_type=response.content_type,
            url=url,
            retrieved_at=retrieved_at,
        )

    def search_full_text(
        self,
        query: str,
        *,
        forms: tuple[str, ...],
        start_date: date,
        end_date: date,
        from_offset: int = 0,
        size: int = FULL_TEXT_SEARCH_MAX_PAGE_SIZE,
    ) -> FetchResult[SecFullTextSearchResponseDTO]:
        """`GET https://efts.sec.gov/LATEST/search-index` — Layer 0 of the
        market discovery pipeline (PLAN.md Milestone 7.5): SEC's own
        server-side full-text index, queried with a curated distress-phrase
        query and a form-type/date-range filter, market-wide — not a scan
        of every filing. `size` is clamped to SEC's own real max (100,
        live-verified); pagination uses `from_offset` exactly like the
        `from`/`size` params SEC's own API documents.
        """
        params = {
            "q": query,
            "forms": ",".join(forms),
            "dateRange": "custom",
            "startdt": start_date.isoformat(),
            "enddt": end_date.isoformat(),
            "from": from_offset,
            "size": min(size, FULL_TEXT_SEARCH_MAX_PAGE_SIZE),
        }
        url = f"{_FULL_TEXT_SEARCH_URL}?{urlencode(params)}"
        response = self._http.get(url)
        retrieved_at = datetime.now(UTC)
        dto = SecFullTextSearchResponseDTO.model_validate(json.loads(response.raw_bytes))
        return FetchResult(
            dto=dto,
            raw_bytes=response.raw_bytes,
            content_type=response.content_type,
            url=url,
            retrieved_at=retrieved_at,
        )

    def fetch_filing_document(
        self, cik10: str, accession_no: str, primary_document: str
    ) -> FilingDocumentFetchResult:
        """Fetch a filing's primary document (the actual 8-K/10-Q/etc. body)
        for text extraction (PLAN.md 24.4's deterministic rule matching).
        """
        cik_unpadded = str(int(cik10))
        accession_nodash = accession_no.replace("-", "")
        url = _ARCHIVES_DOCUMENT_URL.format(
            cik=cik_unpadded, accession_nodash=accession_nodash, primary_document=primary_document
        )
        response = self._http.get(url)
        retrieved_at = datetime.now(UTC)
        return FilingDocumentFetchResult(
            raw_bytes=response.raw_bytes,
            content_type=response.content_type,
            url=url,
            retrieved_at=retrieved_at,
        )
