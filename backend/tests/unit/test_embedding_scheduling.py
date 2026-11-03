"""Pure scheduling rules (Milestone 10D.2 scheduling increment): delay
parsing, backoff, retry planning, eligibility at the exact boundary, and the
executable specification of the claim predicate. Injected clock and jitter;
nothing sleeps; no database."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.core.types import EmbeddingJobStatus
from app.embeddings import scheduling as sch
from app.embeddings.scheduling import SchedulingView

NOW = datetime(2026, 11, 2, 12, 0, 0, tzinfo=UTC)
P, M, V = "openai", "text-embedding-3-large", "alias-test"


# --- parse_retry_after ---


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("0", 0.0),
        ("7", 7.0),
        ("  7 ", 7.0),
        ("2.5", 2.5),
        ("00012", 12.0),
        ("1e2", 100.0),
    ],
)
def test_numeric_retry_after_is_honored(raw: str, expected: float) -> None:
    assert sch.parse_retry_after(raw, now=NOW) == expected


@pytest.mark.parametrize(
    "raw", [None, "", "   ", "soon", "-1", "-0.5", "nan", "inf", "-inf", "1,5"]
)
def test_missing_or_malformed_or_negative_retry_after_is_none(raw: str | None) -> None:
    assert sch.parse_retry_after(raw, now=NOW) is None


def test_http_date_retry_after_is_resolved_against_the_injected_clock() -> None:
    future = "Mon, 02 Nov 2026 12:01:30 GMT"
    assert sch.parse_retry_after(future, now=NOW) == 90.0
    past = "Mon, 02 Nov 2026 11:00:00 GMT"
    assert sch.parse_retry_after(past, now=NOW) == 0.0  # valid: retry now
    equal = "Mon, 02 Nov 2026 12:00:00 GMT"
    assert sch.parse_retry_after(equal, now=NOW) == 0.0
    assert sch.parse_retry_after("Mon, 99 Foo 2026 12:00:00 GMT", now=NOW) is None


def test_http_date_in_another_timezone_offset_is_the_same_instant() -> None:
    # 07:01:30 -0500 == 12:01:30 UTC
    assert sch.parse_retry_after("Mon, 02 Nov 2026 07:01:30 -0500", now=NOW) == 90.0
    local_now = NOW.astimezone(timezone(timedelta(hours=9)))
    assert sch.parse_retry_after("Mon, 02 Nov 2026 12:01:30 GMT", now=local_now) == 90.0


def test_extreme_delays_are_bounded_not_overflowing() -> None:
    assert sch.parse_retry_after("1e30", now=NOW) == sch._SANITY_MAX_DELAY_SECONDS
    far = "Fri, 01 Jan 2999 00:00:00 GMT"
    assert sch.parse_retry_after(far, now=NOW) == sch._SANITY_MAX_DELAY_SECONDS


def test_naive_now_is_rejected() -> None:
    # Numeric seconds need no clock; an HTTP-date is resolved against it.
    assert sch.parse_retry_after("5", now=datetime(2026, 11, 2, 12, 0, 0)) == 5.0
    with pytest.raises(ValueError, match="naive"):
        sch.parse_retry_after("Mon, 02 Nov 2026 12:01:30 GMT", now=datetime(2026, 11, 2))


# --- backoff ---


def test_backoff_doubles_is_capped_and_jitter_only_adds() -> None:
    low = [sch.backoff_seconds(n, jitter=lambda: 0.0) for n in range(1, 10)]
    assert low[:4] == [30.0, 60.0, 120.0, 240.0]
    assert max(low) == sch.BACKOFF_CAP_SECONDS
    high = sch.backoff_seconds(1, jitter=lambda: 0.999999)
    assert 30.0 < high <= 30.0 * (1 + sch.JITTER_FRACTION)
    for n in range(1, 10):
        assert sch.backoff_seconds(n, jitter=lambda: 0.5) >= low[n - 1]  # never earlier


def test_backoff_clamps_a_misbehaving_jitter_source() -> None:
    assert sch.backoff_seconds(1, jitter=lambda: -5.0) == 30.0
    assert sch.backoff_seconds(1, jitter=lambda: 9.0) == 30.0 * (1 + sch.JITTER_FRACTION)
    assert sch.backoff_seconds(0, jitter=lambda: 0.0) == 30.0  # attempt floor


# --- retry planning ---


def test_rate_limit_waits_for_the_later_of_vendor_delay_and_backoff() -> None:
    plan = sch.plan_rate_limit_retry(1, vendor_delay_seconds=300, now=NOW, jitter=lambda: 0.0)
    assert not plan.hold and plan.not_before == NOW + timedelta(seconds=300)
    plan = sch.plan_rate_limit_retry(3, vendor_delay_seconds=5, now=NOW, jitter=lambda: 0.0)
    assert plan.not_before == NOW + timedelta(seconds=120)  # backoff dominates a short delay
    plan = sch.plan_rate_limit_retry(1, vendor_delay_seconds=None, now=NOW, jitter=lambda: 0.0)
    assert plan.not_before == NOW + timedelta(seconds=30)


def test_a_vendor_delay_is_never_shortened() -> None:
    for delay in (1.0, 29.0, 31.0, 1000.0, sch.MAX_AUTOMATIC_DELAY_SECONDS):
        plan = sch.plan_rate_limit_retry(1, vendor_delay_seconds=delay, now=NOW, jitter=lambda: 0.0)
        assert plan.not_before is not None
        assert (plan.not_before - NOW).total_seconds() >= delay


def test_the_automatic_limit_boundary_schedules_at_the_limit_and_holds_beyond_it() -> None:
    at = sch.plan_rate_limit_retry(
        1, vendor_delay_seconds=sch.MAX_AUTOMATIC_DELAY_SECONDS, now=NOW, jitter=lambda: 0.0
    )
    assert not at.hold
    beyond = sch.plan_rate_limit_retry(
        1, vendor_delay_seconds=sch.MAX_AUTOMATIC_DELAY_SECONDS + 0.001, now=NOW, jitter=lambda: 0.0
    )
    assert beyond.hold and beyond.not_before is None
    assert beyond.hold_reason == sch.HOLD_RETRY_AFTER_TOO_LONG  # held, not retried early


def test_transient_retry_uses_backoff_only() -> None:
    plan = sch.plan_transient_retry(2, now=NOW, jitter=lambda: 0.0)
    assert plan.not_before == NOW + timedelta(seconds=60) and not plan.hold


def test_planning_converts_the_clock_to_utc() -> None:
    local = NOW.astimezone(timezone(timedelta(hours=-5)))
    plan = sch.plan_transient_retry(1, now=local, jitter=lambda: 0.0)
    assert plan.not_before == NOW + timedelta(seconds=30)
    assert plan.not_before is not None and plan.not_before.utcoffset() == timedelta(0)


# --- eligibility at the boundary ---


def test_null_is_due_and_the_exact_boundary_is_due() -> None:
    assert sch.is_due(None, now=NOW)
    assert sch.is_due(NOW, now=NOW)  # equality is eligible
    assert sch.is_due(NOW - timedelta(microseconds=1), now=NOW)
    assert not sch.is_due(NOW + timedelta(microseconds=1), now=NOW)


def test_due_comparison_is_timezone_aware() -> None:
    plus9 = NOW.astimezone(timezone(timedelta(hours=9)))
    assert sch.is_due(plus9, now=NOW)  # same instant
    assert not sch.is_due(plus9 + timedelta(seconds=1), now=NOW)
    with pytest.raises(ValueError, match="naive"):
        sch.is_due(datetime(2026, 11, 2, 12, 0, 0), now=NOW)


# --- the claim predicate (executable specification of the SQL) ---


def _job(
    jid: str,
    *,
    status: EmbeddingJobStatus = EmbeddingJobStatus.PENDING,
    not_before: datetime | None = None,
    wide: bool = False,
    provider: str = P,
    model: str = M,
    version: str = V,
    age: int = 0,
) -> SchedulingView:
    return SchedulingView(
        job_id=jid,
        provider=provider,
        model=model,
        model_version=version,
        status=status,
        retry_not_before=not_before,
        provider_wide=wide,
        created_at=NOW - timedelta(minutes=age),
    )


def _claimable(jobs: list[SchedulingView], *, now: datetime = NOW) -> list[str]:
    return [
        j.job_id for j in sch.claimable_jobs(jobs, provider=P, model=M, model_version=V, now=now)
    ]


def test_due_pending_jobs_are_claimable_oldest_first() -> None:
    assert _claimable([_job("new", age=1), _job("old", age=9), _job("mid", age=5)]) == [
        "old",
        "mid",
        "new",
    ]


def test_a_per_job_delay_hides_only_that_job() -> None:
    delayed = _job("a", not_before=NOW + timedelta(seconds=30), age=9)
    assert _claimable([delayed, _job("b", age=1)]) == ["b"]
    assert _claimable([delayed], now=NOW + timedelta(seconds=30)) == ["a"]  # boundary
    assert _claimable([delayed], now=NOW + timedelta(seconds=29)) == []


def test_a_provider_wide_delay_blocks_every_job_for_that_provider_and_model() -> None:
    blocker = _job("blocker", not_before=NOW + timedelta(seconds=90), wide=True, age=9)
    others = [_job("other", age=1)]
    assert _claimable([blocker, *others]) == []
    assert _claimable([blocker, *others], now=NOW + timedelta(seconds=90)) == ["blocker", "other"]
    assert _claimable([blocker, *others], now=NOW + timedelta(seconds=89)) == []


def test_a_provider_wide_delay_does_not_block_another_provider_or_model() -> None:
    blocker = _job("blocker", not_before=NOW + timedelta(hours=1), wide=True)
    elsewhere = _job("x", provider="voyage", model="voyage-4")
    other_model = _job("y", model="text-embedding-3-small")
    assert (
        sch.claimable_jobs(
            [blocker, elsewhere, other_model],
            provider="voyage",
            model="voyage-4",
            model_version=V,
            now=NOW,
        )[0].job_id
        == "x"
    )
    assert [
        j.job_id
        for j in sch.claimable_jobs(
            [blocker, other_model],
            provider=P,
            model="text-embedding-3-small",
            model_version=V,
            now=NOW,
        )
    ] == ["y"]


def test_a_held_provider_wide_job_blocks_the_queue_until_it_is_released() -> None:
    held = _job("held", status=EmbeddingJobStatus.HELD, wide=True, age=9)
    pending = _job("p", age=1)
    assert _claimable([held, pending]) == []
    released = _job("held", status=EmbeddingJobStatus.PENDING, wide=False, age=9)
    assert _claimable([released, pending]) == ["held", "p"]


def test_a_non_provider_wide_hold_blocks_only_itself_and_is_never_claimable() -> None:
    held = _job("held", status=EmbeddingJobStatus.HELD, wide=False)
    assert _claimable([held, _job("p")]) == ["p"]
    assert "held" not in _claimable([held])


def test_only_pending_jobs_are_claimable_and_the_version_must_match() -> None:
    jobs = [
        _job("proc", status=EmbeddingJobStatus.PROCESSING),
        _job("done", status=EmbeddingJobStatus.COMPLETED),
        _job("failed", status=EmbeddingJobStatus.FAILED),
        _job("blocked", status=EmbeddingJobStatus.BLOCKED_INELIGIBLE),
        _job("old-version", version="alias-old"),
        _job("ok"),
    ]
    assert _claimable(jobs) == ["ok"]
