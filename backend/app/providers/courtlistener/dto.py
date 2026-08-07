"""Provider DTOs for CourtListener's REST API v4 — mirror the real JSON
response shapes closely enough to parse them, not exhaustively (unused
fields ignored via `extra="ignore"`, not modeled). Verified against live
requests during Milestone 7 development (Diebold Holding Company, Inc. /
Diebold Nixdorf Holding Company, Inc., docket 23-90602, S.D. Tex. Bankr.):
the Search API (`/api/rest/v4/search/?type=r`) works anonymously; the
Docket-Entries API (`/api/rest/v4/docket-entries/`) requires a real
`Authorization: Token ...` header (401 otherwise) — see `client.py`.

DTOs are allowed to be provider-specific, unlike canonical domain objects
(`app/domain/**`) — these field names match CourtListener's API verbatim
(including its camelCase Search fields); the normalizer (`normalizer.py`)
is the only place that translation happens.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CourtListenerSearchResultDTO(BaseModel):
    """One RECAP docket result from `/api/rest/v4/search/?type=r&q=...` —
    real, live-verified field names (camelCase, as CourtListener's Search API
    actually returns them, distinct from the snake_case PACER-data endpoints
    below).
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    docket_id: int
    caseName: str
    docketNumber: str
    court: str | None = None
    court_id: str | None = None
    dateFiled: str | None = None
    chapter: str | None = None
    suitNature: str | None = None
    pacer_case_id: str | None = None
    docket_absolute_url: str | None = None


class CourtListenerSearchResponseDTO(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    count: int | None = None
    next: str | None = None
    results: list[CourtListenerSearchResultDTO] = Field(default_factory=list)


class RecapDocumentDTO(BaseModel):
    """One document attached to a docket entry — never fetched/displayed
    when `is_sealed` (PLAN.md section 22)."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    id: int
    document_number: str | None = None
    attachment_number: int | None = None
    description: str | None = None
    page_count: int | None = None
    is_available: bool = False
    # Real, live-confirmed: CourtListener sometimes returns `null` here, not
    # always a bool. `None` is treated as sealed (see `is_sealed_or_unknown`
    # below) — PLAN.md section 22's "never fetch sealed material" means
    # unknown status must fail safe toward "sealed," never toward "open."
    is_sealed: bool | None = None
    absolute_url: str | None = None
    # Already-OCR'd/extracted text, included inline on the docket-entries
    # response itself (confirmed live) — no separate per-document fetch is
    # needed for Layer 1 rule matching, unlike SEC's filing text.
    plain_text: str | None = None

    @property
    def is_sealed_or_unknown(self) -> bool:
        """Never `False` when the API's own `is_sealed` is `null` — treat
        unknown seal status as sealed, the safe default (PLAN.md section 22).
        This is the only property every other module in this package must
        use instead of the raw `is_sealed` field."""
        return self.is_sealed is not False


class DocketEntryDTO(BaseModel):
    """One entry from `/api/rest/v4/docket-entries/?docket={id}` —
    real, live-verified field names."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    id: int
    entry_number: int | None = None
    date_filed: str | None = None
    description: str | None = None
    recap_documents: list[RecapDocumentDTO] = Field(default_factory=list)


class DocketEntriesPageDTO(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    count: int | None = None
    next: str | None = None
    previous: str | None = None
    results: list[DocketEntryDTO] = Field(default_factory=list)
