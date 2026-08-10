"""Integration tests for `app/ai/model_router.py` (PLAN.md Milestone 7.5.3's
AI cost-control correction) against the live shared `nexus` schema —
`ai_call_log` rows are real writes (rolled back per-test by the shared
`db_session` fixture), so these prove the routing/budget/observability
behavior end to end, not just in isolation from persistence.
"""

from __future__ import annotations

import json
from datetime import date
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session

from app.ai.model_router import AiCallBudget, ModelRouter, RoutingConfig
from app.ai.providers.base import CompletionRequest, CompletionResponse
from app.core.distress_rules import RuleMatch
from app.core.types import (
    AiOperation,
    DetectionMethod,
    EvidenceSeverity,
    EvidenceType,
    FilingMonitorRunMode,
    ProviderName,
)
from app.domain.issuer import Issuer, IssuerCreate
from app.domain.market_discovery import MarketDiscoveryRunCreate
from app.domain.research_evidence import ResearchEvidence, ResearchEvidenceCreate
from app.repositories import (
    ai_call_log_repository,
    issuer_repository,
    market_discovery_repository,
    provenance_repository,
    research_evidence_repository,
)
from app.services import alert_synthesis_service
from app.services.alert_synthesis_service import SourceDescription
from tests.integration.conftest import reported_public_provenance


def _seed_discovery_run(db: Session):
    return market_discovery_repository.create_run(
        db,
        MarketDiscoveryRunCreate(
            mode=FilingMonitorRunMode.BACKFILL,
            window_start_date=date(2026, 1, 1),
            window_end_date=date(2026, 8, 6),
        ),
    )


