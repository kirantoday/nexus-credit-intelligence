"""Repository for Universal Search (PLAN.md 4.13, 8; Milestone 12A).

Function-style, matching this project's repository conventions — but
unlike every other repository, this one returns a lightweight internal
`SearchHit` per row, not a domain object: search results are an assembled,
cross-table read-model with no persisted canonical shape of their own
(the same reason `WatchlistIssuerRow` lives directly in `schemas/
watchlist.py` with no domain-object counterpart — see `watchlist_service`).
`search_service` assembles `SearchHit`s from here into the API's
`SearchResultItem` schema.

**Included entity types** (PLAN.md 4.13's search-target list, scoped to
what this milestone's architecture review found to be real, analyst-
meaningful, already-existing free text): `issuer`, `security`,
`alert_event`, `court_docket`, `court_docket_entry`, `collection`
(Research Universes/Watchlists/Benchmarks alike), `research_note`
(current content only), and a deliberately **thin** `sec_filing` metadata
search (accession number, form type — no filing content is stored
anywhere in this schema, so "search SEC filings" cannot honestly mean more
than that).

**Deliberately excluded**:
- `research_evidence` — `alert_event` is the canonical, human-facing
  "distress development" unit (`issuer_timeline_service.get_issuer_timeline`
  reads exclusively from `alert_event`, never `research_evidence`, directly
  confirming this); indexing the raw evidence underneath it as well would
  just duplicate the same signal at a noisier grain.
- `research_note_version` — only the live `research_note` row is indexed.
  A note edited five times would otherwise produce five near-identical
  search hits differing only in old wording. Version history stays
  reachable exactly where Milestone 10A already built it: the note's own
  Version History UI. Enforced at the schema level too — no
  `search_vector` column exists on `research_note_version` at all.
- `audit_event` — an operational log, not research content.
- `docket_document` — no real extracted text exists anywhere in this
  schema yet (10B/document extraction is out of scope); its only text
  field is a short administrative label, not analyst-searchable content.
- All of 10B (`research_document` doesn't exist).

**Ranking tiers** (PLAN.md 4.13/8's fixed contract — exact identifier
matches always outrank fuzzy matches, never blended into one score):
Tier 0 exact identifier match (CIK/ticker/LEI/CUSIP/ISIN/FIGI/docket
number/accession number, via `search_exact_matches`) is queried entirely
separately from the per-entity-type Tier 1-3 functions below, which
combine, in order: an exact/prefix name/description match, PostgreSQL
full-text search (`websearch_to_tsquery` + `ts_rank_cd` against each
table's generated `search_vector` column), and — for `issuer`/`security`
only — a `pg_trgm` similarity fallback, used only when the first two tiers
don't fill the requested limit (typo tolerance, never the primary
ranking signal).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.types import SearchEntityType
from app.models.alert import AlertEvent as AlertEventModel
from app.models.collection import Collection as CollectionModel
from app.models.court_docket import CourtDocket as CourtDocketModel
from app.models.court_docket_entry import CourtDocketEntry as CourtDocketEntryModel
from app.models.issuer import Issuer as IssuerModel
from app.models.research import ResearchNote as ResearchNoteModel
from app.models.sec_filing import SecFiling as SecFilingModel
from app.models.security import Security as SecurityModel

_TRIGRAM_SIMILARITY_THRESHOLD = 0.3


@dataclass(frozen=True, slots=True)
class SearchHit:
    """One row of a search result, before the service layer turns it into
    the API's `SearchResultItem`."""

    entity_type: SearchEntityType
    entity_id: UUID
    title: str
    snippet: str | None
    issuer_id: UUID | None
    collection_type: str | None
    context_date: date | None
    rank: float
    matched_field: str | None = None


def _truncate(value: str | None, *, length: int = 180) -> str | None:
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    if len(value) <= length:
        return value
    return value[: length - 1].rstrip() + "…"


def _first_non_empty(*values: str | None) -> str | None:
    for value in values:
        if value:
            return value
    return None


# --- Tier 0: exact identifier match ---


