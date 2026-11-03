"""Repository behavior for scheduling and holds, against a session double
(Milestone 10D.2 scheduling increment).

These tests exercise the Python side of each function and compile the claim
statement to PostgreSQL text *without connecting*. They do **not** prove what
the database does: `FOR UPDATE SKIP LOCKED` behavior, the NOT EXISTS lookup,
transaction commit, concurrent claimers and restart behavior are unverified
until the future integration tests (matrix in the readiness report).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy.dialects import postgresql

from app.core.types import EmbeddingJobStatus
from app.models.document_embedding_job import DocumentEmbeddingJob as JobModel
from app.repositories import document_embedding_job_repository as repo

NOW = datetime(2026, 11, 2, 12, 0, 0, tzinfo=UTC)


def _row(**overrides: Any) -> JobModel:
    values: dict[str, Any] = {
        "id": uuid.uuid4(),
        "research_document_id": uuid.uuid4(),
        "document_extraction_id": uuid.uuid4(),
        "embedding_provider": "openai",
        "embedding_model": "text-embedding-3-large",
        "embedding_model_version": "alias-test",
        "dimension": 1024,
        "status": "pending",
        "attempt_count": 0,
        "error_classification": None,
        "error_message": None,
        "status_note": None,
        "chunk_total": None,
        "chunks_embedded": 0,
        "chunks_replaced": 0,
        "provenance_id": None,
        "requested_by": None,
        "started_at": None,
        "completed_at": None,
        "created_at": NOW - timedelta(hours=1),
        "retry_not_before": None,
        "provider_wide": False,
        "hold_reason": None,
        "held_at": None,
        "released_at": None,
        "released_by": None,
    }
    values.update(overrides)
    return JobModel(**values)


class _Scalars:
    def __init__(self, rows: list[JobModel]) -> None:
        self._rows = rows

    def first(self) -> JobModel | None:
        return self._rows[0] if self._rows else None

    def all(self) -> list[JobModel]:
        return self._rows


class _Result:
    def __init__(self, rows: list[JobModel]) -> None:
        self._rows = rows

    def scalars(self) -> _Scalars:
        return _Scalars(self._rows)


class FakeSession:
    def __init__(self, *, rows: list[JobModel] | None = None) -> None:
        self.rows = rows or []
        self.executed: list[Any] = []
        self.flushes = 0

    def get(self, _model: Any, key: uuid.UUID) -> JobModel | None:
        return next((r for r in self.rows if r.id == key), None)

    def execute(self, statement: Any) -> _Result:
        self.executed.append(statement)
        return _Result(self.rows)

    def flush(self) -> None:
        self.flushes += 1

    def refresh(self, _row: Any) -> None:
        return None


# --- claim ---


def test_claim_returns_none_when_nothing_is_claimable() -> None:
    db = FakeSession(rows=[])
    assert repo.claim_next_pending(db, provider="openai", model="m", model_version="v") is None  # type: ignore[arg-type]


def test_claim_consumes_an_attempt_clears_the_schedule_and_stamps_the_injected_time() -> None:
    row = _row(retry_not_before=NOW - timedelta(seconds=1), provider_wide=True, attempt_count=1)
    db = FakeSession(rows=[row])
    job = repo.claim_next_pending(
        db,  # type: ignore[arg-type]
        provider="openai",
        model="text-embedding-3-large",
        model_version="alias-test",
        now=NOW,
    )
    assert job is not None and job.status is EmbeddingJobStatus.PROCESSING
    assert job.attempt_count == 2 and job.started_at == NOW
    assert job.retry_not_before is None and job.provider_wide is False


def test_claim_rejects_a_naive_clock() -> None:
    with pytest.raises(ValueError, match="naive"):
        repo.claim_next_pending(
            FakeSession(rows=[_row()]),  # type: ignore[arg-type]
            provider="p",
            model="m",
            model_version="v",
            now=datetime(2026, 11, 2, 12, 0, 0),
        )


def _compiled_claim() -> str:
    statement = repo._claim_statement(provider="openai", model="m", model_version="v", now=NOW)
    return str(statement.compile(dialect=postgresql.dialect()))


def test_the_claim_sql_has_the_scheduling_predicates() -> None:
    sql = _compiled_claim()
    assert "FOR UPDATE SKIP LOCKED" in sql  # existing claim discipline preserved
    assert "LIMIT" in sql and "ORDER BY" in sql and "created_at" in sql
    assert "embedding_provider =" in sql and "embedding_model =" in sql
    assert "embedding_model_version =" in sql
    assert "retry_not_before IS NULL" in sql and "retry_not_before <=" in sql  # boundary: <=
    assert "NOT (EXISTS" in sql  # provider-wide blocker lookup
    assert "provider_wide IS true" in sql
    # the blocker covers held jobs and still-delayed pending jobs
    assert "status =" in sql and "retry_not_before >" in sql


def test_the_claim_sql_never_matches_held_or_processing_rows() -> None:
    statement = repo._claim_statement(provider="p", model="m", model_version="v", now=NOW)
    params = statement.compile(dialect=postgresql.dialect()).params
    values = {v for v in params.values() if isinstance(v, str)}
    assert "pending" in values  # the claimed status
    # `held` appears only inside the blocker subquery, never as a claim target
    main_where = _compiled_claim().split("NOT (EXISTS")[0]
    assert main_where.count("status =") == 1


# --- requeue / stale recovery ---


def test_requeue_stores_a_utc_delay_and_provider_scope_only_with_a_time() -> None:
    row = _row(status="processing", attempt_count=2)
    db = FakeSession(rows=[row])
    later = NOW + timedelta(seconds=90)
    job = repo.requeue_pending(
        db,  # type: ignore[arg-type]
        row.id,
        error_classification="transient",
        error_message="x",
        note="n",
        refund_attempt=False,
        retry_not_before=later.astimezone(UTC),
        provider_wide=True,
    )
    assert job.status is EmbeddingJobStatus.PENDING and job.retry_not_before == later
    assert job.provider_wide is True and job.attempt_count == 2
    again = repo.requeue_pending(
        db,  # type: ignore[arg-type]
        row.id,
        error_classification=None,
        error_message=None,
        note="budget_stop",
        refund_attempt=True,
        provider_wide=True,  # no time: scope is dropped
    )
    assert again.retry_not_before is None and again.provider_wide is False
    assert again.attempt_count == 1  # refunded


def test_requeue_rejects_a_naive_time() -> None:
    row = _row(status="processing")
    with pytest.raises(ValueError, match="naive"):
        repo.requeue_pending(
            FakeSession(rows=[row]),  # type: ignore[arg-type]
            row.id,
            error_classification=None,
            error_message=None,
            note="n",
            refund_attempt=False,
            retry_not_before=datetime(2026, 11, 2, 13, 0, 0),
        )


def test_stale_recovery_delays_the_job_and_never_resurrects_exhausted_attempts() -> None:
    stale_a = _row(status="processing", attempt_count=1, started_at=NOW - timedelta(hours=1))
    stale_b = _row(status="processing", attempt_count=3, started_at=NOW - timedelta(hours=1))
    db = FakeSession(rows=[stale_a, stale_b])
    later = NOW + timedelta(seconds=45)
    recovered = repo.reclaim_stale_processing(
        db,  # type: ignore[arg-type]
        stale_after=NOW,
        max_attempts=3,
        retry_not_before=later,
    )
    by_id = {j.id: j for j in recovered}
    first, second = by_id[stale_a.id], by_id[stale_b.id]
    assert first.status is EmbeddingJobStatus.PENDING and first.retry_not_before == later
    assert first.provider_wide is False and first.started_at is None
    assert second.status is EmbeddingJobStatus.FAILED and second.retry_not_before is None


def test_the_stale_recovery_query_selects_only_processing_rows() -> None:
    db = FakeSession(rows=[])
    repo.reclaim_stale_processing(db, stale_after=NOW, max_attempts=3)  # type: ignore[arg-type]
    sql = str(db.executed[0].compile(dialect=postgresql.dialect()))
    assert "status =" in sql and "started_at <" in sql
    values = list(db.executed[0].compile(dialect=postgresql.dialect()).params.values())
    assert "processing" in values and "held" not in values  # holds are untouched


# --- holds and release ---


def test_hold_makes_a_non_claimable_job_and_records_evidence() -> None:
    row = _row(status="processing", attempt_count=2, started_at=NOW)
    db = FakeSession(rows=[row])
    job = repo.hold_job(
        db,  # type: ignore[arg-type]
        row.id,
        reason="provider_credentials_or_quota",
        provider_wide=True,
        error_classification="deterministic",
        error_message="EmbeddingAuthError (deterministic)",
        refund_attempt=True,
        now=NOW,
    )
    assert job.status is EmbeddingJobStatus.HELD
    assert job.hold_reason == "provider_credentials_or_quota" and job.held_at == NOW
    assert job.provider_wide is True and job.retry_not_before is None
    assert job.attempt_count == 1 and job.error_message == "EmbeddingAuthError (deterministic)"
    assert job.status_note == "held:provider_credentials_or_quota" and job.started_at is None


def test_release_requires_a_held_job() -> None:
    for status in ("pending", "processing", "completed", "failed", "blocked_ineligible"):
        row = _row(status=status)
        with pytest.raises(repo.JobNotHeldError):
            repo.release_held(FakeSession(rows=[row]), row.id, released_by="op", now=NOW)  # type: ignore[arg-type]


def test_release_reopens_the_job_but_keeps_lifetime_evidence() -> None:
    held_at = NOW - timedelta(hours=2)
    row = _row(
        status="held",
        attempt_count=2,
        provider_wide=True,
        hold_reason="provider_configuration",
        held_at=held_at,
        error_classification="deterministic",
        error_message="EmbeddingConfigurationError (deterministic)",
    )
    job = repo.release_held(FakeSession(rows=[row]), row.id, released_by="  Dana ", now=NOW)  # type: ignore[arg-type]
    assert job.status is EmbeddingJobStatus.PENDING
    assert job.retry_not_before is None and job.provider_wide is False
    assert job.released_at == NOW and job.released_by == "  Dana "  # caller trims
    # not silently reset:
    assert job.attempt_count == 2 and job.hold_reason == "provider_configuration"
    assert job.held_at == held_at
    assert job.error_message == "EmbeddingConfigurationError (deterministic)"
    assert job.status_note == "released_from_hold"


def test_held_jobs_count_as_active_so_re_enqueueing_cannot_bypass_a_hold() -> None:
    assert EmbeddingJobStatus.HELD.value in repo._ACTIVE
    # The partial unique index includes `held` too (checked in the model and
    # migration-source tests).


def test_terminal_transitions_clear_any_pending_schedule() -> None:
    for transition, kwargs in (
        (repo.mark_completed, {"chunk_total": 1}),
        (repo.mark_failed, {"error_classification": "transient", "error_message": "e"}),
        (repo.mark_blocked, {"reason": "archived"}),
    ):
        row = _row(status="processing", retry_not_before=None, provider_wide=True)
        job = transition(FakeSession(rows=[row]), row.id, **kwargs)  # type: ignore[arg-type]
        assert job.retry_not_before is None and job.provider_wide is False


def test_list_held_orders_by_hold_time_and_returns_only_held() -> None:
    db = FakeSession(rows=[_row(status="held", hold_reason="r", held_at=NOW)])
    jobs = repo.list_held(db)  # type: ignore[arg-type]
    assert [j.status for j in jobs] == [EmbeddingJobStatus.HELD]
    sql = str(db.executed[0].compile(dialect=postgresql.dialect()))
    assert "held_at" in sql and "ORDER BY" in sql
