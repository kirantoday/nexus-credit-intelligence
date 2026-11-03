"""Policy audit events, holds and release (Milestone 10D.2 scheduling
increment): atomicity, ordering, field safety and fail-closed behavior.

Repository and session doubles only. They prove the order of calls and what
is written; whether a commit is really durable and a rollback really leaves
no row is database behavior covered by the future integration tests.
An audit event is evidence of what was observed or asserted. It grants
nothing, and no field here claims owner acceptance.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest

from app.core.types import AuditEventType, EmbeddingJobStatus
from app.embeddings.dimensions import EmbeddingModelSpec
from app.embeddings.errors import EmbeddingConfigurationError
from app.embeddings.factory import OPENAI_POLICY_APPROVAL_VALUE, get_embedding_provider
from app.embeddings.processor import JobContext, ProcessorConfig
from app.repositories.document_embedding_job_repository import JobNotHeldError
from app.retrieval.eligibility import EligibilityFacts
from app.scripts import release_held_embedding_job as release_script
from app.services import document_embedding_service as svc

from .test_document_embedding_worker import _FakeDb, _FakeService, _settings

SPEC = EmbeddingModelSpec("openai", "text-embedding-3-large", "alias-test", 1024)
NOW = datetime(2026, 11, 2, 12, 0, 0, tzinfo=UTC)
SECRET = "sk-test-SECRET-VALUE-must-never-appear"
_SHA = "a" * 64


class Db:
    """Session double that records the order of operations."""

    def __init__(self, log: list[str] | None = None, *, fail_commit: bool = False) -> None:
        self.log = log if log is not None else []
        self.fail_commit = fail_commit

    def commit(self) -> None:
        self.log.append("commit")
        if self.fail_commit:
            raise RuntimeError("commit failed")

    def rollback(self) -> None:
        self.log.append("rollback")


def _settings_obj(**overrides: Any) -> SimpleNamespace:
    values: dict[str, Any] = {
        "embedding_external_policy_approval": OPENAI_POLICY_APPROVAL_VALUE,
        "embedding_policy_reference": "adr-021-accepted-sha256-test",
        "embedding_api_key": SECRET,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


# --- policy_observation / fields ---


def test_observation_distinguishes_a_matching_string_from_acceptance() -> None:
    obs = svc.policy_observation(_settings_obj(), SPEC, asserted_actor="Dana")
    assert obs.acknowledgement_required and obs.acknowledgement_matches_required
    assert obs.policy_reference_observed == "adr-021-accepted-sha256-test"
    fields = svc._policy_fields(obs)
    assert fields["policy_acknowledgement_source"] == "environment_variable"
    assert fields["policy_reference_verified"] is False
    assert fields["owner_acceptance_verified"] is False
    assert fields["asserted_actor"] == "Dana" and fields["identity_verified"] is False


@pytest.mark.parametrize(
    ("ack", "reference", "matches", "ref_seen"),
    [
        (None, None, False, None),
        ("", "  ", False, None),
        ("openai:text-embedding-3-large ", "ref-1", False, "ref-1"),
        ("OPENAI:text-embedding-3-large", None, False, None),
        ("voyage:voyage-4", "ref-2", False, "ref-2"),
        (OPENAI_POLICY_APPROVAL_VALUE, " ref-3 ", True, "ref-3"),
    ],
)
def test_missing_or_mismatching_policy_settings_are_recorded_as_such(
    ack: str | None, reference: str | None, matches: bool, ref_seen: str | None
) -> None:
    obs = svc.policy_observation(
        _settings_obj(embedding_external_policy_approval=ack, embedding_policy_reference=reference),
        SPEC,
        asserted_actor=None,
    )
    assert obs.acknowledgement_matches_required is matches
    assert obs.policy_reference_observed == ref_seen
    assert obs.acknowledgement_observed == (ack or None)


def test_a_provider_without_an_acknowledgement_requirement_is_marked_so() -> None:
    fake = EmbeddingModelSpec("fake", "fake-embedding", "fake-1", 1024)
    obs = svc.policy_observation(SimpleNamespace(), fake, asserted_actor=None)
    assert obs.acknowledgement_required is False and obs.acknowledgement_matches_required is False


def test_audit_fields_never_contain_credentials_content_or_acceptance_claims() -> None:
    obs = svc.policy_observation(_settings_obj(), SPEC, asserted_actor="Dana")
    blob = json.dumps(svc._policy_fields(obs))
    assert SECRET not in blob and "api_key" not in blob.lower()
    flat = svc._policy_fields(obs)
    assert not any(
        value is True for key, value in flat.items() if key.endswith("_verified")
    ), "no verification claim may be true"
    assert "accepted_by_owner" not in flat and "approved" not in blob.lower()


# --- enqueue: same transaction as the job ---


def _patch_enqueue(
    monkeypatch: pytest.MonkeyPatch, *, log: list[str], existing: Any = None, eligible: bool = True
) -> dict[str, Any]:
    captured: dict[str, Any] = {}
    document_id, extraction_id = uuid.uuid4(), uuid.uuid4()
    facts = EligibilityFacts(
        document_found=True,
        is_archived=not eligible,
        confidentiality_classification="standard",
        payload_checksum=_SHA,
        active_approval_checksum=_SHA,
        extraction_found=True,
        extraction_belongs_to_document=True,
        extraction_is_current=True,
        extraction_status="completed",
    )
    monkeypatch.setattr(
        svc.document_extraction_repository,
        "get_extraction",
        lambda db, _id: SimpleNamespace(research_document_id=document_id),
    )
    monkeypatch.setattr(
        svc.public_document_approval_repository, "load_eligibility_facts", lambda db, **_: facts
    )
    monkeypatch.setattr(
        svc.document_embedding_job_repository, "get_active_job", lambda db, **_: existing
    )

    def create_pending(db: Any, data: Any) -> Any:
        log.append("create_job")
        captured["job"] = SimpleNamespace(id=uuid.uuid4())
        return captured["job"]

    monkeypatch.setattr(svc.document_embedding_job_repository, "create_pending", create_pending)

    def create_event(db: Any, event: Any) -> None:
        log.append("create_audit")
        captured["event"] = event
        if captured.get("audit_error"):
            raise captured["audit_error"]

    monkeypatch.setattr(svc.audit_repository, "create_event", create_event)
    captured["extraction_id"] = extraction_id
    return captured


def test_enqueue_writes_the_audit_event_after_the_job_with_policy_facts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    log: list[str] = []
    captured = _patch_enqueue(monkeypatch, log=log)
    obs = svc.policy_observation(_settings_obj(), SPEC, asserted_actor="Dana")
    job = svc.enqueue_embedding(
        Db(log),  # type: ignore[arg-type]
        document_extraction_id=captured["extraction_id"],
        spec=SPEC,
        requested_by="Dana",
        policy=obs,
    )
    assert log == ["create_job", "create_audit"] and job is captured["job"]
    event = captured["event"]
    assert event.event_type == AuditEventType.DOCUMENT_EMBEDDING_REQUESTED.value
    assert event.entity_id == job.id and event.user_id == "Dana"
    state = event.after_state
    assert state["provider"] == "openai" and state["nexus_config_version"] == "alias-test"
    assert state["dimension"] == 1024 and state["policy_acknowledgement_matches_required"] is True
    assert state["policy_reference_observed"] == "adr-021-accepted-sha256-test"
    assert SECRET not in json.dumps(state)


def test_an_audit_failure_propagates_so_the_caller_can_roll_the_job_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    log: list[str] = []
    captured = _patch_enqueue(monkeypatch, log=log)
    captured["audit_error"] = RuntimeError("audit write failed")
    with pytest.raises(RuntimeError):
        svc.enqueue_embedding(
            Db(log),  # type: ignore[arg-type]
            document_extraction_id=captured["extraction_id"],
            spec=SPEC,
            requested_by=None,
            policy=svc.policy_observation(_settings_obj(), SPEC, asserted_actor=None),
        )
    assert "commit" not in log  # the service never commits; nothing is made durable


def test_the_worker_rolls_back_and_exits_nonzero_when_enqueue_or_its_audit_fails() -> None:
    class _Failing(_FakeService):
        def enqueue_embedding(self, db: Any, **_: Any) -> Any:
            raise RuntimeError("driver text with SECRET detail")

    db = _FakeDb()
    from app.scripts.run_document_embedding_worker import run

    code = run(
        ["--max-tokens", "100", "--enqueue-extraction", str(uuid.UUID(int=9))],
        settings=_settings(),
        session_factory=lambda: db,
        service=_Failing(),
    )
    assert code == 1 and db.rollbacks == 1 and db.commits == 0 and db.closed


def test_an_existing_active_job_is_returned_without_a_second_job_or_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    log: list[str] = []
    existing = SimpleNamespace(id=uuid.uuid4())
    captured = _patch_enqueue(monkeypatch, log=log, existing=existing)
    job = svc.enqueue_embedding(
        Db(log),  # type: ignore[arg-type]
        document_extraction_id=captured["extraction_id"],
        spec=SPEC,
        requested_by=None,
    )
    assert job is existing and log == []


def test_an_ineligible_document_creates_neither_a_job_nor_an_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    log: list[str] = []
    captured = _patch_enqueue(monkeypatch, log=log, eligible=False)
    with pytest.raises(svc.DocumentNotEligibleError):
        svc.enqueue_embedding(
            Db(log),  # type: ignore[arg-type]
            document_extraction_id=captured["extraction_id"],
            spec=SPEC,
            requested_by=None,
        )
    assert log == []


# --- worker start: durable before any provider work ---


def test_worker_start_event_is_committed_not_just_flushed(monkeypatch: pytest.MonkeyPatch) -> None:
    log: list[str] = []
    events: list[Any] = []
    monkeypatch.setattr(
        svc.audit_repository, "create_event", lambda db, e: (log.append("audit"), events.append(e))
    )
    run_id = uuid.uuid4()
    svc.record_worker_started(
        Db(log),  # type: ignore[arg-type]
        run_id=run_id,
        policy=svc.policy_observation(_settings_obj(), SPEC, asserted_actor="Dana"),
        limits={"max_tokens": 100, "max_jobs": 1},
    )
    assert log == ["audit", "commit"]  # the commit follows the write
    event = events[0]
    assert event.event_type == AuditEventType.EMBEDDING_WORKER_STARTED.value
    assert event.entity_table == "embedding_worker_run" and event.entity_id is None
    assert event.user_id == "Dana"
    assert event.after_state["run_id"] == str(run_id)
    assert event.after_state["limits"] == {"max_tokens": 100, "max_jobs": 1}
    assert event.after_state["identity_verified"] is False
    assert SECRET not in json.dumps(event.after_state)


def test_worker_start_failures_roll_back_and_raise_so_no_provider_work_follows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for fail_write in (True, False):
        log: list[str] = []

        def create_event(db: Any, e: Any, *, fail: bool = fail_write) -> None:
            if fail:
                raise RuntimeError("write failed")

        monkeypatch.setattr(svc.audit_repository, "create_event", create_event)
        with pytest.raises(RuntimeError):
            svc.record_worker_started(
                Db(log, fail_commit=not fail_write),  # type: ignore[arg-type]
                run_id=uuid.uuid4(),
                policy=svc.policy_observation(_settings_obj(), SPEC, asserted_actor=None),
                limits={},
            )
        assert log[-1] == "rollback"


# --- holds, release ---


def _held_domain(**overrides: Any) -> SimpleNamespace:
    values: dict[str, Any] = {
        "id": uuid.uuid4(),
        "status": EmbeddingJobStatus.HELD,
        "embedding_provider": "openai",
        "embedding_model": "text-embedding-3-large",
        "attempt_count": 1,
        "hold_reason": "provider_credentials_or_quota",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_a_hold_and_its_audit_event_commit_together_with_a_reason_code_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    log: list[str] = []
    events: list[Any] = []
    held = _held_domain()
    monkeypatch.setattr(
        svc.document_embedding_job_repository,
        "hold_job",
        lambda db, job_id, **kw: (log.append("hold"), held)[1],
    )
    monkeypatch.setattr(
        svc.audit_repository, "create_event", lambda db, e: (log.append("audit"), events.append(e))
    )
    store = svc.SqlJobStore(Db(log))  # type: ignore[arg-type]
    store.hold(
        JobContext(held.id, uuid.uuid4(), uuid.uuid4(), "T", 1),
        reason="provider_credentials_or_quota",
        provider_wide=True,
        error_classification="deterministic",
        error_message="EmbeddingAuthError (deterministic)",
        refund_attempt=True,
    )
    assert log == ["rollback", "hold", "audit", "commit"]
    state = events[0].after_state
    assert events[0].event_type == AuditEventType.EMBEDDING_JOB_HELD.value
    assert (
        state["hold_reason"] == "provider_credentials_or_quota" and state["provider_wide"] is True
    )
    assert "error_message" not in state  # no provider response text is audited


def test_a_failed_hold_audit_rolls_the_hold_back_and_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    log: list[str] = []
    monkeypatch.setattr(
        svc.document_embedding_job_repository, "hold_job", lambda db, job_id, **kw: _held_domain()
    )

    def boom(db: Any, event: Any) -> None:
        raise RuntimeError("audit down")

    monkeypatch.setattr(svc.audit_repository, "create_event", boom)
    store = svc.SqlJobStore(Db(log))  # type: ignore[arg-type]
    with pytest.raises(RuntimeError):
        store.hold(
            JobContext(uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), "T", 1),
            reason="r",
            provider_wide=True,
            error_classification=None,
            error_message=None,
            refund_attempt=False,
        )
    assert log[-1] == "rollback" and "commit" not in log


def test_requeue_passes_the_schedule_to_the_repository(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}
    monkeypatch.setattr(
        svc.document_embedding_job_repository,
        "requeue_pending",
        lambda db, job_id, **kw: seen.update(kw),
    )
    later = NOW + timedelta(seconds=90)
    svc.SqlJobStore(Db()).requeue(  # type: ignore[arg-type]
        JobContext(uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), "T", 1),
        error_classification="transient",
        error_message="m",
        note="n",
        refund_attempt=False,
        retry_not_before=later,
        provider_wide=True,
    )
    assert seen["retry_not_before"] == later and seen["provider_wide"] is True


def test_release_records_an_unverified_actor_and_keeps_the_audit_in_the_same_transaction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    log: list[str] = []
    events: list[Any] = []
    held, released = _held_domain(), _held_domain(status=EmbeddingJobStatus.PENDING)
    monkeypatch.setattr(svc.document_embedding_job_repository, "get_job", lambda db, jid: held)
    monkeypatch.setattr(
        svc.document_embedding_job_repository,
        "release_held",
        lambda db, jid, released_by: (log.append("release"), released)[1],
    )
    monkeypatch.setattr(
        svc.audit_repository, "create_event", lambda db, e: (log.append("audit"), events.append(e))
    )
    job = svc.release_held_job(Db(log), job_id=held.id, released_by="Dana")  # type: ignore[arg-type]
    assert job is released and log == ["release", "audit"]  # caller commits both together
    event = events[0]
    assert event.event_type == AuditEventType.EMBEDDING_JOB_RELEASED.value
    assert event.before_state["hold_reason"] == "provider_credentials_or_quota"
    assert event.after_state["identity_verified"] is False
    assert event.after_state["asserted_actor"] == "Dana"


def test_releasing_a_job_that_is_not_held_writes_no_event(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[Any] = []
    monkeypatch.setattr(svc.document_embedding_job_repository, "get_job", lambda db, jid: None)

    def not_held(db: Any, jid: Any, released_by: str) -> Any:
        raise JobNotHeldError("not held")

    monkeypatch.setattr(svc.document_embedding_job_repository, "release_held", not_held)
    monkeypatch.setattr(svc.audit_repository, "create_event", lambda db, e: events.append(e))
    with pytest.raises(JobNotHeldError):
        svc.release_held_job(Db(), job_id=uuid.uuid4(), released_by="Dana")  # type: ignore[arg-type]
    assert events == []


# --- stale recovery and claim wiring ---


def test_stale_recovery_uses_the_injected_clock_and_delays_the_recovered_job(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, Any] = {}
    log: list[str] = []
    monkeypatch.setattr(
        svc.document_embedding_job_repository,
        "reclaim_stale_processing",
        lambda db, **kw: (seen.update(kw), [])[1],
    )
    svc.reclaim_stale_jobs(
        Db(log),  # type: ignore[arg-type]
        stale_after_seconds=900,
        max_attempts=3,
        clock=lambda: NOW,
        jitter=lambda: 0.0,
    )
    assert seen["stale_after"] == NOW - timedelta(seconds=900)
    assert seen["retry_not_before"] == NOW + timedelta(seconds=30)  # never immediate
    assert log == ["commit"]


def test_the_claim_is_scoped_to_the_workers_provider_model_version_and_clock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, Any] = {}
    log: list[str] = []
    monkeypatch.setattr(
        svc.document_embedding_job_repository,
        "claim_next_pending",
        lambda db, **kw: (seen.update(kw), None)[1],
    )
    result = svc.process_next_job(
        Db(log),  # type: ignore[arg-type]
        provider=SimpleNamespace(),  # type: ignore[arg-type]
        spec=SPEC,
        budget=SimpleNamespace(),  # type: ignore[arg-type]
        config=ProcessorConfig(batch_size=2, max_attempts=3, clock=lambda: NOW),
    )
    assert result is None and log == ["commit"]
    assert seen == {
        "provider": "openai",
        "model": "text-embedding-3-large",
        "model_version": "alias-test",
        "now": NOW,
    }


# --- release script ---


class _ReleaseService:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def release_held_job(self, db: Any, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return SimpleNamespace(id=kwargs["job_id"], status=SimpleNamespace(value="pending"))


class _ReleaseRepo:
    JobNotHeldError = JobNotHeldError

    def __init__(self, held: list[Any] | None = None) -> None:
        self.held = held or []

    def list_held(self, db: Any) -> list[Any]:
        return self.held


def _release(
    argv: list[str], service: _ReleaseService | None = None, repo: _ReleaseRepo | None = None
):
    db = _FakeDb()
    code = release_script.run(
        argv,
        session_factory=lambda: db,
        service=service or _ReleaseService(),
        repository=repo or _ReleaseRepo(),
    )
    return code, db


def test_release_requires_an_explicit_confirm_a_job_id_and_a_name() -> None:
    job = str(uuid.UUID(int=3))
    for argv in (
        ["--job-id", job, "--released-by", "Dana"],  # no --confirm
        ["--confirm", "--released-by", "Dana"],  # no job id
        ["--job-id", job, "--confirm"],  # no name
        ["--job-id", job, "--confirm", "--released-by", "   "],  # blank name
    ):
        service = _ReleaseService()
        code, db = _release(argv, service)
        assert code == 1 and service.calls == [] and db.commits == 0


def test_release_commits_once_sends_no_request_and_trims_the_asserted_name(
    capsys: pytest.CaptureFixture[str],
) -> None:
    service = _ReleaseService()
    job = uuid.UUID(int=3)
    code, db = _release(["--job-id", str(job), "--confirm", "--released-by", "  Dana  "], service)
    assert code == 0 and db.commits == 1 and db.closed
    assert service.calls == [{"job_id": job, "released_by": "Dana"}]
    assert "no provider request was made" in capsys.readouterr().out


def test_release_of_a_job_that_is_not_held_is_refused_and_rolled_back() -> None:
    service = _ReleaseService(error=JobNotHeldError("x"))
    code, db = _release(
        ["--job-id", str(uuid.UUID(int=3)), "--confirm", "--released-by", "D"], service
    )
    assert code == 1 and db.rollbacks == 1 and db.commits == 0


def test_a_failed_audit_means_the_job_is_not_released() -> None:
    service = _ReleaseService(error=RuntimeError("audit down; secret detail"))
    code, db = _release(
        ["--job-id", str(uuid.UUID(int=3)), "--confirm", "--released-by", "D"], service
    )
    assert code == 1 and db.rollbacks == 1 and db.commits == 0


def test_list_prints_ids_and_reason_codes_only(capsys: pytest.CaptureFixture[str]) -> None:
    job = SimpleNamespace(
        id=uuid.UUID(int=4),
        hold_reason="provider_configuration",
        provider_wide=True,
        held_at=NOW,
        attempt_count=1,
        error_message="SHOULD-NOT-APPEAR",
    )
    code, db = _release(["--list"], repo=_ReleaseRepo([job]))
    out = capsys.readouterr().out
    assert code == 0 and db.commits == 0 and "provider_configuration" in out
    assert "SHOULD-NOT-APPEAR" not in out


def test_release_without_a_database_configuration_fails_closed() -> None:
    assert release_script.run(["--list"], session_factory=None) == 1


# --- factory: the policy reference is required for a real provider ---


@pytest.mark.parametrize("reference", [None, "", "   "])
def test_a_real_provider_needs_a_policy_reference(reference: str | None) -> None:
    cfg = SimpleNamespace(
        environment="production",
        embeddings_enabled=True,
        embedding_provider="openai",
        embedding_model_id="text-embedding-3-large",
        embedding_model_version="alias-test",
        embedding_dimension=1024,
        embedding_batch_size=8,
        embedding_api_key=SECRET,
        embedding_request_timeout_seconds=30.0,
        embedding_external_policy_approval=OPENAI_POLICY_APPROVAL_VALUE,
        embedding_policy_reference=reference,
    )
    with pytest.raises(EmbeddingConfigurationError, match="EMBEDDING_POLICY_REFERENCE") as info:
        get_embedding_provider(cfg)  # type: ignore[arg-type]
    assert SECRET not in str(info.value)