def search_exact_matches(db: Session, query: str, *, limit: int) -> list[SearchHit]:
    q = query.strip()
    if not q:
        return []
    hits: list[SearchHit] = []

    issuer_stmt = select(
        IssuerModel.id, IssuerModel.legal_name, IssuerModel.cik, IssuerModel.ticker, IssuerModel.lei
    ).where(
        (func.lower(IssuerModel.cik) == q.lower())
        | (func.lower(IssuerModel.ticker) == q.lower())
        | (func.lower(IssuerModel.lei) == q.lower())
    )
    for issuer_row in db.execute(issuer_stmt).all():
        matched_field, matched_value = (
            ("CIK", issuer_row.cik)
            if issuer_row.cik and issuer_row.cik.lower() == q.lower()
            else (
                ("Ticker", issuer_row.ticker)
                if issuer_row.ticker and issuer_row.ticker.lower() == q.lower()
                else ("LEI", issuer_row.lei)
            )
        )
        hits.append(
            SearchHit(
                entity_type=SearchEntityType.ISSUER,
                entity_id=issuer_row.id,
                title=issuer_row.legal_name,
                snippet=f"{matched_field}: {matched_value}",
                issuer_id=issuer_row.id,
                collection_type=None,
                context_date=None,
                rank=1.0,
                matched_field=matched_field,
            )
        )

    security_stmt = select(
        SecurityModel.id,
        SecurityModel.description,
        SecurityModel.issuer_id,
        SecurityModel.cusip,
        SecurityModel.isin,
        SecurityModel.figi,
    ).where(
        (func.lower(SecurityModel.cusip) == q.lower())
        | (func.lower(SecurityModel.isin) == q.lower())
        | (func.lower(SecurityModel.figi) == q.lower())
    )
    for security_row in db.execute(security_stmt).all():
        matched_field, matched_value = (
            ("CUSIP", security_row.cusip)
            if security_row.cusip and security_row.cusip.lower() == q.lower()
            else (
                ("ISIN", security_row.isin)
                if security_row.isin and security_row.isin.lower() == q.lower()
                else ("FIGI", security_row.figi)
            )
        )
        hits.append(
            SearchHit(
                entity_type=SearchEntityType.SECURITY,
                entity_id=security_row.id,
                title=security_row.description,
                snippet=f"{matched_field}: {matched_value}",
                issuer_id=security_row.issuer_id,
                collection_type=None,
                context_date=None,
                rank=1.0,
                matched_field=matched_field,
            )
        )

    docket_stmt = select(
        CourtDocketModel.id,
        CourtDocketModel.case_name,
        CourtDocketModel.docket_number,
        CourtDocketModel.issuer_id,
    ).where(func.lower(CourtDocketModel.docket_number) == q.lower())
    for docket_row in db.execute(docket_stmt).all():
        hits.append(
            SearchHit(
                entity_type=SearchEntityType.COURT_DOCKET,
                entity_id=docket_row.id,
                title=docket_row.case_name,
                snippet=f"Docket Number: {docket_row.docket_number}",
                issuer_id=docket_row.issuer_id,
                collection_type=None,
                context_date=None,
                rank=1.0,
                matched_field="Docket Number",
            )
        )

    filing_stmt = select(
        SecFilingModel.id,
        SecFilingModel.accession_no,
        SecFilingModel.form_type,
        SecFilingModel.filing_date,
        SecFilingModel.issuer_id,
    ).where(func.lower(SecFilingModel.accession_no) == q.lower())
    for filing_row in db.execute(filing_stmt).all():
        hits.append(
            SearchHit(
                entity_type=SearchEntityType.SEC_FILING,
                entity_id=filing_row.id,
                title=f"{filing_row.form_type} — {filing_row.accession_no}",
                snippet=f"Accession Number: {filing_row.accession_no}",
                issuer_id=filing_row.issuer_id,
                collection_type=None,
                context_date=filing_row.filing_date,
                rank=1.0,
                matched_field="Accession Number",
            )
        )

    return hits[:limit]


# --- Tier 1-3: issuer / security (prefix -> FTS -> trigram fallback) ---


