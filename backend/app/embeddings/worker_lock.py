"""Exclusive embedding-worker ownership (Milestone 10D.2 scheduling increment).

**Selected first-release model: one active embedding worker per provider and
model.** Provider rate limits and spend limits belong to the provider
account, so the first release avoids a shared cooldown/rate limiter between
concurrent workers by making concurrency impossible instead.

**Mechanism.** A PostgreSQL *session-level advisory lock*
(`pg_try_advisory_lock`) taken on a **dedicated connection** that stays open
for the whole run:

- The connection comes from a dedicated engine with `NullPool`, so it is
  never returned to (and silently reused from) a shared pool, which would
  leave the lock attached to a pooled session. It must be a **direct,
  session-mode** connection (`DIRECT_DATABASE_URL`); a transaction-pooling
  endpoint does not preserve session state and could not hold this lock.
- It is opened in AUTOCOMMIT, so the lock does not live inside a transaction,
  and **no row lock and no open transaction is held over a provider call**:
  the job claim commits before the provider is contacted.
- A second worker's `pg_try_advisory_lock` returns false and it exits without
  building a request. It never waits.
- **Crash behavior.** The lock belongs to the database session, so PostgreSQL
  releases it when the connection or process dies. A crashed worker therefore
  cannot leave a stale lock; its `processing` job is recovered by the stale
  rule with a delay.
- **Ownership loss.** Before every provider request `OwnershipGuardedProvider`
  runs `assert_held()`, a liveness query on the lock connection. If the
  connection is gone the request is **not sent** and the run ends. This detects
  a dead connection; it cannot detect every way a session could have been
  replaced, and it is **unproven until integration tests** against a real
  database (including a pooler, a failover and a killed backend).
- **Cleanup.** `release()` runs `pg_advisory_unlock`, closes the connection and
  disposes the engine, and is called in a `finally` on every exit path.

Unit tests use a connection double; they prove the control flow (refusal, loss,
cleanup, zero calls), not the database's locking.
"""

from __future__ import annotations

import hashlib
from typing import Any, Protocol

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from app.embeddings.base import EmbeddingProvider, EmbeddingResult
from app.embeddings.errors import EmbeddingConfigurationError, EmbeddingOwnershipLostError

_LOCK_NAMESPACE = "nexus.embedding_worker.v1"


def advisory_lock_key(provider: str, model: str) -> int:
    """A stable signed 64-bit key for one provider/model queue."""
    digest = hashlib.sha256(f"{_LOCK_NAMESPACE}:{provider}:{model}".encode()).digest()
    return int.from_bytes(digest[:8], "big", signed=True)


class WorkerLock(Protocol):
    def acquire(self) -> bool:
        """Takes the lock without waiting. `False` when another worker holds
        it. Raises on a database error."""
        ...

    def assert_held(self) -> None:
        """Raises `EmbeddingOwnershipLostError` if ownership cannot be shown."""
        ...

    def release(self) -> None:
        """Idempotent; never raises."""
        ...


class PostgresAdvisoryWorkerLock:
    def __init__(self, engine: Engine, *, key: int, dispose_engine: bool = True) -> None:
        self._engine = engine
        self._key = key
        self._dispose_engine = dispose_engine
        self._connection: Connection | None = None

    def acquire(self) -> bool:
        if self._connection is not None:
            raise RuntimeError("the worker lock is already held by this object")
        connection = self._engine.connect().execution_options(isolation_level="AUTOCOMMIT")
        try:
            acquired = bool(
                connection.execute(
                    text("SELECT pg_try_advisory_lock(:key)"), {"key": self._key}
                ).scalar()
            )
        except Exception:
            connection.close()
            raise
        if not acquired:
            connection.close()
            return False
        self._connection = connection
        return True

    def assert_held(self) -> None:
        if self._connection is None:
            raise EmbeddingOwnershipLostError("the worker lock is not held")
        try:
            self._connection.execute(text("SELECT 1")).scalar()
        except Exception:
            self._discard()
            raise EmbeddingOwnershipLostError(
                "the worker lock connection is no longer usable"
            ) from None

    def release(self) -> None:
        connection, self._connection = self._connection, None
        try:
            if connection is not None:
                try:
                    connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": self._key})
                except Exception:  # noqa: BLE001 - the session end releases it anyway
                    pass
                finally:
                    connection.close()
        finally:
            if self._dispose_engine:
                try:
                    self._engine.dispose()
                except Exception:  # noqa: BLE001 - cleanup must not raise
                    pass

    def _discard(self) -> None:
        connection, self._connection = self._connection, None
        if connection is not None:
            try:
                connection.close()
            except Exception:  # noqa: BLE001 - already broken
                pass


def build_postgres_worker_lock(settings: Any, spec: Any) -> PostgresAdvisoryWorkerLock:
    """The production lock: a dedicated `NullPool` engine on the direct
    (session-mode) database URL. No connection is opened until `acquire()`."""
    from sqlalchemy import create_engine
    from sqlalchemy.pool import NullPool

    url = getattr(settings, "direct_database_url", None)
    if not url:
        raise EmbeddingConfigurationError(
            "DIRECT_DATABASE_URL is required for the exclusive embedding worker lock"
        )
    engine = create_engine(url, poolclass=NullPool)
    return PostgresAdvisoryWorkerLock(engine, key=advisory_lock_key(spec.provider, spec.model_id))


class OwnershipGuardedProvider:
    """Wraps a provider so that ownership is re-checked immediately before
    every request. If it cannot be shown, no request is made."""

    def __init__(self, inner: EmbeddingProvider, lock: WorkerLock) -> None:
        self._inner = inner
        self._lock = lock

    @property
    def provider_name(self) -> str:
        return self._inner.provider_name

    @property
    def model_id(self) -> str:
        return self._inner.model_id

    @property
    def model_version(self) -> str:
        return self._inner.model_version

    @property
    def dimension(self) -> int:
        return self._inner.dimension

    @property
    def max_batch_size(self) -> int:
        return self._inner.max_batch_size

    def __getattr__(self, name: str) -> Any:
        # Optional hooks such as `input_size` / `max_batch_input_size`.
        return getattr(self._inner, name)

    def embed_documents(self, texts: Any) -> EmbeddingResult:
        self._lock.assert_held()
        return self._inner.embed_documents(texts)

    def embed_query(self, text: str) -> EmbeddingResult:
        self._lock.assert_held()
        return self._inner.embed_query(text)

    def close(self) -> None:
        closer = getattr(self._inner, "close", None)
        if callable(closer):
            closer()
