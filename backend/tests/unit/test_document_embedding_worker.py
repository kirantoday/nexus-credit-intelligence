"""Unit tests for `app.scripts.run_document_embedding_worker.run`
(Milestone 10D.2): feature-flag gating, budget requirements, and the
exit-code discipline. The service and database session are injected fakes —
no database, network, or provider is touched."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any

import pytest

from app.embeddings.dimensions import EMBEDDING_COLUMN_DIMENSION
from app.embeddings.errors import EmbeddingConfigurationError
from app.embeddings.processor import JobOutcome, JobResult
from app.retrieval.eligibility import EligibilityReason
from app.scripts.run_document_embedding_worker import run


class _FakeDb:
    def __init__(self) -> None:
        self.closed = False
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def close(self) -> None:
        self.closed = True


class _NotEligible(Exception):
    def __init__(self) -> None:
        self.reason = EligibilityReason.NOT_APPROVED
        super().__init__("not eligible")


class _NotFound(Exception):
    pass


class _FakeService:
    DocumentNotEligibleError = _NotEligible
    DocumentExtractionNotFoundError = _NotFound

    def __init__(self, results: list[JobResult | None] | None = None) -> None:
        self.results = list(results or [])
        self.process_calls = 0
        self.enqueue_error: Exception | None = None
        self.reclaims = 0

    def reclaim_stale_jobs(self, db: Any, **_: Any) -> list[Any]:
        self.reclaims += 1
        return []

    def process_next_job(self, db: Any, **_: Any) -> JobResult | None:
        self.process_calls += 1
        return self.results.pop(0) if self.results else None

    def enqueue_embedding(self, db: Any, **_: Any) -> Any:
        if self.enqueue_error is not None:
            raise self.enqueue_error
        return SimpleNamespace(id=uuid.UUID(int=7), status=SimpleNamespace(value="pending"))


def _settings(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "environment": "local",
        "embeddings_enabled": True,
        "embedding_provider": "fake",
        "embedding_model_id": None,
        "embedding_model_version": None,
        "embedding_dimension": EMBEDDING_COLUMN_DIMENSION,
        "embedding_batch_size": 8,
        "embedding_job_max_attempts": 3,
        "embedding_stale_processing_after_seconds": 900,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _call(
    argv: list[str],
    *,
    settings: SimpleNamespace | None = None,
    service: _FakeService | None = None,
    db: _FakeDb | None = None,
    session_factory: Any = "default",
    provider_factory: Any = None,
) -> int:
    fake_db = db or _FakeDb()
    return run(
        argv,
        settings=settings or _settings(),
        session_factory=(lambda: fake_db) if session_factory == "default" else session_factory,
        provider_factory=provider_factory,
        service=service or _FakeService(),
    )


def test_feature_flag_defaults_off_and_blocks_the_worker(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = _call(["--max-tokens", "100"], settings=_settings(embeddings_enabled=False))
    assert code == 1
    assert "disabled" in capsys.readouterr().err


def test_an_explicit_token_budget_is_required() -> None:
    with pytest.raises(SystemExit) as excinfo:
        _call([])
    assert excinfo.value.code == 2


def test_a_non_positive_budget_is_a_configuration_error() -> None:
    assert _call(["--max-tokens", "0"]) == 1


def test_missing_database_is_a_configuration_error() -> None:
    assert _call(["--max-tokens", "100"], session_factory=None) == 1


def test_an_unbuildable_provider_is_a_configuration_error() -> None:
    def broken(_settings: object) -> object:
        raise EmbeddingConfigurationError("no vendor approved")

    assert _call(["--max-tokens", "100"], provider_factory=broken) == 1


def test_a_cost_ceiling_for_an_unpriced_model_is_refused() -> None:
    from app.embeddings.dimensions import EmbeddingModelSpec
    from app.embeddings.fake import FakeEmbeddingProvider

    def unpriced(_settings: object) -> tuple[object, object]:
        return (
            FakeEmbeddingProvider(model_id="unpriced", model_version="v1"),
            EmbeddingModelSpec("fake", "unpriced", "v1", EMBEDDING_COLUMN_DIMENSION),
        )

    assert _call(["--max-tokens", "100", "--max-cost-usd", "1.0"], provider_factory=unpriced) == 1


def test_nothing_pending_exits_zero_and_closes_the_session(
    capsys: pytest.CaptureFixture[str],
) -> None:
    db = _FakeDb()
    service = _FakeService(results=[])
    assert _call(["--max-tokens", "100"], service=service, db=db) == 0
    assert db.closed
    assert "nothing to do" in capsys.readouterr().out
    assert service.reclaims == 1


@pytest.mark.parametrize(
    "outcome", [JobOutcome.FAILED, JobOutcome.BLOCKED_INELIGIBLE, JobOutcome.REQUEUED]
)
def test_a_job_that_ends_failed_blocked_or_requeued_is_still_exit_zero(
    outcome: JobOutcome,
) -> None:
    service = _FakeService(results=[JobResult(outcome, note="x")])
    assert _call(["--max-tokens", "100"], service=service) == 0


def test_run_is_bounded_by_max_jobs() -> None:
    done = JobResult(JobOutcome.COMPLETED, embedded=1)
    service = _FakeService(results=[done, done, done, done])
    assert _call(["--max-tokens", "100", "--max-jobs", "2"], service=service) == 0
    assert service.process_calls == 2


def test_a_credentials_or_configuration_stop_exits_non_zero_and_stops_the_run() -> None:
    stop = JobResult(JobOutcome.REQUEUED, note="provider_unavailable", abort_run=True)
    service = _FakeService(results=[stop, JobResult(JobOutcome.COMPLETED)])
    assert _call(["--max-tokens", "100", "--max-jobs", "5"], service=service) == 1
    assert service.process_calls == 1


def test_a_rate_limit_stop_ends_the_run_early_but_exits_zero() -> None:
    stop = JobResult(JobOutcome.REQUEUED, note="transient_failure_requeued", abort_run=True)
    service = _FakeService(results=[stop, JobResult(JobOutcome.COMPLETED)])
    assert _call(["--max-tokens", "100", "--max-jobs", "5"], service=service) == 0
    assert service.process_calls == 1


def test_enqueue_refusal_is_reported_without_a_reason_leak_and_commits_nothing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    db = _FakeDb()
    service = _FakeService()
    service.enqueue_error = _NotEligible()
    code = _call(
        ["--max-tokens", "100", "--enqueue-extraction", str(uuid.UUID(int=5))],
        service=service,
        db=db,
    )
    assert code == 0
    assert "not_approved" in capsys.readouterr().out
    assert db.commits == 0
    assert service.process_calls == 0  # enqueue mode never processes


def test_enqueue_success_commits_and_prints_only_an_id(capsys: pytest.CaptureFixture[str]) -> None:
    db = _FakeDb()
    code = _call(["--max-tokens", "100", "--enqueue-extraction", str(uuid.UUID(int=5))], db=db)
    assert code == 0
    assert db.commits == 1
    assert str(uuid.UUID(int=7)) in capsys.readouterr().out


def test_a_provider_that_owns_an_http_client_is_closed_after_the_run() -> None:
    from .embedding_support import SPEC

    class _ClosableProvider:
        closed = 0

        def close(self) -> None:
            type(self).closed += 1

    provider = _ClosableProvider()
    code = _call(
        ["--max-tokens", "100"],
        provider_factory=lambda _settings: (provider, SPEC),
    )
    assert code == 0
    assert _ClosableProvider.closed == 1