def search_issuers(db: Session, query: str, *, limit: int) -> list[SearchHit]:
    q = query.strip()
    if not q or limit <= 0:
        return []

    def _hit(row: object, *, rank: float) -> SearchHit:
        return SearchHit(
            entity_type=SearchEntityType.ISSUER,
            entity_id=row.id,  # type: ignore[attr-defined]
            title=row.legal_name,  # type: ignore[attr-defined]
            snippet=_first_non_empty(
                f"Ticker: {row.ticker}" if row.ticker else None,  # type: ignore[attr-defined]
                row.sector,  # type: ignore[attr-defined]
            ),
            issuer_id=row.id,  # type: ignore[attr-defined]
            collection_type=None,
            context_date=None,
            rank=rank,
        )

    cols = (IssuerModel.id, IssuerModel.legal_name, IssuerModel.ticker, IssuerModel.sector)
    hits: list[SearchHit] = []
    seen: set[UUID] = set()

    prefix_stmt = (
        select(*cols)
        .where(IssuerModel.legal_name.ilike(f"{q}%"))
        .order_by(IssuerModel.legal_name.asc())
        .limit(limit)
    )
    for row in db.execute(prefix_stmt).all():
        hits.append(_hit(row, rank=2.0))
        seen.add(row.id)

    if len(hits) < limit:
        tsquery = func.websearch_to_tsquery("english", q)
        fts_stmt = select(
            *cols, func.ts_rank_cd(IssuerModel.search_vector, tsquery).label("r")
        ).where(IssuerModel.search_vector.op("@@")(tsquery))
        if seen:
            fts_stmt = fts_stmt.where(IssuerModel.id.notin_(seen))
        fts_stmt = fts_stmt.order_by(
            func.ts_rank_cd(IssuerModel.search_vector, tsquery).desc()
        ).limit(limit - len(hits))
        for row in db.execute(fts_stmt).all():
            hits.append(_hit(row, rank=float(row.r)))
            seen.add(row.id)

    if len(hits) < limit:
        sim = func.similarity(IssuerModel.legal_name, q)
        trgm_stmt = select(*cols, sim.label("s")).where(sim > _TRIGRAM_SIMILARITY_THRESHOLD)
        if seen:
            trgm_stmt = trgm_stmt.where(IssuerModel.id.notin_(seen))
        trgm_stmt = trgm_stmt.order_by(sim.desc()).limit(limit - len(hits))
        for row in db.execute(trgm_stmt).all():
            hits.append(_hit(row, rank=float(row.s)))
            seen.add(row.id)

    return hits


def search_securities(db: Session, query: str, *, limit: int) -> list[SearchHit]:
    q = query.strip()
    if not q or limit <= 0:
        return []

    def _hit(row: object, *, rank: float) -> SearchHit:
        return SearchHit(
            entity_type=SearchEntityType.SECURITY,
            entity_id=row.id,  # type: ignore[attr-defined]
            title=row.description,  # type: ignore[attr-defined]
            snippet=row.legal_name,  # type: ignore[attr-defined]
            issuer_id=row.issuer_id,  # type: ignore[attr-defined]
            collection_type=None,
            context_date=None,
            rank=rank,
        )

    cols = (
        SecurityModel.id,
        SecurityModel.description,
        SecurityModel.issuer_id,
        IssuerModel.legal_name,
    )
    base = select(*cols).join(IssuerModel, SecurityModel.issuer_id == IssuerModel.id)
    hits: list[SearchHit] = []
    seen: set[UUID] = set()

    prefix_stmt = (
        base.where(SecurityModel.description.ilike(f"{q}%"))
        .order_by(SecurityModel.description.asc())
        .limit(limit)
    )
    for row in db.execute(prefix_stmt).all():
        hits.append(_hit(row, rank=2.0))
        seen.add(row.id)

    if len(hits) < limit:
        tsquery = func.websearch_to_tsquery("english", q)
        rank_expr = func.ts_rank_cd(SecurityModel.search_vector, tsquery)
        fts_stmt = base.add_columns(rank_expr.label("r")).where(
            SecurityModel.search_vector.op("@@")(tsquery)
        )
        if seen:
            fts_stmt = fts_stmt.where(SecurityModel.id.notin_(seen))
        fts_stmt = fts_stmt.order_by(rank_expr.desc()).limit(limit - len(hits))
        for row in db.execute(fts_stmt).all():
            hits.append(_hit(row, rank=float(row.r)))
            seen.add(row.id)

    if len(hits) < limit:
        sim = func.similarity(SecurityModel.description, q)
        trgm_stmt = base.add_columns(sim.label("s")).where(sim > _TRIGRAM_SIMILARITY_THRESHOLD)
        if seen:
            trgm_stmt = trgm_stmt.where(SecurityModel.id.notin_(seen))
        trgm_stmt = trgm_stmt.order_by(sim.desc()).limit(limit - len(hits))
        for row in db.execute(trgm_stmt).all():
            hits.append(_hit(row, rank=float(row.s)))
            seen.add(row.id)

    return hits


