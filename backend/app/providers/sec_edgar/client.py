"""SEC EDGAR HTTP client: fetches and parses the two endpoints Milestone 3 needs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Generic, TypeVar

from app.providers.base.http_client import ThrottledHttpClient
from app.providers.sec_edgar.dto import SecCompanyFactsDTO, SecSubmissionsDTO

_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik10}.json"
_COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10}.json"

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
