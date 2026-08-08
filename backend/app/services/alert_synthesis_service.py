"""Provider-agnostic alert synthesis: Evidence -> Bundle -> Alert (PLAN.md 24.3, ADR-018).

Takes `ResearchEvidence` rows already persisted by whichever provider
produced them (SEC EDGAR today) and turns each *new* evidence bundle into
exactly one `alert_event`, via the AI evidence-review layer when available,
falling back to a deterministic templated alert otherwise. This module
contains zero SEC-specific field references — everything it reads off
`ResearchEvidence`/`EvidenceBundle` is already generic, and any SEC-specific
formatting (e.g. "8-K filed 2026-08-01, Accession ...") is supplied by the
caller via the injected `describe_source` callback, not hardcoded here. A
future CourtListener/FRED/ratings integration calls
`synthesize_alerts_from_evidence` with its own evidence and its own
`describe_source`, unchanged.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.ai.evidence_review import review_evidence_candidates
from app.ai.llm_gate import check_send_to_llm
from app.ai.providers.base import LLMProvider
from app.core.distress_rules import RuleMatch
from app.core.types import (
    AlertStatus,
    DataClassification,
    DetectionMethod,
    EvidenceType,
    ProviderName,
    TransformationType,
)
from app.domain.alert import AlertEvent, AlertEventCreate
from app.domain.evidence_bundle import EvidenceBundle, group_evidence_into_bundles
from app.domain.provenance import CalculationCreate, CalculationInputCreate, ProvenanceCreate
from app.domain.research_evidence import ResearchEvidence
from app.repositories import alert_repository, issuer_repository, provenance_repository

_TOPIC_PHRASES: dict[EvidenceType, str] = {
    EvidenceType.BANKRUPTCY_OR_RECEIVERSHIP: "bankruptcy or receivership filing",
    EvidenceType.CHAPTER_11: "Chapter 11 filing",
    EvidenceType.CHAPTER_7: "Chapter 7 filing",
    EvidenceType.DEFAULT_OR_MISSED_PAYMENT: "missed payment or default",
    EvidenceType.COVENANT_BREACH: "covenant breach or event of default",
    EvidenceType.DEBT_ACCELERATION: "debt acceleration",
    EvidenceType.GOING_CONCERN: "going-concern language",
    EvidenceType.SUBSTANTIAL_DOUBT: (
        "substantial doubt about ability to continue as a going concern"
    ),
    EvidenceType.LIQUIDITY_WARNING: "liquidity warning",
    EvidenceType.RESTRUCTURING_ADVISOR: "engagement of a restructuring advisor",
    EvidenceType.RESTRUCTURING_SUPPORT_AGREEMENT: "restructuring support agreement",
    EvidenceType.EXCHANGE_OFFER: "exchange offer",
    EvidenceType.LIABILITY_MANAGEMENT_TRANSACTION: "liability management transaction",
    EvidenceType.DEBT_AMENDMENT: "debt amendment",
    EvidenceType.MATURITY_EXTENSION: "maturity extension",
    EvidenceType.REFINANCING: "refinancing activity",
    EvidenceType.DIP_FINANCING: "debtor-in-possession financing",
    EvidenceType.EMERGENCY_FINANCING: "emergency financing",
    EvidenceType.MATERIAL_ASSET_SALE: "material asset sale",
    EvidenceType.DELISTING_NOTICE: "delisting notice",
    EvidenceType.WORKFORCE_REDUCTION: "workforce reduction",
    EvidenceType.FACILITY_CLOSURE: "facility closure",
    EvidenceType.MATERIAL_IMPAIRMENT: "material impairment",
    EvidenceType.AUDITOR_RESIGNATION: "auditor resignation",
    EvidenceType.ADVERSE_AUDIT_DEVELOPMENT: "adverse audit development",
    EvidenceType.STRATEGIC_ALTERNATIVES: "review of strategic alternatives",
    EvidenceType.PLAN_CONFIRMED: "confirmation of a plan of reorganization",
    EvidenceType.CASE_DISMISSED: "dismissal of a bankruptcy case",
    EvidenceType.CASE_CONVERTED: "conversion of a bankruptcy case to Chapter 7",
    EvidenceType.TRUSTEE_APPOINTED: "appointment of a bankruptcy trustee",
    EvidenceType.CLAIMS_BAR_DATE_SET: "a claims bar date being set",
    EvidenceType.RELIEF_FROM_STAY_MOTION: "a motion for relief from the automatic stay",
}


@dataclass(frozen=True, slots=True)
class SourceDescription:
    """What the caller knows about a bundle's primary evidence source that
    `alert_synthesis_service` itself must not know how to compute — e.g. SEC
    filing formatting. Injected via `describe_source`, never hardcoded here.
    """

    phrase: str  # e.g. "a new 10-Q" — inserted into the cautious headline template
    label: str  # e.g. "10-Q filed 2026-08-01, Accession 0001234-26-000123"
    url: str | None
    as_of_date: date


DescribeSourceFn = Callable[[ResearchEvidence], SourceDescription]


def evidence_to_candidate(evidence: ResearchEvidence) -> RuleMatch:
    """Adapt a persisted `ResearchEvidence` row back into the lightweight
    `RuleMatch` shape `app.ai.evidence_review` expects — keeps that module
    (and its already-tested/live-verified behavior) untouched."""
    return RuleMatch(
        rule_id=evidence.matched_rule,
        evidence_type=evidence.evidence_type,
        severity=evidence.severity,
        matched_text=evidence.matched_rule,
        excerpt=evidence.evidence_excerpt,
        start_offset=evidence.evidence_start_offset or 0,
        end_offset=evidence.evidence_end_offset or 0,
        source_item=evidence.source_item,
        confidence=evidence.confidence or 0.0,
    )


def _deterministic_summary(bundle: EvidenceBundle, *, source_phrase: str) -> tuple[str, str]:
    """Cautious, evidence-based wording — never asserts a conclusion beyond
    what was matched (CLAUDE.md / PLAN.md 24.4's explicit wording rule)."""
    dominant = bundle.primary_evidence
    topic = _TOPIC_PHRASES.get(
        dominant.evidence_type, dominant.evidence_type.value.replace("_", " ")
    )
    headline = f"Potential {topic} detected in {source_phrase}."
    signal_count = len(bundle.evidence)
    plural = "s" if signal_count != 1 else ""
    explanation = (
        f"Deterministic rule matching flagged {signal_count} signal{plural} in {source_phrase}, "
        f"including {topic}. Review the underlying filing excerpt for full context before "
        "drawing conclusions."
    )
    return headline, explanation


def _synthesis_provenance(
    db: Session,
    *,
    bundle: EvidenceBundle,
    ai_assisted: bool,
    source: SourceDescription,
) -> UUID:
    """Creates the `calculation` + `calculation_input` lineage and the
    `provenance` row for the alert, following exactly the pattern Milestone 6
    established for `illustrative_recovery` (PLAN.md section 6/24.3) — a
    derived fact never gets a bare provenance pointer with no traceable
    inputs. Returns the new provenance row's id.
    """
    method = "research_alert_synthesis_ai_assisted" if ai_assisted else "research_alert_synthesis"
    calculation = provenance_repository.create_calculation(
        db,
        CalculationCreate(
            method=method,
            formula_note=(
                f"Alert synthesized from evidence bundle '{bundle.bundle_key}' "
                f"({len(bundle.evidence)} contributing evidence record(s))."
            ),
        ),
        inputs=[
            CalculationInputCreate(provenance_id=e.provenance_id, sequence_number=i)
            for i, e in enumerate(bundle.evidence)
        ],
    )
    primary_provider = bundle.evidence[0].evidence_provider
    provider_enum = ProviderName.AI_GENERATED if ai_assisted else ProviderName(primary_provider)
    provenance = provenance_repository.create_provenance(
        db,
        ProvenanceCreate(
            provider=provider_enum,
            source_record_id=bundle.bundle_key,
            source_url=source.url,
            as_of_date=source.as_of_date,
            retrieved_at=datetime.now(UTC),
            transformation=TransformationType.CALCULATED,
            classification=(
                DataClassification.AI_EXTRACTED if ai_assisted else DataClassification.PUBLIC
            ),
            calculation_id=calculation.id,
        ),
    )
    return provenance.id


def _synthesize_one_alert(
    db: Session,
    *,
    bundle: EvidenceBundle,
    describe_source: DescribeSourceFn,
    llm: LLMProvider | None,
    environment: str,
    is_backfill: bool,
) -> AlertEvent:
    issuer = issuer_repository.get_issuer(db, bundle.issuer_id)
    if issuer is None:
        raise ValueError(
            f"issuer {bundle.issuer_id} not found for evidence bundle {bundle.bundle_key}"
        )

    source = describe_source(bundle.primary_evidence)

    review_result = None
    if llm is not None:
        gate_decision = check_send_to_llm(
            classification=DataClassification.PUBLIC, entitlement=None, environment=environment
        )
        if gate_decision.allowed:
            candidates = [evidence_to_candidate(e) for e in bundle.evidence]
            review_result = review_evidence_candidates(
                llm,
                issuer_name=issuer.legal_name,
                source_description=source.label,
                candidates=candidates,
            )

    ai_assisted = review_result is not None
    if review_result is not None:
        headline = review_result.headline
        explanation = review_result.explanation
        severity = review_result.severity
        confidence: float | None = review_result.confidence
        detection_method = DetectionMethod.AI_ASSISTED
        issuer_is_subject: bool | None = review_result.issuer_is_subject
    else:
        headline, explanation = _deterministic_summary(bundle, source_phrase=source.phrase)
        severity = bundle.primary_evidence.severity
        confidence = max(
            (e.confidence for e in bundle.evidence if e.confidence is not None), default=None
        )
        detection_method = DetectionMethod.DETERMINISTIC
        issuer_is_subject = None

    provenance_id = _synthesis_provenance(db, bundle=bundle, ai_assisted=ai_assisted, source=source)

    alert = alert_repository.create_alert(
        db,
        AlertEventCreate(
            issuer_id=bundle.issuer_id,
            category=bundle.primary_evidence.evidence_type.value,
            severity=severity,
            headline=headline,
            explanation=explanation,
            evidence_ids=[e.id for e in bundle.evidence],
            bundle_key=bundle.bundle_key,
            primary_evidence_provider=bundle.primary_evidence.evidence_provider,
            primary_source_label=source.label,
            primary_source_url=source.url,
            detection_method=detection_method,
            ai_assisted=ai_assisted,
            confidence=confidence,
            as_of_date=source.as_of_date,
            provenance_id=provenance_id,
            status=AlertStatus.NEW,
            is_backfill=is_backfill,
            issuer_is_subject=issuer_is_subject,
        ),
    )
    return alert


def synthesize_alerts_from_evidence(
    db: Session,
    *,
    evidence: list[ResearchEvidence],
    describe_source: DescribeSourceFn,
    llm: LLMProvider | None,
    environment: str,
    is_backfill: bool,
) -> list[AlertEvent]:
    """Group `evidence` into bundles and create one alert per genuinely new
    bundle. Idempotent: a bundle that already produced an alert (looked up by
    `bundle_key`) is skipped, never duplicated — safe to call repeatedly
    across retried runs (PLAN.md 24.5's retry-safety requirement).
    """
    created: list[AlertEvent] = []
    for bundle in group_evidence_into_bundles(evidence):
        if not bundle.evidence:
            continue
        existing = alert_repository.get_alert_by_bundle_key(db, bundle.bundle_key)
        if existing is not None:
            continue
        alert = _synthesize_one_alert(
            db,
            bundle=bundle,
            describe_source=describe_source,
            llm=llm,
            environment=environment,
            is_backfill=is_backfill,
        )
        created.append(alert)
    return created