# --- Tier 2: PostgreSQL full-text search only (no prefix/trigram tier —
# these aren't proper-noun lookups the way issuer/security names are) ---


def search_alerts(db: Session, query: str, *, limit: int) -> list[SearchHit]:
    q = query.strip()
    if not q or limit <= 0:
        return []
    tsquery = func.websearch_to_tsquery("english", q)
    rank = func.ts_rank_cd(AlertEventModel.search_vector, tsquery)
    stmt = (
        select(
            AlertEventModel.id,
            AlertEventModel.headline,
            AlertEventModel.explanation,
            AlertEventModel.issuer_id,
            AlertEventModel.as_of_date,
            AlertEventModel.severity,
            IssuerModel.legal_name,
            rank.label("r"),
        )
        .join(IssuerModel, AlertEventModel.issuer_id == IssuerModel.id)
        .where(AlertEventModel.search_vector.op("@@")(tsquery))
        .order_by(rank.desc(), AlertEventModel.as_of_date.desc())
        .limit(limit)
    )
    return [
        SearchHit(
            entity_type=SearchEntityType.ALERT_EVENT,
            entity_id=row.id,
            title=row.headline,
            snippet=f"{row.legal_name}: {_truncate(row.explanation)}",
            issuer_id=row.issuer_id,
            collection_type=None,
            context_date=row.as_of_date,
            rank=float(row.r),
        )
        for row in db.execute(stmt).all()
    ]


def search_court_dockets(db: Session, query: str, *, limit: int) -> list[SearchHit]:
    q = query.strip()
    if not q or limit <= 0:
        return []
    tsquery = func.websearch_to_tsquery("english", q)
    rank = func.ts_rank_cd(CourtDocketModel.search_vector, tsquery)
    stmt = (
        select(
            CourtDocketModel.id,
            CourtDocketModel.case_name,
            CourtDocketModel.court,
            CourtDocketModel.docket_number,
            CourtDocketModel.issuer_id,
            CourtDocketModel.date_filed,
            rank.label("r"),
        )
        .where(CourtDocketModel.search_vector.op("@@")(tsquery))
        .order_by(rank.desc())
        .limit(limit)
    )
    return [
        SearchHit(
            entity_type=SearchEntityType.COURT_DOCKET,
            entity_id=row.id,
            title=row.case_name,
            snippet=f"{row.court} · {row.docket_number}",
            issuer_id=row.issuer_id,
            collection_type=None,
            context_date=row.date_filed,
            rank=float(row.r),
        )
        for row in db.execute(stmt).all()
    ]


def search_court_docket_entries(db: Session, query: str, *, limit: int) -> list[SearchHit]:
    """Matches on `description` — the only real free text a docket entry
    has. Always joins back to `court_docket` so the result carries the
    parent case's `issuer_id`/case name/docket number for navigation
    context, per the explicit instruction that docket-entry results must
    not be a disconnected search experience."""
    q = query.strip()
    if not q or limit <= 0:
        return []
    tsquery = func.websearch_to_tsquery("english", q)
    rank = func.ts_rank_cd(CourtDocketEntryModel.search_vector, tsquery)
    stmt = (
        select(
            CourtDocketEntryModel.id,
            CourtDocketEntryModel.description,
            CourtDocketEntryModel.entry_number,
            CourtDocketEntryModel.entry_date,
            CourtDocketModel.case_name,
            CourtDocketModel.docket_number,
            CourtDocketModel.issuer_id,
            rank.label("r"),
        )
        .join(CourtDocketModel, CourtDocketEntryModel.docket_id == CourtDocketModel.id)
        .where(CourtDocketEntryModel.search_vector.op("@@")(tsquery))
        .order_by(rank.desc())
        .limit(limit)
    )
    return [
        SearchHit(
            entity_type=SearchEntityType.COURT_DOCKET_ENTRY,
            entity_id=row.id,
            title=_truncate(row.description, length=120) or "(no description on file)",
            snippet=f"{row.case_name} ({row.docket_number})"
            + (f" · Entry #{row.entry_number}" if row.entry_number else ""),
            issuer_id=row.issuer_id,
            collection_type=None,
            context_date=row.entry_date,
            rank=float(row.r),
        )
        for row in db.execute(stmt).all()
    ]


