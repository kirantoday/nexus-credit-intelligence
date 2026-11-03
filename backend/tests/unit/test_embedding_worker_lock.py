"""Exclusive worker ownership (Milestone 10D.2 scheduling increment).

Connection and service doubles only. These tests prove the **control flow**:
refusal, loss, ordering and cleanup, and that no provider request is made
unless ownership is shown. They do not prove PostgreSQL advisory-lock
semantics, pooling behavior, failover or crash release; that is the future
integration-test matrix (see the readiness report).
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy.pool import NullPool

from app.embeddings import worker_lock as wl
from app.embeddings.budget import EmbeddingRunBudget
from app.embeddings.dimensions import EmbeddingModelSpec
from app.embeddings.errors import EmbeddingConfigurationError, EmbeddingOwnershipLostError
from app.embeddings.processor import JobOutcome, ProcessorConfig, process_job
from app.scripts.run_document_embedding_worker import EXIT_LOCK_HELD, run

from .embedding_support import InMemoryJobStore, make_chunks, make_job
from .test_document_embedding_worker import _FakeDb, _FakeService, _settings
from .test_openai_embedding_adapter import (  # noqa: F401 - _network_tripwire is autouse
    SPEC,
    _json_response,
    _network_tripwire,
    _ok_body,
    _provider,
)

# --- connection doubles ---


class FakeResult:
    def __init__(self, value: Any) -> None:
        self._value = value

    def scalar(self) -> Any:
        return self._value


class FakeConn:
    def __init__(
        self,
        *,
        acquire: Any = True,
        fail_liveness: bool = False,
        fail_unlock: bool = False,
        fail_acquire: bool = False,
    ) -> None:
        self.acquire = acquire
        self.fail_liveness = fail_liveness
        self.fail_unlock = fail_unlock
        self.fail_acquire = fail_acquire
        self.executed: list[tuple[str, Any]] = []
        self.closed = False
        self.options: dict[str, Any] = {}

    def execution_options(self, **options: Any) -> FakeConn:
        self.options = options
        return self

    def execute(self, statement: Any, params: Any = None) -> FakeResult:
        sql = str(statement)
        self.executed.append((sql, params))
        if "pg_try_advisory_lock" in sql:
            if self.fail_acquire:
                raise RuntimeError("connection refused")
            return FakeResult(self.acquire)
        if "pg_advisory_unlock" in sql:
            if self.fail_unlock:
                raise RuntimeError("gone")
            return FakeResult(True)
        if self.fail_liveness:
            raise RuntimeError("server closed the connection")
        return FakeResult(1)

    def close(self) -> None:
        self.closed = True


class FakeEngine:
    def __init__(self, conn: FakeConn) -> None:
        self.conn = conn
        self.disposed = 0
        self.connects = 0

    def connect(self) -> FakeConn:
        self.connects += 1
        return self.conn

    def dispose(self) -> None:
        self.disposed += 1


def _lock(conn: FakeConn) -> tuple[wl.PostgresAdvisoryWorkerLock, FakeEngine]:
    engine = FakeEngine(conn)
    return wl.PostgresAdvisoryWorkerLock(engine, key=42), engine  # type: ignore[arg-type]


# --- key ---


def test_the_lock_key_is_stable_signed_64_bit_and_per_provider_and_model() -> None:
    key = wl.advisory_lock_key("openai", "text-embedding-3-large")
    assert key == wl.advisory_lock_key("openai", "text-embedding-3-large")
    assert -(2**63) <= key < 2**63
    assert key != wl.advisory_lock_key("openai", "text-embedding-3-small")
    assert key != wl.advisory_lock_key("voyage", "text-embedding-3-large")


# --- PostgresAdvisoryWorkerLock ---


def test_acquire_takes_a_session_lock_on_a_dedicated_autocommit_connection() -> None:
    conn = FakeConn(acquire=True)
    lock, engine = _lock(conn)
    assert lock.acquire() is True
    assert conn.options == {"isolation_level": "AUTOCOMMIT"}  # not inside a transaction
    assert conn.executed[0][1] == {"key": 42} and not conn.closed
    lock.assert_held()  # a liveness query on the same connection
    assert engine.connects == 1
    with pytest.raises(RuntimeError, match="already held"):
        lock.acquire()


def test_a_second_worker_is_refused_and_leaves_nothing_open() -> None:
    conn = FakeConn(acquire=False)
    lock, _engine = _lock(conn)
    assert lock.acquire() is False
    assert conn.closed
    with pytest.raises(EmbeddingOwnershipLostError):
        lock.assert_held()  # never held


def test_an_acquire_error_closes_the_connection_and_propagates() -> None:
    conn = FakeConn(fail_acquire=True)
    lock, _engine = _lock(conn)
    with pytest.raises(RuntimeError):
        lock.acquire()
    assert conn.closed


def test_loss_of_the_connection_is_detected_and_discards_it() -> None:
    conn = FakeConn()
    lock, _engine = _lock(conn)
    lock.acquire()
    conn.fail_liveness = True
    with pytest.raises(EmbeddingOwnershipLostError) as info:
        lock.assert_held()
    assert "server closed" not in str(info.value)  # driver text is not propagated
    assert conn.closed
    with pytest.raises(EmbeddingOwnershipLostError):
        lock.assert_held()  # stays lost


def test_release_unlocks_closes_and_disposes_and_is_idempotent() -> None:
    conn = FakeConn()
    lock, engine = _lock(conn)
    lock.acquire()
    lock.release()
    assert any("pg_advisory_unlock" in sql for sql, _ in conn.executed)
    assert conn.closed and engine.disposed == 1
    lock.release()  # second call: nothing to do, must not raise
    assert engine.disposed == 2


def test_release_never_raises_even_if_unlock_fails() -> None:
    conn = FakeConn(fail_unlock=True)
    lock, engine = _lock(conn)
    lock.acquire()
    lock.release()
    assert conn.closed and engine.disposed == 1


def test_the_production_lock_requires_the_direct_url_and_uses_a_non_pooling_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = SimpleNamespace(provider="openai", model_id="text-embedding-3-large")
    with pytest.raises(EmbeddingConfigurationError, match="DIRECT_DATABASE_URL"):
        wl.build_postgres_worker_lock(SimpleNamespace(direct_database_url=None), spec)

    captured: dict[str, Any] = {}

    def fake_create_engine(url: str, **kwargs: Any) -> FakeEngine:
        captured["url"] = url
        captured.update(kwargs)
        return FakeEngine(FakeConn())

    monkeypatch.setattr("sqlalchemy.create_engine", fake_create_engine)
    lock = wl.build_postgres_worker_lock(
        SimpleNamespace(direct_database_url="postgresql://u:p@host/db"), spec
    )
    assert captured["poolclass"] is NullPool  # never a shared pool
    assert lock._connection is None  # nothing opened until acquire()


# --- OwnershipGuardedProvider ---


class _Inner:
    provider_name = "openai"
    model_id = "m"
    model_version = "v"
    dimension = 1024
    max_batch_size = 8
    max_batch_input_size = 123

    def __init__(self) -> None:
        self.calls = 0
        self.closed = 0

    def input_size(self, text: str) -> int:
        return len(text)

    def embed_documents(self, texts: Any) -> str:
        self.calls += 1
        return "docs"

    def embed_query(self, text: str) -> str:
        self.calls += 1
        return "query"

    def close(self) -> None:
        self.closed += 1


class _ToggleLock:
    def __init__(self, ok: bool = True) -> None:
        self.ok = ok
        self.checks = 0

    def assert_held(self) -> None:
        self.checks += 1
        if not self.ok:
            raise EmbeddingOwnershipLostError("lost")


def test_the_guard_checks_ownership_before_every_request_and_sends_nothing_when_lost() -> None:
    inner, lock = _Inner(), _ToggleLock()
    guarded = wl.OwnershipGuardedProvider(inner, lock)  # type: ignore[arg-type]
    assert guarded.embed_documents(["a"]) == "docs" and guarded.embed_query("q") == "query"  # type: ignore[comparison-overlap]
    assert lock.checks == 2 and inner.calls == 2
    lock.ok = False
    with pytest.raises(EmbeddingOwnershipLostError):
        guarded.embed_documents(["a"])
    with pytest.raises(EmbeddingOwnershipLostError):
        guarded.embed_query("q")
    assert inner.calls == 2  # no request after ownership was lost


def test_the_guard_delegates_identity_batch_hooks_and_close() -> None:
    inner = _Inner()
    guarded = wl.OwnershipGuardedProvider(inner, _ToggleLock())  # type: ignore[arg-type]
    assert (guarded.provider_name, guarded.model_id, guarded.dimension) == ("openai", "m", 1024)
    assert guarded.max_batch_size == 8 and guarded.max_batch_input_size == 123
    assert guarded.input_size("abc") == 3
    guarded.close()
    assert inner.closed == 1


def test_an_ownership_loss_during_a_job_sends_no_further_request_and_refunds_the_attempt() -> None:
    provider, rec = _provider(
        lambda request: _json_response(
            200,
            _ok_body(len(__import__("json").loads(request.content)["input"])),
        )
    )

    class _LoseAfterOne(_ToggleLock):
        def assert_held(self) -> None:
            self.checks += 1
            if self.checks > 1:
                raise EmbeddingOwnershipLostError("lost")

    guarded = wl.OwnershipGuardedProvider(provider, _LoseAfterOne())  # type: ignore[arg-type]
    store = InMemoryJobStore(chunks=make_chunks(4))
    budget = EmbeddingRunBudget(max_tokens=1_000_000)
    result = process_job(
        make_job(),
        store=store,
        provider=guarded,
        spec=SPEC,
        budget=budget,
        config=ProcessorConfig(batch_size=2, max_attempts=3),
    )
    assert result.outcome is JobOutcome.REQUEUED and result.abort_run is True
    assert result.note == "worker_ownership_lost"
    assert rec.count == 1  # only the first batch, while ownership was shown
    assert (
        store.requeues[0]["refund_attempt"] is True
        and store.requeues[0]["retry_not_before"] is None
    )
    assert budget.requests_made == 1  # the lost-ownership attempt is not counted as a request


# --- worker flow with a lock ---

OPENAI_SPEC = EmbeddingModelSpec("openai", "text-embedding-3-large", "alias-test", 1024)


class _Events:
    def __init__(self) -> None:
        self.log: list[str] = []


class _Svc(_FakeService):
    def __init__(self, events: _Events, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.events = events

    def reclaim_stale_jobs(self, db: Any, **kwargs: Any) -> list[Any]:
        self.events.log.append("reclaim")
        return super().reclaim_stale_jobs(db, **kwargs)

    def record_worker_started(self, db: Any, **kwargs: Any) -> None:
        self.events.log.append("audit")
        super().record_worker_started(db, **kwargs)

    def process_next_job(self, db: Any, **kwargs: Any) -> Any:
        self.events.log.append("process")
        return super().process_next_job(db, **kwargs)


class _RecordingLock:
    def __init__(
        self, events: _Events, *, acquire: bool = True, lose_after: int | None = None
    ) -> None:
        self.events = events
        self._acquire = acquire
        self.lose_after = lose_after
        self.checks = 0
        self.released = 0

    def acquire(self) -> bool:
        self.events.log.append("acquire")
        return self._acquire

    def assert_held(self) -> None:
        self.checks += 1
        if self.lose_after is not None and self.checks > self.lose_after:
            raise EmbeddingOwnershipLostError("lost")

    def release(self) -> None:
        self.events.log.append("release")
        self.released += 1


def _worker(
    events: _Events,
    *,
    lock: _RecordingLock | None,
    service: _Svc | None = None,
    argv: list[str] | None = None,
    use_factory: bool = True,
    provider: Any = None,
    db: _FakeDb | None = None,
) -> tuple[int, _Svc, _FakeDb, Any]:
    svc = service or _Svc(events, results=[])
    fake_db = db or _FakeDb()
    inner = provider or _Inner()
    code = run(
        argv or ["--max-tokens", "100"],
        settings=_settings(direct_database_url="postgresql://redacted/db"),
        session_factory=lambda: fake_db,
        provider_factory=lambda _s: (inner, OPENAI_SPEC),
        service=svc,
        lock_factory=(lambda _s, _spec: lock) if use_factory else None,
    )
    return code, svc, fake_db, inner


def test_ownership_then_audit_then_work_then_cleanup_in_that_order() -> None:
    events = _Events()
    lock = _RecordingLock(events)
    code, _svc, db, inner = _worker(events, lock=lock)
    assert code == 0
    assert events.log == ["acquire", "audit", "reclaim", "process", "release"]
    assert db.closed and inner.closed == 1  # the provider's client is closed too


def test_a_second_worker_exits_without_audit_claim_or_provider_request() -> None:
    events = _Events()
    lock = _RecordingLock(events, acquire=False)
    code, svc, db, inner = _worker(events, lock=lock)
    assert code == EXIT_LOCK_HELD
    assert events.log == ["acquire", "release"]  # released: nothing leaks
    assert svc.worker_started == [] and svc.process_calls == 0 and inner.calls == 0
    assert db.closed


def test_a_real_provider_without_a_lock_factory_fails_closed() -> None:
    events = _Events()
    code, svc, _db, inner = _worker(events, lock=None, use_factory=False)
    assert code == 1 and svc.process_calls == 0 and inner.calls == 0
    assert events.log == []


def test_a_lock_error_fails_closed_and_cleans_up() -> None:
    events = _Events()

    class _Broken(_RecordingLock):
        def acquire(self) -> bool:
            raise RuntimeError("driver: password authentication failed for user secret")

    code, svc, _db, _inner = _worker(events, lock=_Broken(events))
    assert code == 1 and svc.process_calls == 0 and svc.worker_started == []


def test_an_audit_failure_means_zero_provider_work_and_the_lock_is_released() -> None:
    events = _Events()
    lock = _RecordingLock(events)
    svc = _Svc(events, results=[])
    svc.audit_error = RuntimeError("audit table unavailable")
    code, svc, db, inner = _worker(events, lock=lock, service=svc)
    assert code == 1
    assert "process" not in events.log and "reclaim" not in events.log
    assert inner.calls == 0 and lock.released == 1 and db.closed


def test_ownership_loss_between_jobs_stops_before_the_next_claim() -> None:
    events = _Events()
    lock = _RecordingLock(events, lose_after=0)
    code, svc, _db, _inner = _worker(
        events, lock=lock, argv=["--max-tokens", "100", "--max-jobs", "3"]
    )
    assert code == 1 and svc.process_calls == 0
    assert events.log[-1] == "release"


def test_cleanup_runs_even_when_the_service_raises() -> None:
    events = _Events()
    lock = _RecordingLock(events)

    class _Exploding(_Svc):
        def process_next_job(self, db: Any, **kwargs: Any) -> Any:
            raise RuntimeError("unexpected")

    with pytest.raises(RuntimeError):
        _worker(events, lock=lock, service=_Exploding(events, results=[]))
    assert lock.released == 1


def test_the_fake_provider_needs_no_lock_and_never_takes_one() -> None:
    events = _Events()
    svc = _Svc(events, results=[])
    code = run(
        ["--max-tokens", "100"],
        settings=_settings(),
        session_factory=lambda: _FakeDb(),
        service=svc,
        lock_factory=lambda *_a: pytest.fail("the fake provider must not take the lock"),
    )
    assert code == 0 and events.log == ["audit", "reclaim", "process"]


def test_enqueue_mode_takes_no_lock_and_makes_no_provider_request() -> None:
    events = _Events()
    code, svc, db, inner = _worker(
        events,
        lock=_RecordingLock(events),
        argv=["--max-tokens", "100", "--enqueue-extraction", str(uuid.UUID(int=5))],
    )
    assert code == 0 and "acquire" not in events.log and inner.calls == 0
    assert svc.worker_started == [] and db.commits == 1


def test_disabled_embeddings_build_neither_a_lock_nor_a_provider() -> None:
    called: list[str] = []
    code = run(
        ["--max-tokens", "100"],
        settings=_settings(embeddings_enabled=False),
        session_factory=lambda: _FakeDb(),
        provider_factory=lambda _s: called.append("provider"),  # type: ignore[arg-type, return-value]
        lock_factory=lambda *_a: called.append("lock"),
        service=_FakeService(),
    )
    assert code == 1 and called == []