class _FakeProvider:
    """A controllable `LLMProvider` double: returns a fixed structured
    response (or raises, or returns unparseable text) — never touches the
    network. Tracks call count for assertions."""

    def __init__(
        self,
        *,
        confidence: float = 0.9,
        model: str = "fake-model",
        raises: Exception | None = None,
        malformed: bool = False,
        issuer_is_subject: bool = True,
    ) -> None:
        self.confidence = confidence
        self.model = model
        self.raises = raises
        self.malformed = malformed
        self.issuer_is_subject = issuer_is_subject
        self.call_count = 0

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        self.call_count += 1
        if self.raises is not None:
            raise self.raises
        if self.malformed:
            return CompletionResponse(
                text="not valid json", model=self.model, input_tokens=10, output_tokens=5
            )
        payload = {
            "headline": "Potential distress signal detected in a new filing",
            "explanation": "Evidence-based explanation of the flagged excerpt.",
            "severity": "high",
            "confidence": self.confidence,
            "issuer_is_subject": self.issuer_is_subject,
        }
        return CompletionResponse(
            text=json.dumps(payload), model=self.model, input_tokens=120, output_tokens=60
        )

    def call_tools(self, request: object) -> object:
        raise NotImplementedError

    def create_embeddings(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError


def _config(**overrides: object) -> RoutingConfig:
    defaults: dict[str, object] = dict(
        haiku_confidence_threshold=0.75,
        deterministic_confidence_floor=0.5,
        high_impact_evidence_types=frozenset(
            {EvidenceType.CHAPTER_11, EvidenceType.BANKRUPTCY_OR_RECEIVERSHIP}
        ),
        max_attempts=2,
        retry_delay_seconds=0.01,
    )
    defaults.update(overrides)
    return RoutingConfig(**defaults)  # type: ignore[arg-type]


def _candidate(
    *, confidence: float = 0.9, evidence_type: EvidenceType = EvidenceType.GOING_CONCERN
) -> RuleMatch:
    return RuleMatch(
        rule_id="test_rule",
        evidence_type=evidence_type,
        severity=EvidenceSeverity.HIGH,
        matched_text="going concern",
        excerpt="The Company has substantial doubt about its ability to continue.",
        start_offset=0,
        end_offset=10,
        source_item=None,
        confidence=confidence,
    )


@pytest.fixture
def issuer(db_session: Session) -> Issuer:
    provenance = provenance_repository.create_provenance(db_session, reported_public_provenance())
    return issuer_repository.create_issuer(
        db_session,
        IssuerCreate(legal_name=f"Test Router Issuer {uuid4()}", provenance_id=provenance.id),
    )


def test_below_deterministic_floor_makes_zero_calls(db_session: Session, issuer: Issuer) -> None:
    haiku = _FakeProvider(confidence=0.9)
    sonnet = _FakeProvider(confidence=0.9)
    router = ModelRouter(haiku=haiku, sonnet=sonnet, config=_config(), budget=AiCallBudget())

    routed = router.review_evidence(
        db_session,
        issuer_id=issuer.id,
        issuer_name=issuer.legal_name,
        source_description="10-Q filed 2026-08-01",
        candidates=[_candidate(confidence=0.3)],
        bundle_key=f"test:below-floor:{uuid4()}",
    )

    assert routed.result is None
    assert routed.deferred is False
    assert haiku.call_count == 0
    assert sonnet.call_count == 0


def test_simple_case_routes_to_haiku_only(db_session: Session, issuer: Issuer) -> None:
    haiku = _FakeProvider(confidence=0.95)
    sonnet = _FakeProvider(confidence=0.95)
    router = ModelRouter(haiku=haiku, sonnet=sonnet, config=_config(), budget=AiCallBudget())

    routed = router.review_evidence(
        db_session,
        issuer_id=issuer.id,
        issuer_name=issuer.legal_name,
        source_description="10-Q filed 2026-08-01",
        candidates=[_candidate(confidence=0.9)],
        bundle_key=f"test:simple:{uuid4()}",
    )

    assert routed.result is not None
    assert haiku.call_count == 1
    assert sonnet.call_count == 0


def test_confident_haiku_result_skips_sonnet(db_session: Session, issuer: Issuer) -> None:
    haiku = _FakeProvider(confidence=0.85)
    sonnet = _FakeProvider(confidence=0.85)
    router = ModelRouter(haiku=haiku, sonnet=sonnet, config=_config(), budget=AiCallBudget())

    routed = router.review_evidence(
        db_session,
        issuer_id=issuer.id,
        issuer_name=issuer.legal_name,
        source_description="10-Q filed 2026-08-01",
        candidates=[_candidate(confidence=0.9)],
        bundle_key=f"test:confident:{uuid4()}",
    )

    assert routed.result is not None
    assert routed.result.confidence == 0.85
    assert sonnet.call_count == 0


def test_ambiguous_haiku_result_escalates_to_sonnet(db_session: Session, issuer: Issuer) -> None:
    haiku = _FakeProvider(confidence=0.5)  # below 0.75 threshold
    sonnet = _FakeProvider(confidence=0.95)
    router = ModelRouter(haiku=haiku, sonnet=sonnet, config=_config(), budget=AiCallBudget())

    routed = router.review_evidence(
        db_session,
        issuer_id=issuer.id,
        issuer_name=issuer.legal_name,
        source_description="10-Q filed 2026-08-01",
        candidates=[_candidate(confidence=0.9)],
        bundle_key=f"test:ambiguous:{uuid4()}",
    )

    assert haiku.call_count == 1
    assert sonnet.call_count == 1
    assert routed.result is not None
    assert routed.result.confidence == 0.95  # sonnet's result wins


def test_high_impact_category_goes_straight_to_sonnet_never_haiku(
    db_session: Session, issuer: Issuer
) -> None:
    """Even a very high Haiku confidence (0.99) must not matter — a
    Chapter 11 bundle never goes through Haiku at all (PLAN.md Milestone
    7.5.3's live quality-validation finding: Haiku's self-reported
    confidence was not a reliable enough signal for this category on a
    real production third-party-attribution case)."""
    haiku = _FakeProvider(confidence=0.99)
    sonnet = _FakeProvider(confidence=0.97)
    router = ModelRouter(haiku=haiku, sonnet=sonnet, config=_config(), budget=AiCallBudget())

    routed = router.review_evidence(
        db_session,
        issuer_id=issuer.id,
        issuer_name=issuer.legal_name,
        source_description="8-K filed 2026-08-01",
        candidates=[_candidate(confidence=0.95, evidence_type=EvidenceType.CHAPTER_11)],
        bundle_key=f"test:high-impact:{uuid4()}",
    )

    assert haiku.call_count == 0
    assert sonnet.call_count == 1
    assert routed.result is not None
    assert routed.result.confidence == 0.97


def test_failed_haiku_result_escalates_to_sonnet(db_session: Session, issuer: Issuer) -> None:
    haiku = _FakeProvider(malformed=True)
    sonnet = _FakeProvider(confidence=0.9)
    router = ModelRouter(haiku=haiku, sonnet=sonnet, config=_config(), budget=AiCallBudget())

    routed = router.review_evidence(
        db_session,
        issuer_id=issuer.id,
        issuer_name=issuer.legal_name,
        source_description="10-Q filed 2026-08-01",
        candidates=[_candidate(confidence=0.9)],
        bundle_key=f"test:haiku-failed:{uuid4()}",
    )

    assert sonnet.call_count == 1
    assert routed.result is not None


def test_ai_call_budget_reached_stops_further_calls(db_session: Session, issuer: Issuer) -> None:
    haiku = _FakeProvider(confidence=0.95)
    sonnet = _FakeProvider(confidence=0.95)
    budget = AiCallBudget(max_calls=1)
    router = ModelRouter(haiku=haiku, sonnet=sonnet, config=_config(), budget=budget)

    # First bundle consumes the one allowed call.
    router.review_evidence(
        db_session,
        issuer_id=issuer.id,
        issuer_name=issuer.legal_name,
        source_description="10-Q filed 2026-08-01",
        candidates=[_candidate(confidence=0.9)],
        bundle_key=f"test:budget-first:{uuid4()}",
    )
    assert haiku.call_count == 1

    # Second bundle must make zero further calls — deferred instead.
    routed = router.review_evidence(
        db_session,
        issuer_id=issuer.id,
        issuer_name=issuer.legal_name,
        source_description="10-Q filed 2026-08-02",
        candidates=[_candidate(confidence=0.9)],
        bundle_key=f"test:budget-second:{uuid4()}",
    )
    assert haiku.call_count == 1  # unchanged
    assert sonnet.call_count == 0
    assert routed.result is None
    assert routed.deferred is True


def test_dollar_budget_reached_stops_further_calls(db_session: Session, issuer: Issuer) -> None:
    sonnet = _FakeProvider(confidence=0.95)
    # Any real call costs > $0 for claude-haiku-4-5-20251001's real pricing
    # entry — set the cap at a value the very first call will exceed.
    budget = AiCallBudget(max_cost_usd=0.0000001)
    router = ModelRouter(
        haiku=_FakeProvider(confidence=0.95, model="claude-haiku-4-5-20251001"),
        sonnet=sonnet,
        config=_config(),
        budget=budget,
    )

    routed = router.review_evidence(
        db_session,
        issuer_id=issuer.id,
        issuer_name=issuer.legal_name,
        source_description="10-Q filed 2026-08-01",
        candidates=[_candidate(confidence=0.9)],
        bundle_key=f"test:dollar-budget-1:{uuid4()}",
    )
    assert routed.result is not None  # first call still allowed (budget checked before, not after)

    routed_second = router.review_evidence(
        db_session,
        issuer_id=issuer.id,
        issuer_name=issuer.legal_name,
        source_description="10-Q filed 2026-08-02",
        candidates=[_candidate(confidence=0.9)],
        bundle_key=f"test:dollar-budget-2:{uuid4()}",
    )
    assert routed_second.result is None
    assert routed_second.deferred is True


def test_sonnet_budget_reached_stops_further_sonnet_calls(
    db_session: Session, issuer: Issuer
) -> None:
    haiku = _FakeProvider(confidence=0.5)  # always escalates
    sonnet = _FakeProvider(confidence=0.95)
    budget = AiCallBudget(max_sonnet_calls=0)
    router = ModelRouter(haiku=haiku, sonnet=sonnet, config=_config(), budget=budget)

    routed = router.review_evidence(
        db_session,
        issuer_id=issuer.id,
        issuer_name=issuer.legal_name,
        source_description="10-Q filed 2026-08-01",
        candidates=[_candidate(confidence=0.9)],
        bundle_key=f"test:sonnet-budget:{uuid4()}",
    )

    assert haiku.call_count == 1
    assert sonnet.call_count == 0
    # Haiku was attempted and returned a (low-confidence) result, so this
    # is NOT deferred — Haiku's weaker result is used rather than nothing.
    assert routed.deferred is False
    assert routed.result is not None
    assert routed.result.confidence == 0.5


def test_zero_ai_mode_makes_zero_anthropic_calls(db_session: Session, issuer: Issuer) -> None:
    router = ModelRouter(haiku=None, sonnet=None, config=_config(), budget=AiCallBudget())

    routed = router.review_evidence(
        db_session,
        issuer_id=issuer.id,
        issuer_name=issuer.legal_name,
        source_description="10-Q filed 2026-08-01",
        candidates=[_candidate(confidence=0.9)],
        bundle_key=f"test:zero-ai:{uuid4()}",
    )

    assert routed.result is None
    assert routed.deferred is True
    calls = ai_call_log_repository.aggregate_for_discovery_run(db_session, uuid4())
    assert calls.total_calls == 0


def test_ai_call_log_records_model_route_and_tokens(db_session: Session, issuer: Issuer) -> None:
    haiku = _FakeProvider(confidence=0.95, model="claude-haiku-4-5-20251001")
    router = ModelRouter(haiku=haiku, sonnet=None, config=_config(), budget=AiCallBudget())
    discovery_run_id = _seed_discovery_run(db_session).id

    router.review_evidence(
        db_session,
        issuer_id=issuer.id,
        issuer_name=issuer.legal_name,
        source_description="10-Q filed 2026-08-01",
        candidates=[_candidate(confidence=0.9)],
        bundle_key=f"test:log-fields:{uuid4()}",
        discovery_run_id=discovery_run_id,
    )

    usage = ai_call_log_repository.aggregate_for_discovery_run(db_session, discovery_run_id)
    assert usage.total_calls == 1
    assert usage.haiku_calls == 1
    assert usage.sonnet_calls == 0
    assert usage.total_input_tokens == 120
    assert usage.total_output_tokens == 60
    assert usage.total_estimated_cost_usd > 0
    assert "claude-haiku-4-5-20251001" in usage.cost_by_model
    assert usage.calls_by_operation[AiOperation.EVIDENCE_REVIEW.value] == 1


def test_reclassify_operation_is_recorded_distinctly(db_session: Session, issuer: Issuer) -> None:
    haiku = _FakeProvider(confidence=0.95)
    router = ModelRouter(haiku=haiku, sonnet=None, config=_config(), budget=AiCallBudget())
    discovery_run_id = _seed_discovery_run(db_session).id

    router.review_evidence(
        db_session,
        issuer_id=issuer.id,
        issuer_name=issuer.legal_name,
        source_description="alert source label",
        candidates=[_candidate(confidence=0.9)],
        bundle_key=f"test:reclassify:{uuid4()}",
        discovery_run_id=discovery_run_id,
        operation=AiOperation.RECLASSIFY_ISSUER_IS_SUBJECT,
    )

    usage = ai_call_log_repository.aggregate_for_discovery_run(db_session, discovery_run_id)
    assert usage.calls_by_operation[AiOperation.RECLASSIFY_ISSUER_IS_SUBJECT.value] == 1


def _seed_evidence(db: Session, *, issuer_id: UUID) -> ResearchEvidence:
    provenance = provenance_repository.create_provenance(db, reported_public_provenance())
    return research_evidence_repository.create_evidence(
        db,
        ResearchEvidenceCreate(
            issuer_id=issuer_id,
            evidence_provider=ProviderName.SEC_EDGAR.value,
            source_type="sec_filing",
            evidence_type=EvidenceType.GOING_CONCERN,
            severity=EvidenceSeverity.HIGH,
            matched_rule="phrase_substantial_doubt_going_concern",
            evidence_excerpt="Substantial doubt about ability to continue as a going concern.",
            confidence=0.9,
            detection_method=DetectionMethod.DETERMINISTIC,
            provenance_id=provenance.id,
        ),
    )


def _describe_source(_evidence: ResearchEvidence) -> SourceDescription:
    return SourceDescription(
        phrase="a new 10-Q", label="10-Q filed 2026-08-01", url=None, as_of_date=date(2026, 8, 1)
    )


def test_already_reviewed_bundle_makes_zero_further_ai_calls(
    db_session: Session, issuer: Issuer
) -> None:
    """Proves `synthesize_alerts_from_evidence`'s pre-existing bundle_key
    check still prevents any router call (not just a duplicate alert) once
    a bundle already has one — the real cost-saving guarantee behind
    PLAN.md Milestone 7.5.3's "re-running a historical window must not
    generate duplicate AI spend" requirement."""
    haiku = _FakeProvider(confidence=0.95)
    router = ModelRouter(haiku=haiku, sonnet=None, config=_config(), budget=AiCallBudget())
    evidence = _seed_evidence(db_session, issuer_id=issuer.id)

    first_alerts = alert_synthesis_service.synthesize_alerts_from_evidence(
        db_session,
        evidence=[evidence],
        describe_source=_describe_source,
        router=router,
        environment="test",
        is_backfill=True,
    )
    assert len(first_alerts) == 1
    assert haiku.call_count == 1

    # Re-run over the *same* evidence (simulating a repeated/idempotent
    # historical backfill pass) — zero new alerts, zero new AI calls.
    second_alerts = alert_synthesis_service.synthesize_alerts_from_evidence(
        db_session,
        evidence=[evidence],
        describe_source=_describe_source,
        router=router,
        environment="test",
        is_backfill=True,
    )
    assert len(second_alerts) == 0
    assert haiku.call_count == 1  # unchanged — no additional spend
