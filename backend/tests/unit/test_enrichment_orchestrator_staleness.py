"""Unit tests for `app/services/enrichment_orchestrator.py`'s `_should_run`
staleness policy (PLAN.md Milestone 7.5 section 8) — pure function, no I/O.

This is the logic that makes the orchestrator apply uniformly to newly
discovered and already-known issuers alike: whether a provider runs is
driven entirely by the current `issuer_enrichment_status` row (never
checked / stale / retry-due / forced), never by an issuer's discovery
recency.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.core.types import EnrichmentStatus, ProviderName
from app.domain.enrichment_status import IssuerEnrichmentStatus
from app.services.enrichment_orchestrator import _should_run

_NOW = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)
_TTL = timedelta(hours=12)


def _status(**overrides: object) -> IssuerEnrichmentStatus:
    defaults: dict[str, object] = dict(
        id=uuid4(),
        issuer_id=uuid4(),
        provider=ProviderName.SEC_EDGAR,
        status=EnrichmentStatus.COMPLETE,
        last_attempt_at=_NOW - timedelta(hours=1),
        last_success_at=_NOW - timedelta(hours=1),
        next_retry_at=None,
        attempt_count=1,
        records_found=1,
        error_classification=None,
        checkpoint=None,
        created_at=_NOW - timedelta(days=1),
        updated_at=_NOW - timedelta(hours=1),
    )
    defaults.update(overrides)
    return IssuerEnrichmentStatus(**defaults)  # type: ignore[arg-type]


def test_never_checked_always_runs() -> None:
    assert _should_run(None, ttl=_TTL, force=False, now=_NOW) is True


def test_force_always_runs_even_when_fresh() -> None:
    fresh = _status(last_success_at=_NOW - timedelta(minutes=1))
    assert _should_run(fresh, ttl=_TTL, force=True, now=_NOW) is True


def test_fresh_complete_status_is_skipped() -> None:
    fresh = _status(status=EnrichmentStatus.COMPLETE, last_success_at=_NOW - timedelta(hours=1))
    assert _should_run(fresh, ttl=_TTL, force=False, now=_NOW) is False


def test_stale_complete_status_runs_again() -> None:
    stale = _status(status=EnrichmentStatus.COMPLETE, last_success_at=_NOW - timedelta(hours=13))
    assert _should_run(stale, ttl=_TTL, force=False, now=_NOW) is True


def test_no_data_status_follows_same_ttl_as_complete() -> None:
    stale_no_data = _status(
        status=EnrichmentStatus.NO_DATA, last_success_at=_NOW - timedelta(hours=13)
    )
    assert _should_run(stale_no_data, ttl=_TTL, force=False, now=_NOW) is True


def test_failed_retryable_runs_only_after_next_retry_at() -> None:
    not_due_yet = _status(
        status=EnrichmentStatus.FAILED_RETRYABLE,
        last_success_at=None,
        next_retry_at=_NOW + timedelta(hours=1),
    )
    due = _status(
        status=EnrichmentStatus.FAILED_RETRYABLE,
        last_success_at=None,
        next_retry_at=_NOW - timedelta(minutes=1),
    )
    assert _should_run(not_due_yet, ttl=_TTL, force=False, now=_NOW) is False
    assert _should_run(due, ttl=_TTL, force=False, now=_NOW) is True


def test_failed_permanent_never_auto_retries() -> None:
    permanent = _status(status=EnrichmentStatus.FAILED_PERMANENT, last_success_at=None)
    assert _should_run(permanent, ttl=_TTL, force=False, now=_NOW) is False


def test_blocked_entitlement_never_auto_retries() -> None:
    blocked = _status(status=EnrichmentStatus.BLOCKED_ENTITLEMENT, last_success_at=None)
    assert _should_run(blocked, ttl=_TTL, force=False, now=_NOW) is False


def test_unsupported_never_auto_retries() -> None:
    unsupported = _status(status=EnrichmentStatus.UNSUPPORTED, last_success_at=None)
    assert _should_run(unsupported, ttl=_TTL, force=False, now=_NOW) is False


def test_ambiguous_rechecked_after_its_own_ttl_not_provider_ttl() -> None:
    recent_ambiguous = _status(
        status=EnrichmentStatus.AMBIGUOUS,
        last_success_at=None,
        last_attempt_at=_NOW - timedelta(hours=1),
    )
    old_ambiguous = _status(
        status=EnrichmentStatus.AMBIGUOUS,
        last_success_at=None,
        last_attempt_at=_NOW - timedelta(days=4),
    )
    assert _should_run(recent_ambiguous, ttl=_TTL, force=False, now=_NOW) is False
    assert _should_run(old_ambiguous, ttl=_TTL, force=False, now=_NOW) is True


def test_running_status_stuck_past_ttl_is_safe_to_retry() -> None:
    stuck = _status(
        status=EnrichmentStatus.RUNNING,
        last_success_at=None,
        last_attempt_at=_NOW - timedelta(hours=2),
    )
    fresh_running = _status(
        status=EnrichmentStatus.RUNNING,
        last_success_at=None,
        last_attempt_at=_NOW - timedelta(minutes=5),
    )
    assert _should_run(stuck, ttl=_TTL, force=False, now=_NOW) is True
    assert _should_run(fresh_running, ttl=_TTL, force=False, now=_NOW) is False
