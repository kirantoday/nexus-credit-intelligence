"""Unit tests for the extraction worker entry point's observability and
exit-code contract (Milestone 10C recovery). Entirely DB-free: `SessionLocal`,
the storage client, and the service functions are replaced with fakes, so
these tests can never claim or mutate a real `document_extraction` row.
"""

from __future__ import annotations

import logging
import uuid
from types import SimpleNamespace
from typing import Any

import pytest

from app.scripts import run_document_extraction_worker as worker


class _FakeSession:
    def __init__(self, *, fail_connect: bool = False) -> None:
        self.fail_connect = fail_connect
        self.closed = False

    def execute(self, *_args: Any, **_kwargs: Any) -> None:
        if self.fail_connect:
            raise RuntimeError("could not connect")

    def rollback(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True


class _FakeStorage:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def _patch_common(monkeypatch: pytest.MonkeyPatch, *, session: _FakeSession | None) -> _FakeStorage:
    import app.db.session as session_module
    import app.storage.factory as factory_module

    storage = _FakeStorage()
    monkeypatch.setattr(
        session_module, "SessionLocal", (lambda: session) if session is not None else None
    )
    monkeypatch.setattr(factory_module, "get_storage_client", lambda _settings: storage)
    # `main()` installs a SIGTERM handler and reconfigures logging; keep the
    # test process's own handlers intact.
    monkeypatch.setattr(worker, "_configure_process", lambda: None)
    return storage


def _extraction(status: str = "completed") -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        research_document_id=uuid.uuid4(),
        status=SimpleNamespace(value=status),
        attempt_count=1,
        page_count=3,
        chunk_count=7,
        table_count=1,
        extractor_provider="pymupdf4llm",
        extractor_version="x",
        chunking_strategy_version="structure_v1",
        is_current=status == "completed",
        error_classification=None,
        error_message=None,
    )


def test_missing_database_config_logs_and_exits_1(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _patch_common(monkeypatch, session=None)
    with caplog.at_level(logging.INFO, logger=worker.logger.name):
        assert worker.main() == 1
    text = caplog.text
    assert "worker_started" in text
    assert "outcome=config_error" in text


def test_db_connection_failure_is_logged_and_exits_1(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    session = _FakeSession(fail_connect=True)
    _patch_common(monkeypatch, session=session)
    with caplog.at_level(logging.INFO, logger=worker.logger.name):
        assert worker.main() == 1
    assert "outcome=db_connection_error" in caplog.text
    assert session.closed


def test_empty_queue_exits_0_and_logs_no_eligible_job(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    from app.services import document_extraction_service as service

    session = _FakeSession()
    storage = _patch_common(monkeypatch, session=session)
    monkeypatch.setattr(service, "reclaim_stale_jobs", lambda _db: [])
    monkeypatch.setattr(service, "process_one", lambda _db, _storage: None)
    with caplog.at_level(logging.INFO, logger=worker.logger.name):
        assert worker.main() == 0
    for marker in (
        "worker_started",
        "config_validated",
        "database_connected",
        "stale_jobs_reclaimed count=0",
        "outcome=no_eligible_job",
    ):
        assert marker in caplog.text
    assert session.closed and storage.closed


def test_processed_job_logs_counts_and_never_content(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    from app.services import document_extraction_service as service

    result = _extraction("completed")
    _patch_common(monkeypatch, session=_FakeSession())
    monkeypatch.setattr(service, "reclaim_stale_jobs", lambda _db: [])
    monkeypatch.setattr(service, "process_one", lambda _db, _storage: result)
    with caplog.at_level(logging.INFO, logger=worker.logger.name):
        assert worker.main() == 0
    assert "outcome=processed" in caplog.text
    assert f"extraction_id={result.id}" in caplog.text
    assert "chunk_count=7" in caplog.text
    assert "elapsed_s=" in caplog.text


def test_failed_extraction_is_a_normal_exit_0_with_a_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    from app.services import document_extraction_service as service

    result = _extraction("failed")
    result.error_classification = "deterministic"
    result.error_message = "ExtractionFailure: corrupt"
    _patch_common(monkeypatch, session=_FakeSession())
    monkeypatch.setattr(service, "reclaim_stale_jobs", lambda _db: [])
    monkeypatch.setattr(service, "process_one", lambda _db, _storage: result)
    with caplog.at_level(logging.INFO, logger=worker.logger.name):
        assert worker.main() == 0
    assert "extraction_not_completed" in caplog.text
    assert "error_classification=deterministic" in caplog.text


def test_unhandled_exception_is_logged_with_traceback_and_exits_1(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    from app.services import document_extraction_service as service

    _patch_common(monkeypatch, session=_FakeSession())

    def boom(_db: object) -> list[object]:
        raise ValueError("unexpected")

    monkeypatch.setattr(service, "reclaim_stale_jobs", boom)
    with caplog.at_level(logging.INFO, logger=worker.logger.name):
        assert worker.main() == 1
    assert "outcome=unhandled_error" in caplog.text
    assert "ValueError" in caplog.text