def search_collections(db: Session, query: str, *, limit: int) -> list[SearchHit]:
    q = query.strip()
    if not q or limit <= 0:
        return []
    tsquery = func.websearch_to_tsquery("english", q)
    rank = func.ts_rank_cd(CollectionModel.search_vector, tsquery)
    stmt = (
        select(
            CollectionModel.id,
            CollectionModel.name,
            CollectionModel.description,
            CollectionModel.collection_type,
            rank.label("r"),
        )
        .where(CollectionModel.search_vector.op("@@")(tsquery))
        .order_by(rank.desc())
        .limit(limit)
    )
    return [
        SearchHit(
            entity_type=SearchEntityType.COLLECTION,
            entity_id=row.id,
            title=row.name,
            snippet=_truncate(row.description),
            issuer_id=None,
            collection_type=row.collection_type,
            context_date=None,
            rank=float(row.r),
        )
        for row in db.execute(stmt).all()
    ]


def search_research_notes(db: Session, query: str, *, limit: int) -> list[SearchHit]:
    """Live `research_note` rows only — `research_note_version` has no
    `search_vector` column at all (enforced at the schema level, not just
    by this query)."""
    q = query.strip()
    if not q or limit <= 0:
        return []
    tsquery = func.websearch_to_tsquery("english", q)
    rank = func.ts_rank_cd(ResearchNoteModel.search_vector, tsquery)
    stmt = (
        select(
            ResearchNoteModel.id,
            ResearchNoteModel.title,
            ResearchNoteModel.base_case,
            ResearchNoteModel.bull_case,
            ResearchNoteModel.bear_case,
            ResearchNoteModel.issuer_id,
            ResearchNoteModel.updated_at,
            rank.label("r"),
        )
        .where(ResearchNoteModel.search_vector.op("@@")(tsquery))
        .where(ResearchNoteModel.is_archived.is_(False))
        .order_by(rank.desc(), ResearchNoteModel.updated_at.desc())
        .limit(limit)
    )
    return [
        SearchHit(
            entity_type=SearchEntityType.RESEARCH_NOTE,
            entity_id=row.id,
            title=row.title,
            snippet=_truncate(_first_non_empty(row.base_case, row.bull_case, row.bear_case)),
            issuer_id=row.issuer_id,
            collection_type=None,
            context_date=row.updated_at.date(),
            rank=float(row.r),
        )
        for row in db.execute(stmt).all()
    ]


# --- Thin SEC filing metadata search (no filing content is stored) ---


def search_sec_filings(db: Session, query: str, *, limit: int) -> list[SearchHit]:
    """Deliberately thin: matches only `form_type` (e.g. "10-K", "8-K"),
    the one real metadata field worth free-text matching on this table.
    Never implies full-text search over filing content, because none
    exists. Exact `accession_no` matching is handled entirely by Tier 0
    (`search_exact_matches`) — this group intentionally does *not* also
    substring-match `accession_no`: it's a long digit string, and a
    substring match against it produces coincidental noise for any
    numeric-looking query (e.g. a 4-digit year query incidentally matching
    inside an unrelated 20-digit accession number) rather than a
    meaningful result."""
    q = query.strip()
    if not q or limit <= 0:
        return []
    pattern = f"%{q}%"
    stmt = (
        select(
            SecFilingModel.id,
            SecFilingModel.accession_no,
            SecFilingModel.form_type,
            SecFilingModel.filing_date,
            SecFilingModel.issuer_id,
        )
        .where(SecFilingModel.form_type.ilike(pattern))
        .order_by(SecFilingModel.filing_date.desc())
        .limit(limit)
    )
    return [
        SearchHit(
            entity_type=SearchEntityType.SEC_FILING,
            entity_id=row.id,
            title=f"{row.form_type} — {row.accession_no}",
            snippet=f"Filed {row.filing_date.isoformat()}",
            issuer_id=row.issuer_id,
            collection_type=None,
            context_date=row.filing_date,
            rank=0.0,
        )
        for row in db.execute(stmt).all()
    ]
