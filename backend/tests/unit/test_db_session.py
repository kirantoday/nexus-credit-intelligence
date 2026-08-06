"""Unit tests for get_db()'s commit/rollback lifecycle (app/db/session.py).

Mocks SessionLocal entirely so this is a fast, no-database unit test of the
control flow itself: commit once on success, rollback on exception, always close.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.db import session as session_module


def test_get_db_commits_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_session = MagicMock()
    monkeypatch.setattr(session_module, "SessionLocal", lambda: fake_session)

    gen = session_module.get_db()
    yielded = next(gen)
    assert yielded is fake_session

    with pytest.raises(StopIteration):
        next(gen)

    fake_session.commit.assert_called_once()
    fake_session.rollback.assert_not_called()
    fake_session.close.assert_called_once()


def test_get_db_rolls_back_on_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_session = MagicMock()
    monkeypatch.setattr(session_module, "SessionLocal", lambda: fake_session)

    gen = session_module.get_db()
    next(gen)

    with pytest.raises(RuntimeError, match="boom"):
        gen.throw(RuntimeError("boom"))

    fake_session.commit.assert_not_called()
    fake_session.rollback.assert_called_once()
    fake_session.close.assert_called_once()


def test_get_db_raises_clear_error_when_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(session_module, "SessionLocal", None)

    with pytest.raises(RuntimeError, match="DATABASE_URL is not configured"):
        next(session_module.get_db())
