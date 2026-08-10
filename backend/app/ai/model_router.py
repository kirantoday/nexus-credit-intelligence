"""Centralized deterministic -> Haiku -> Sonnet routing policy and per-run
AI budget enforcement (PLAN.md Milestone 7.5.3's AI cost-control
correction).

Before this module, every evidence-review call went straight to
`review_evidence_candidates` with a single, always-Sonnet `LLMProvider` —
no routing, no budget, no observability. `ModelRouter.review_evidence` is
now the *only* sanctioned way to reach `review_evidence_candidates`
outside a bare single-model test double: it decides whether a call is
needed at all, which model handles it, whether a second (Sonnet) opinion
is warranted, enforces the run's hard budget immediately before every
provider call (so no caller can bypass it), and writes exactly one
`ai_call_log` row per real API request.

Routing policy, in order:
1. Deterministic floor: if every candidate's own Layer-1 confidence is
   below `deterministic_confidence_floor`, no model is called at all —
   the bundle is too weak a signal to spend anything reviewing.
2. High-impact categories (`universe_classification_service
   .definitive_evidence_types()` — Chapter 11, bankruptcy/receivership,
   plan-confirmed) go **straight to Sonnet, never through Haiku at all**.
   This was empirically corrected during this milestone's own quality
   validation: a real production Chapter 11 third-party-attribution case
   — exactly the class of error Milestone 7.5.1 fixed — was confidently
   (0.98) misclassified by Haiku, above even a strict confidence
   threshold. A confidence-based escalation bar is not a reliable enough
   safeguard for this category, so there is no bar to clear here — "be
   especially conservative for definitive/high-impact classifications"
   means Sonnet unconditionally, not Sonnet-if-Haiku-seems-unsure.
3. Everything else: Haiku first, escalating to Sonnet (bounded to exactly
   one attempt) only when Haiku's own call fails/returns an unparseable
   result, or its reported `confidence` is below `haiku_confidence_threshold`.
   Sonnet is never asked to re-review a Haiku result that already cleared
   its bar — that would defeat the entire cost-saving purpose.

Budget: `AiCallBudget` is a single mutable tracker shared across every
`review_evidence` call within one run (one instance per CLI invocation).
`can_call` is checked immediately before every provider call, never
delegated to a caller — once a limit is hit, the *next* call this router
would have made is skipped and `deferred=True` is returned instead of a
result, so `alert_synthesis_service` can leave that bundle's alert
uncreated (not a low-confidence/deterministic alert masquerading as
reviewed) for a future run with fresh budget to pick up via the same
`bundle_key` idempotency check.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy.orm import Session

from app.ai.evidence_review import EvidenceReviewResult, review_evidence_candidates
from app.ai.pricing import estimate_cost_usd
from app.ai.providers.base import CompletionRequest, CompletionResponse, LLMProvider
from app.core.distress_rules import RuleMatch
from app.core.types import AiOperation, AiRoute, EvidenceType
from app.domain.ai_call_log import AiCallLogCreate
from app.repositories import ai_call_log_repository


@dataclass(frozen=True, slots=True)
class RoutingConfig:
    haiku_confidence_threshold: float
    deterministic_confidence_floor: float
    high_impact_evidence_types: frozenset[EvidenceType]
    max_attempts: int = 2
    retry_delay_seconds: float = 2.0


@dataclass(slots=True)
class AiCallBudget:
    """One instance per run. `None` for any limit means that limit is
    unenforced — a caller that wants a hard ceiling must pass one
    explicitly (PLAN.md: batch/backfill callers always do)."""

    max_calls: int | None = None
    max_cost_usd: float | None = None
    max_sonnet_calls: int | None = None

    calls_made: int = field(default=0, init=False)
    sonnet_calls_made: int = field(default=0, init=False)
    cost_so_far_usd: float = field(default=0.0, init=False)
    calls_blocked: int = field(default=0, init=False)
    # Bundles that cleared the deterministic floor but got neither a Haiku
    # nor a Sonnet attempt at all (no provider configured — e.g. zero-AI
    # mode — or budget exhausted before the first attempt). Distinct from
    # `calls_blocked`, which only counts an attempt the budget itself
    # stopped mid-escalation.
    deferred_count: int = field(default=0, init=False)
    deterministic_skips: int = field(default=0, init=False)

    def can_call(self, *, is_sonnet: bool) -> bool:
        if self.max_calls is not None and self.calls_made >= self.max_calls:
            return False
        if self.max_cost_usd is not None and self.cost_so_far_usd >= self.max_cost_usd:
            return False
        if is_sonnet and self.max_sonnet_calls is not None:
            if self.sonnet_calls_made >= self.max_sonnet_calls:
                return False
        return True

    def record(self, *, cost_usd: float | None, is_sonnet: bool) -> None:
        self.calls_made += 1
        if is_sonnet:
            self.sonnet_calls_made += 1
        if cost_usd is not None:
            self.cost_so_far_usd += cost_usd

    def record_blocked(self) -> None:
        self.calls_blocked += 1

    def record_deferred(self) -> None:
        self.deferred_count += 1

    def record_deterministic_skip(self) -> None:
        self.deterministic_skips += 1


@dataclass(frozen=True, slots=True)
class RoutedReview:
    result: EvidenceReviewResult | None
    # True only when the budget prevented *any* attempt at all — the
    # caller must not create a deterministic-fallback alert in this case,
    # since that would permanently foreclose a real AI review later via
    # the bundle_key idempotency check. False (including when `result` is
    # None because Haiku/Sonnet genuinely failed or the deterministic
    # floor applied) means the deterministic fallback path is correct.
    deferred: bool


def default_routing_config(settings: object) -> RoutingConfig:
    from app.services.universe_classification_service import definitive_evidence_types

    return RoutingConfig(
        haiku_confidence_threshold=settings.ai_haiku_confidence_threshold,  # type: ignore[attr-defined]
        deterministic_confidence_floor=settings.ai_deterministic_confidence_floor,  # type: ignore[attr-defined]
        high_impact_evidence_types=frozenset(definitive_evidence_types()),
        max_attempts=settings.ai_call_max_attempts,  # type: ignore[attr-defined]
        retry_delay_seconds=settings.ai_call_retry_delay_seconds,  # type: ignore[attr-defined]
    )


class ModelRouter:
    def __init__(
        self,
        *,
        haiku: LLMProvider | None,
        sonnet: LLMProvider | None,
        config: RoutingConfig,
        budget: AiCallBudget,
    ) -> None:
        self._haiku = haiku
        self._sonnet = sonnet
        self._config = config
        self.budget = budget

    def review_evidence(
        self,
        db: Session,
        *,
        issuer_id: UUID,
        issuer_name: str,
        source_description: str,
        candidates: list[RuleMatch],
        bundle_key: str,
        discovery_run_id: UUID | None = None,
        filing_monitor_run_id: UUID | None = None,
        operation: AiOperation = AiOperation.EVIDENCE_REVIEW,
    ) -> RoutedReview:
        if not candidates:
            return RoutedReview(result=None, deferred=False)

        max_layer1_confidence = max(c.confidence for c in candidates)
        if max_layer1_confidence < self._config.deterministic_confidence_floor:
            self.budget.record_deterministic_skip()
            return RoutedReview(result=None, deferred=False)

        is_high_impact = any(
            c.evidence_type in self._config.high_impact_evidence_types for c in candidates
        )

        if is_high_impact:
            # Empirically corrected during this milestone's own quality
            # validation (PLAN.md Milestone 7.5.3): a real production
            # Chapter 11 third-party-attribution case — exactly the class
            # of error Milestone 7.5.1 fixed — was confidently (0.98)
            # misclassified by Haiku, above even the strict high-impact
            # confidence threshold. Haiku's self-reported confidence is
            # not a reliable enough signal for this category, so
            # definitive/high-impact bundles go straight to Sonnet and
            # never through Haiku at all — "cheapest model capable of the
            # required reliability" here means Sonnet, unconditionally.
            if self._sonnet is None or not self.budget.can_call(is_sonnet=True):
                if self._sonnet is not None:
                    self.budget.record_blocked()
                self.budget.record_deferred()
                return RoutedReview(result=None, deferred=True)
            sonnet_result = self._attempt(
                db,
                provider=self._sonnet,
                route=AiRoute.SONNET,
                routing_reason="high_impact_category_direct_to_sonnet",
                issuer_name=issuer_name,
                source_description=source_description,
                candidates=candidates,
                discovery_run_id=discovery_run_id,
                filing_monitor_run_id=filing_monitor_run_id,
                issuer_id=issuer_id,
                bundle_key=bundle_key,
                operation=operation,
            )
            return RoutedReview(result=sonnet_result, deferred=False)

        threshold = self._config.haiku_confidence_threshold

        haiku_result: EvidenceReviewResult | None = None
        haiku_attempted = False
        if self._haiku is not None:
            if not self.budget.can_call(is_sonnet=False):
                self.budget.record_blocked()
            else:
                haiku_attempted = True
                haiku_result = self._attempt(
                    db,
                    provider=self._haiku,
                    route=AiRoute.HAIKU,
                    routing_reason="haiku_default",
                    issuer_name=issuer_name,
                    source_description=source_description,
                    candidates=candidates,
                    discovery_run_id=discovery_run_id,
                    filing_monitor_run_id=filing_monitor_run_id,
                    issuer_id=issuer_id,
                    bundle_key=bundle_key,
                    operation=operation,
                )

        escalate_reason: str | None = None
        if haiku_result is None:
            escalate_reason = (
                "haiku_call_unavailable_or_budget_blocked"
                if not haiku_attempted
                else "haiku_result_unparseable_or_failed"
            )
        elif haiku_result.confidence < threshold:
            escalate_reason = (
                f"haiku_confidence_{haiku_result.confidence:.2f}_below_threshold_{threshold:.2f}"
            )

        if escalate_reason is None:
            assert haiku_result is not None
            return RoutedReview(result=haiku_result, deferred=False)

        if self._sonnet is None:
            if not haiku_attempted:
                self.budget.record_deferred()
                return RoutedReview(result=None, deferred=True)
            return RoutedReview(result=haiku_result, deferred=False)

        if not self.budget.can_call(is_sonnet=True):
            self.budget.record_blocked()
            if not haiku_attempted:
                self.budget.record_deferred()
                return RoutedReview(result=None, deferred=True)
            return RoutedReview(result=haiku_result, deferred=False)

        sonnet_result = self._attempt(
            db,
            provider=self._sonnet,
            route=AiRoute.SONNET,
            routing_reason=escalate_reason,
            issuer_name=issuer_name,
            source_description=source_description,
            candidates=candidates,
            discovery_run_id=discovery_run_id,
            filing_monitor_run_id=filing_monitor_run_id,
            issuer_id=issuer_id,
            bundle_key=bundle_key,
            operation=operation,
        )
        if sonnet_result is not None:
            return RoutedReview(result=sonnet_result, deferred=False)
        # Sonnet also failed/unparseable — fall back to Haiku's (weaker,
        # already-paid-for) result if we have one, else deterministic.
        return RoutedReview(result=haiku_result, deferred=False)

    def _attempt(
        self,
        db: Session,
        *,
        provider: LLMProvider,
        route: AiRoute,
        routing_reason: str,
        issuer_name: str,
        source_description: str,
        candidates: list[RuleMatch],
        discovery_run_id: UUID | None,
        filing_monitor_run_id: UUID | None,
        issuer_id: UUID,
        bundle_key: str,
        operation: AiOperation,
    ) -> EvidenceReviewResult | None:
        is_sonnet = route is AiRoute.SONNET
        result: EvidenceReviewResult | None = None
        model_used = "unknown"
        input_tokens: int | None = None
        output_tokens: int | None = None
        success = False
        error_classification: str | None = None
        retries = 0
        started = time.monotonic()

        for attempt in range(self._config.max_attempts):
            retries = attempt
            try:
                captured: dict[str, object] = {}
                result = _review_with_capture(
                    provider,
                    issuer_name=issuer_name,
                    source_description=source_description,
                    candidates=candidates,
                    captured=captured,
                )
                model_used = str(captured.get("model", model_used))
                input_tokens = captured.get("input_tokens")  # type: ignore[assignment]
                output_tokens = captured.get("output_tokens")  # type: ignore[assignment]
                success = result is not None
                if not success:
                    error_classification = "unparseable_response"
                break
            except Exception as exc:  # noqa: BLE001 - classified below, never silent
                error_classification = type(exc).__name__
                if attempt + 1 < self._config.max_attempts:
                    time.sleep(self._config.retry_delay_seconds)
                    continue
                result = None
                success = False

        latency_ms = int((time.monotonic() - started) * 1000)
        cost_usd = estimate_cost_usd(
            model=model_used, input_tokens=input_tokens, output_tokens=output_tokens
        )
        self.budget.record(cost_usd=cost_usd, is_sonnet=is_sonnet)

        ai_call_log_repository.create_call_log(
            db,
            AiCallLogCreate(
                discovery_run_id=discovery_run_id,
                filing_monitor_run_id=filing_monitor_run_id,
                issuer_id=issuer_id,
                bundle_key=bundle_key,
                operation=operation,
                route=route,
                model=model_used,
                routing_reason=routing_reason,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                estimated_cost_usd=cost_usd,
                latency_ms=latency_ms,
                success=success,
                retry_count=retries,
                error_classification=error_classification,
            ),
        )
        db.commit()
        return result


def _review_with_capture(
    provider: LLMProvider,
    *,
    issuer_name: str,
    source_description: str,
    candidates: list[RuleMatch],
    captured: dict[str, object],
) -> EvidenceReviewResult | None:
    """Wraps `review_evidence_candidates` to also surface the raw
    `CompletionResponse`'s model/token usage for logging — that function's
    own return type (`EvidenceReviewResult | None`) deliberately carries no
    provider-mechanics fields, so this captures them via the same
    provider's `.complete()` instead of changing that function's contract.
    """
    capturing = _CapturingProvider(provider, captured)
    return review_evidence_candidates(
        capturing,
        issuer_name=issuer_name,
        source_description=source_description,
        candidates=candidates,
    )


class _CapturingProvider:
    """A thin `LLMProvider`-shaped pass-through that records the last real
    response's model/token usage into `captured` — the response text
    itself is never inspected or altered here."""

    def __init__(self, inner: LLMProvider, captured: dict[str, object]) -> None:
        self._inner = inner
        self._captured = captured

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        response = self._inner.complete(request)
        self._captured["model"] = response.model
        self._captured["input_tokens"] = response.input_tokens
        self._captured["output_tokens"] = response.output_tokens
        return response

    def call_tools(self, request: object) -> object:
        return self._inner.call_tools(request)

    def create_embeddings(self, texts: list[str]) -> list[list[float]]:
        return self._inner.create_embeddings(texts)
