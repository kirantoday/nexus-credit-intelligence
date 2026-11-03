"""Pure scheduling rules for embedding jobs (Milestone 10D.2, ADR-021).

Everything here is side-effect free and takes its clock and jitter as
arguments, so the rules are testable without sleeping and so the SQL in
`app.repositories.document_embedding_job_repository` has an executable
specification (`claimable_jobs`) to be checked against in the future
integration tests.

**Scope of a delay.** Provider rate limits, credential problems and quota or
spend limits belong to the provider *account*, not to one job. A job whose
failure is of that kind is marked `provider_wide`: while it is pending with a
future `retry_not_before`, or held, no other job for the same provider and
model is claimable either. Failures of one request (5xx, timeouts,
persistence errors) delay only that job.

**Attempts.** An attempt is consumed when a job is claimed. It is refunded
only for stops that are not the job's fault and that sent nothing the job
could be blamed for: a budget stop, and credential/quota/configuration holds.
A rate-limit requeue does *not* refund, so the attempt cap bounds the number
of rate-limited requests per job. The cap ends a job as `failed`.

**Delays.** A valid vendor delay (`Retry-After` seconds or HTTP-date) is
honored exactly and never shortened: the job is scheduled at the later of the
vendor delay and the exponential backoff. A vendor delay longer than
`MAX_AUTOMATIC_DELAY_SECONDS` is not truncated (that would retry earlier than
the vendor allows) and not scheduled automatically either: the job is held
for an operator. Missing, malformed or negative delays fall back to backoff.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime

from app.core.types import EmbeddingJobStatus

BACKOFF_BASE_SECONDS = 30.0
BACKOFF_CAP_SECONDS = 3600.0
JITTER_FRACTION = 0.25
# Longest vendor-mandated delay the system will schedule automatically (6 h).
MAX_AUTOMATIC_DELAY_SECONDS = 6 * 3600.0
# Sanity bound on any parsed delay (10 years) so arithmetic cannot overflow.
_SANITY_MAX_DELAY_SECONDS = 10 * 365 * 24 * 3600.0

HOLD_PROVIDER_CREDENTIALS_OR_QUOTA = "provider_credentials_or_quota"
HOLD_PROVIDER_CONFIGURATION = "provider_configuration"
HOLD_PROVIDER_SPEC_MISMATCH = "provider_spec_mismatch"
HOLD_RETRY_AFTER_TOO_LONG = "retry_after_exceeds_automatic_limit"

Clock = Callable[[], datetime]
Jitter = Callable[[], float]


def utc_now() -> datetime:
    return datetime.now(UTC)


def ensure_utc(value: datetime) -> datetime:
    """Timestamps are always UTC-aware. A naive value is a programming error
    (it would silently compare as local time), so it is rejected."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("naive datetime is not allowed; scheduling uses UTC-aware timestamps")
    return value.astimezone(UTC)


def parse_retry_after(raw: str | None, *, now: datetime) -> float | None:
    """Seconds to wait from `now`, or `None` when absent or invalid.

    Accepts non-negative decimal seconds or an HTTP-date. A date in the past
    is a valid "retry now" and yields 0.0. Negative, non-finite, empty or
    unparsable values yield `None` (the caller falls back to backoff).
    """
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    try:
        seconds = float(text)
    except ValueError:
        seconds = None
    if seconds is not None:
        if not math.isfinite(seconds) or seconds < 0:
            return None
        return min(seconds, _SANITY_MAX_DELAY_SECONDS)
    try:
        when = parsedate_to_datetime(text)
    except (TypeError, ValueError, IndexError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)  # HTTP-dates are GMT by definition
    delta = (when - ensure_utc(now)).total_seconds()
    return min(max(delta, 0.0), _SANITY_MAX_DELAY_SECONDS)


def backoff_seconds(attempt: int, *, jitter: Jitter) -> float:
    """Exponential backoff for the `attempt`-th consumed attempt (>= 1),
    capped, with jitter added on top so the delay is never shorter than the
    deterministic base. `jitter()` must return a value in [0, 1)."""
    exponent = max(0, attempt - 1)
    raw = min(BACKOFF_CAP_SECONDS, BACKOFF_BASE_SECONDS * (2.0**exponent))
    fraction = min(max(jitter(), 0.0), 1.0)
    return raw * (1.0 + JITTER_FRACTION * fraction)


@dataclass(frozen=True, slots=True)
class RetryPlan:
    hold: bool
    not_before: datetime | None
    hold_reason: str | None = None


def plan_rate_limit_retry(
    attempt: int, *, vendor_delay_seconds: float | None, now: datetime, jitter: Jitter
) -> RetryPlan:
    """Rate limits are provider-wide. A valid vendor delay is never shortened
    and, if beyond the automatic limit, is not scheduled at all."""
    if vendor_delay_seconds is not None and vendor_delay_seconds > MAX_AUTOMATIC_DELAY_SECONDS:
        return RetryPlan(hold=True, not_before=None, hold_reason=HOLD_RETRY_AFTER_TOO_LONG)
    delay = max(vendor_delay_seconds or 0.0, backoff_seconds(attempt, jitter=jitter))
    return RetryPlan(hold=False, not_before=ensure_utc(now) + timedelta(seconds=delay))


def plan_transient_retry(attempt: int, *, now: datetime, jitter: Jitter) -> RetryPlan:
    return RetryPlan(
        hold=False,
        not_before=ensure_utc(now) + timedelta(seconds=backoff_seconds(attempt, jitter=jitter)),
    )


# --- executable specification of the claim predicate ---------------------------------


@dataclass(frozen=True, slots=True)
class SchedulingView:
    """The columns the claim predicate reads."""

    job_id: str
    provider: str
    model: str
    model_version: str
    status: EmbeddingJobStatus
    retry_not_before: datetime | None
    provider_wide: bool
    created_at: datetime


def is_due(retry_not_before: datetime | None, *, now: datetime) -> bool:
    """A `NULL` time means "no delay". A time equal to `now` is due."""
    return retry_not_before is None or ensure_utc(retry_not_before) <= ensure_utc(now)


def provider_queue_blocked(
    jobs: Sequence[SchedulingView], *, provider: str, model: str, now: datetime
) -> bool:
    """True when some provider-wide job for this provider and model is held,
    or is pending with a delay that has not yet elapsed."""
    for job in jobs:
        if job.provider != provider or job.model != model or not job.provider_wide:
            continue
        if job.status is EmbeddingJobStatus.HELD:
            return True
        if (
            job.status is EmbeddingJobStatus.PENDING
            and job.retry_not_before is not None
            and ensure_utc(job.retry_not_before) > ensure_utc(now)
        ):
            return True
    return False


def claimable_jobs(
    jobs: Sequence[SchedulingView], *, provider: str, model: str, model_version: str, now: datetime
) -> list[SchedulingView]:
    """The jobs a worker for this provider/model/version may claim, oldest
    first. The SQL claim must be equivalent to this function."""
    if provider_queue_blocked(jobs, provider=provider, model=model, now=now):
        return []
    eligible = [
        job
        for job in jobs
        if job.status is EmbeddingJobStatus.PENDING
        and job.provider == provider
        and job.model == model
        and job.model_version == model_version
        and is_due(job.retry_not_before, now=now)
    ]
    return sorted(eligible, key=lambda j: j.created_at)
