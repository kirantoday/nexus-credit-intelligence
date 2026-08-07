"""The CourtListener-specific orchestrator (PLAN.md sections 4.5, 15, ADR-018's
documented Milestone 7 forward path).

Docket discovery/linking is a separate, curated step
(`app.providers.courtlistener.provider`'s module docstring explains why —
no reliable automatic "list new PACER cases for issuer X" feed exists). This
service's job starts once a docket is already linked to a real `issuer_id`:
sync its entries, run Layer 1 distress rules against each new entry, and
hand resulting evidence to the provider-agnostic `alert_synthesis_service` —
exactly `filing_monitor_service`'s per-issuer error-isolation and
provenance-per-match pattern, applied to dockets instead of filings.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from app.ai.providers.base import LLMProvider
from app.core.court_docket_matcher import select_best_match
from app.core.distress_rules import DOCKET_EXCLUDED_RULE_IDS, match_rules
from app.core.types import CourtDocketLinkMatchOutcome, DetectionMethod, EvidenceType, ProviderName
from app.domain.alert import AlertEvent
from app.domain.court_docket import CourtDocket
from app.domain.court_docket_link_attempt import CourtDocketLinkAttemptCreate
from app.domain.research_evidence import ResearchEvidence, ResearchEvidenceCreate
from app.providers.base.http_client import ThrottledHttpClient
from app.providers.courtlistener import normalizer as cl_normalizer
from app.providers.courtlistener.provider import DocketEntryIngestResult, DocketSearchCandidate
from app.providers.courtlistener.provider import link_docket as cl_link_docket
from app.providers.courtlistener.provider import search_dockets as cl_search_dockets
from app.providers.courtlistener.provider import sync_docket_entries as cl_sync_docket_entries
from app.repositories import (
    court_docket_entry_repository,
    court_docket_link_attempt_repository,
    court_docket_repository,
    provenance_repository,
    research_evidence_repository,
)
from app.services import alert_synthesis_service
from app.services.alert_synthesis_service import SourceDescription

# Evidence categories that plausibly correspond to a real court docket —
# `attempt_auto_link` is only invoked when an issuer has at least one of
# these; a distress signal with no bankruptcy/restructuring shape has
# nothing for a docket search to plausibly confirm (PLAN.md Milestone 7.5
# section 10: "eligible for CourtListener enrichment" is scoped to
# distressed/restructuring-relevant issuers, not every issuer uniformly).
DOCKET_RELEVANT_EVIDENCE_TYPES: frozenset[EvidenceType] = frozenset(
    {
        EvidenceType.BANKRUPTCY_OR_RECEIVERSHIP,
        EvidenceType.CHAPTER_11,
        EvidenceType.CHAPTER_7,
        EvidenceType.RESTRUCTURING_SUPPORT_AGREEMENT,
        EvidenceType.DIP_FINANCING,
        EvidenceType.PLAN_CONFIRMED,
        EvidenceType.CASE_DISMISSED,
        EvidenceType.CASE_CONVERTED,
        EvidenceType.TRUSTEE_APPOINTED,
    }
)


class SyncDocketEntriesFn(Protocol):
    def __call__(
        self, db: Session, http_client: ThrottledHttpClient, *, docket: CourtDocket
    ) -> list[DocketEntryIngestResult]: ...


def _describe_courtlistener_source(db: Session, evidence: ResearchEvidence) -> SourceDescription:
    """The one place CourtListener-specific source formatting happens —
    injected into the provider-agnostic `alert_synthesis_service`, never
    hardcoded there (ADR-018's documented Milestone 7 forward path)."""
    entry = (
        court_docket_entry_repository.get_entry(db, evidence.docket_entry_id)
        if evidence.docket_entry_id is not None
        else None
    )
    if entry is None:
        return SourceDescription(
            phrase="a recent court docket entry",
            label="CourtListener (source entry unavailable)",
            url=None,
            as_of_date=date.today(),
        )
    docket = court_docket_repository.get_docket(db, entry.docket_id)
    if docket is None:
        return SourceDescription(
            phrase="a new court docket entry",
            label=f"Docket entry filed {entry.entry_date}",
            url=None,
            as_of_date=entry.entry_date or date.today(),
        )
    docket_label = f"{docket.case_name} ({docket.docket_number}, {docket.court})"
    entry_label = (
        f"Docket entry #{entry.entry_number}"
        if entry.entry_number is not None
        else "A docket entry"
    )
    return SourceDescription(
        phrase=f"a new docket entry in {docket_label}",
        label=f"{entry_label} filed {entry.entry_date}, {docket_label}",
        url=f"https://www.courtlistener.com/docket/{docket.courtlistener_docket_id}/",
        as_of_date=entry.entry_date or date.today(),
    )


def _process_one_entry(
    db: Session, *, issuer_id: UUID, ingest_result: DocketEntryIngestResult
) -> list[ResearchEvidence]:
    """Idempotent per entry: reuse existing evidence rather than re-matching
    (mirrors `filing_monitor_service._process_one_filing`'s real
    duplicate-evidence guard, deliberately keyed off existing evidence, not
    `entry_created` — a retry that failed after ingest but before evidence
    creation must still be picked up)."""
    existing_evidence = research_evidence_repository.list_evidence_by_docket_entry(
        db, ingest_result.entry.id
    )
    if existing_evidence:
        return existing_evidence

    matches = match_rules(
        form_type="Docket Entry",
        item_codes=None,
        text=ingest_result.match_text,
        exclude_rule_ids=DOCKET_EXCLUDED_RULE_IDS,
    )

    created: list[ResearchEvidence] = []
    for match in matches:
        evidence_provenance = provenance_repository.create_provenance(
            db,
            cl_normalizer.normalize_docket_evidence_provenance(
                courtlistener_entry_id=ingest_result.entry.courtlistener_entry_id,
                entry_date=ingest_result.entry.entry_date,
                source_url=ingest_result.source_url,
                retrieved_at=ingest_result.retrieved_at,
                raw_payload_id=ingest_result.raw_payload_id,
            ),
        )
        evidence = research_evidence_repository.create_evidence(
            db,
            ResearchEvidenceCreate(
                issuer_id=issuer_id,
                evidence_provider=ProviderName.COURTLISTENER.value,
                source_type="docket_entry",
                docket_entry_id=ingest_result.entry.id,
                evidence_type=match.evidence_type,
                severity=match.severity,
                source_section=None,
                source_item=match.source_item,
                matched_rule=match.rule_id,
                evidence_excerpt=match.excerpt,
                evidence_start_offset=match.start_offset or None,
                evidence_end_offset=match.end_offset or None,
                confidence=match.confidence,
                detection_method=DetectionMethod.DETERMINISTIC,
                provenance_id=evidence_provenance.id,
            ),
        )
        created.append(evidence)
    return created


@dataclass(frozen=True, slots=True)
class DocketSyncResult:
    docket: CourtDocket
    entries_discovered: int
    entries_processed: int
    alerts_created: int


def sync_one_docket(
    db: Session,
    http_client: ThrottledHttpClient,
    llm: LLMProvider | None,
    *,
    docket: CourtDocket,
    environment: str,
    is_backfill: bool = False,
    sync_docket_entries_fn: SyncDocketEntriesFn = cl_sync_docket_entries,
) -> DocketSyncResult:
    """Sync one already-linked docket's entries and synthesize alerts from
    any resulting evidence. The caller (`app.scripts.sync_court_dockets`)
    commits per docket and isolates errors the same way
    `filing_monitor_service.run_monitor` does per issuer, so one docket's
    failure never loses another's already-committed work in the same run.

    `sync_docket_entries_fn` is injectable so evidence/alert-synthesis logic
    is unit-testable without hitting live CourtListener on every test run —
    the same reason `filing_monitor_service.run_monitor` takes
    `fetch_filings_fn`/`fetch_filing_text_fn`; the real wiring (this
    module's own default) passes the actual provider function.
    """
    if docket.issuer_id is None:
        raise ValueError(f"docket {docket.id} has no linked issuer_id — link it first")

    ingest_results = sync_docket_entries_fn(db, http_client, docket=docket)

    all_evidence: list[ResearchEvidence] = []
    for ingest_result in ingest_results:
        all_evidence.extend(
            _process_one_entry(db, issuer_id=docket.issuer_id, ingest_result=ingest_result)
        )

    alerts: list[AlertEvent] = []
    if all_evidence:
        alerts = alert_synthesis_service.synthesize_alerts_from_evidence(
            db,
            evidence=all_evidence,
            describe_source=lambda e: _describe_courtlistener_source(db, e),
            llm=llm,
            environment=environment,
            is_backfill=is_backfill,
        )

    return DocketSyncResult(
        docket=docket,
        entries_discovered=len(ingest_results),
        entries_processed=len(ingest_results),
        alerts_created=len(alerts),
    )


class SearchDocketsFn(Protocol):
    def __call__(
        self, db: Session, http_client: ThrottledHttpClient, *, query: str, court: str | None
    ) -> list[DocketSearchCandidate]: ...


@dataclass(frozen=True, slots=True)
class AutoLinkResult:
    outcome: CourtDocketLinkMatchOutcome
    attempt_id: UUID
    sync_result: DocketSyncResult | None


def attempt_auto_link(
    db: Session,
    http_client: ThrottledHttpClient,
    llm: LLMProvider | None,
    *,
    issuer_id: UUID,
    issuer_legal_name: str,
    environment: str,
    search_dockets_fn: SearchDocketsFn = cl_search_dockets,
    sync_docket_entries_fn: SyncDocketEntriesFn = cl_sync_docket_entries,
) -> AutoLinkResult:
    """Automatic CourtListener docket linking on a hierarchy of identity
    evidence (ADR-020, superseding ADR-019's blanket prohibition). Only
    called for issuers with at least one `DOCKET_RELEVANT_EVIDENCE_TYPES`
    research-evidence row on file — the triggering evidence's excerpt/
    provenance date is what the signal matcher (`app.core.court_docket_matcher`)
    checks candidates against. Every attempt, regardless of outcome, is
    recorded in `court_docket_link_attempt` with its full evaluated signal
    set — never a black box. Only `verified_docket_match` proceeds to
    `link_docket` + a real `sync_one_docket` call; `ambiguous_manual_review`
    and `checked_no_relevant_docket` link nothing, matching the existing
    curated `app.scripts.link_court_dockets` discipline for anything short
    of a unique, uncontradicted strong-signal match.
    """
    relevant_evidence = [
        e
        for e in research_evidence_repository.list_evidence(db, issuer_id=issuer_id, page_size=50)
        if e.evidence_type in DOCKET_RELEVANT_EVIDENCE_TYPES
    ]
    if not relevant_evidence:
        raise ValueError(
            f"issuer {issuer_id} has no docket-relevant evidence on file — "
            "attempt_auto_link should not have been called"
        )

    # Most recent bankruptcy-relevant evidence is the strongest, freshest
    # signal source — older evidence for the same issuer could describe an
    # already-resolved prior case.
    primary_evidence = max(relevant_evidence, key=lambda e: e.created_at)
    evidence_provenance = provenance_repository.get_provenance(db, primary_evidence.provenance_id)
    evidence_as_of_date = evidence_provenance.as_of_date if evidence_provenance else None

    candidates = search_dockets_fn(db, http_client, query=issuer_legal_name, court=None)
    outcome, best, evaluated = select_best_match(
        [c.dto for c in candidates],
        issuer_legal_name=issuer_legal_name,
        evidence_text=primary_evidence.evidence_excerpt,
        evidence_as_of_date=evidence_as_of_date,
    )

    match_signals = {
        "primary_evidence_type": primary_evidence.evidence_type.value,
        "candidates_evaluated": [
            {
                "docket_number": e.candidate.docketNumber,
                "case_name": e.candidate.caseName,
                **e.signals.as_dict(),
            }
            for e in evaluated
        ],
    }

    linked_docket_id: UUID | None = None
    sync_result: DocketSyncResult | None = None
    candidate_docket_id = best.candidate.docket_id if best is not None else None

    if outcome is CourtDocketLinkMatchOutcome.VERIFIED_DOCKET_MATCH:
        assert best is not None
        matching_search_candidate = next(
            c for c in candidates if c.dto.docket_id == best.candidate.docket_id
        )
        docket, _created = cl_link_docket(
            db, issuer_id=issuer_id, candidate=matching_search_candidate
        )
        linked_docket_id = docket.id
        db.commit()
        sync_result = sync_one_docket(
            db,
            http_client,
            llm,
            docket=docket,
            environment=environment,
            sync_docket_entries_fn=sync_docket_entries_fn,
        )
        db.commit()

    attempt = court_docket_link_attempt_repository.create_attempt(
        db,
        CourtDocketLinkAttemptCreate(
            issuer_id=issuer_id,
            query_used=issuer_legal_name,
            candidate_courtlistener_docket_id=candidate_docket_id,
            match_outcome=outcome,
            match_signals=match_signals,
            linked_docket_id=linked_docket_id,
        ),
    )
    db.commit()

    return AutoLinkResult(outcome=outcome, attempt_id=attempt.id, sync_result=sync_result)
