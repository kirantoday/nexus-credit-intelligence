"""Document embedding worker — manually invoked, bounded entry point
(Milestone 10D.2, ADR-021).

    python -m app.scripts.run_document_embedding_worker --max-tokens 50000
    python -m app.scripts.run_document_embedding_worker --enqueue-extraction <uuid> \\
        --requested-by <name>

There is no scheduler and no Railway service for this worker: a cron
service, schedule, or deployment is a separate approval. Each invocation:

1. Refuses to run unless `EMBEDDINGS_ENABLED` is true (default false), the
   model/dimension contract is satisfied, and an **explicit token budget**
   was passed. A cost ceiling is accepted only when the model's price is
   known, because an unenforceable ceiling is not a ceiling.
2. For a real provider, takes the **exclusive worker lock** (one active worker
   per provider/model; see `app.embeddings.worker_lock`). A second worker exits
   with status 3 without any provider request. The fake provider (local/test
   only) needs no lock.
3. Writes and **commits** the `embedding_worker_started` audit event before any
   claim or provider request; if that fails, nothing is sent.
4. Reclaims any `processing` job stuck past the stale threshold (delayed by
   backoff; at-least-once, so a duplicate request is possible).
5. Claims and processes at most `--max-jobs` *due* jobs (default 1), stopping
   early when credentials, quota, configuration, a long vendor delay or a rate
   limit make continuing pointless. Such conditions put the job on an
   **operator hold**; release it with `release_held_embedding_job`.

This worker never imports or calls the extraction worker, and extraction
success never depends on it.

**Exit codes** follow the extraction worker's discipline (2026-08-13
incident): `0` for every completed run, including jobs that ended `failed`,
`blocked_ineligible`, or were requeued — those are classified, persisted
outcomes, not script failures. `1` is reserved for configuration problems
(feature disabled, no database, bad budget, unbuildable provider, bad
credentials) or an unhandled crash. `2` is argparse's usage error.

Output is ids, counts, and reason codes only — never document text, titles,
queries, or vendor messages.
"""

from __future__ import annotations

import argparse
import importlib
import sys
import uuid
from collections.abc import Callable
from typing import Any

# Notes from `app.embeddings.processor` that mean "the environment is
# misconfigured", which warrants a non-zero exit, as opposed to a rate limit
# or budget stop, which is an expected reason to end a run early.
_CONFIGURATION_STOP_NOTES = frozenset(
    {"provider_unavailable", "provider_spec_mismatch", "worker_ownership_lost"}
)

# Exit status when another worker already holds the exclusive lock. The run
# ends before any provider request (argparse's usage error is 2).
EXIT_LOCK_HELD = 3


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_document_embedding_worker",
        description="Process pending document embedding jobs (bounded, manual).",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        required=True,
        help="Hard token budget for this run (required; there is no default).",
    )
    parser.add_argument("--max-cost-usd", type=float, default=None)
    parser.add_argument("--max-requests", type=int, default=None)
    parser.add_argument("--max-jobs", type=int, default=1)
    parser.add_argument(
        "--enqueue-extraction",
        type=uuid.UUID,
        default=None,
        help="Enqueue (if eligible) a job for this extraction id, then exit.",
    )
    parser.add_argument("--requested-by", default=None)
    return parser


def run(
    argv: list[str],
    *,
    settings: Any,
    session_factory: Callable[[], Any] | None,
    provider_factory: Callable[[Any], Any] | None = None,
    service: Any | None = None,
    lock_factory: Callable[[Any, Any], Any] | None = None,
) -> int:
    args = build_parser().parse_args(argv)

    if not settings.embeddings_enabled:
        print("ERROR: EMBEDDINGS_ENABLED is false; embedding is disabled.", file=sys.stderr)
        return 1
    if session_factory is None:
        print("ERROR: DATABASE_URL is not configured.", file=sys.stderr)
        return 1
    if args.max_jobs < 1:
        print("ERROR: --max-jobs must be at least 1.", file=sys.stderr)
        return 1

    from app.embeddings.budget import EmbeddingRunBudget
    from app.embeddings.errors import EmbeddingConfigurationError
    from app.embeddings.factory import get_embedding_provider
    from app.embeddings.pricing import lookup_pricing
    from app.embeddings.processor import ProcessorConfig

    try:
        provider, spec = (provider_factory or get_embedding_provider)(settings)
    except EmbeddingConfigurationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if (
        args.max_cost_usd is not None
        and lookup_pricing(provider=spec.provider, model_id=spec.model_id) is None
    ):
        print(
            "ERROR: --max-cost-usd cannot be enforced because this model's price is unknown.",
            file=sys.stderr,
        )
        return 1
    try:
        budget = EmbeddingRunBudget(
            max_tokens=args.max_tokens,
            max_cost_usd=args.max_cost_usd,
            max_requests=args.max_requests,
        )
    except ValueError as exc:
        print(f"ERROR: invalid budget: {exc}", file=sys.stderr)
        return 1

    svc = (
        service
        if service is not None
        else importlib.import_module("app.services.document_embedding_service")
    )

    config = ProcessorConfig(
        batch_size=settings.embedding_batch_size,
        max_attempts=settings.embedding_job_max_attempts,
    )
    policy = svc.policy_observation(settings, spec, asserted_actor=args.requested_by)

    db = session_factory()
    lock: Any | None = None
    try:
        if args.enqueue_extraction is not None:
            try:
                job = svc.enqueue_embedding(
                    db,
                    document_extraction_id=args.enqueue_extraction,
                    spec=spec,
                    requested_by=args.requested_by,
                    policy=policy,
                )
            except svc.DocumentNotEligibleError as exc:
                db.rollback()
                print(f"Refused to enqueue: {exc.reason.value}")
                return 0
            except svc.DocumentExtractionNotFoundError:
                db.rollback()
                print("Refused to enqueue: extraction not found")
                return 0
            except Exception:  # noqa: BLE001 - e.g. the audit write failed: nothing is queued
                db.rollback()
                print("ERROR: enqueue failed; nothing was queued.", file=sys.stderr)
                return 1
            try:
                db.commit()
            except Exception:  # noqa: BLE001
                db.rollback()
                print("ERROR: enqueue could not be committed; nothing was queued.", file=sys.stderr)
                return 1
            print(f"Enqueued document_embedding_job {job.id} status={job.status.value}")
            return 0

        from app.embeddings.errors import EmbeddingOwnershipLostError
        from app.embeddings.worker_lock import OwnershipGuardedProvider

        if spec.provider != "fake":
            if lock_factory is None:
                print(
                    "ERROR: the exclusive worker lock is required for a real provider "
                    "and is not available; no provider request was made.",
                    file=sys.stderr,
                )
                return 1
            try:
                lock = lock_factory(settings, spec)
                acquired = lock.acquire()
            except EmbeddingConfigurationError as exc:
                print(f"ERROR: {exc}", file=sys.stderr)
                return 1
            except Exception:  # noqa: BLE001 - a database/driver error: message withheld
                print(
                    "ERROR: could not take the exclusive worker lock; no provider request "
                    "was made.",
                    file=sys.stderr,
                )
                return 1
            if not acquired:
                print(
                    "Another embedding worker holds the exclusive lock for this provider and "
                    "model; exiting without any provider request."
                )
                return EXIT_LOCK_HELD
            provider = OwnershipGuardedProvider(provider, lock)

        run_id = uuid.uuid4()
        try:
            svc.record_worker_started(
                db,
                run_id=run_id,
                policy=policy,
                limits={
                    "max_tokens": args.max_tokens,
                    "max_cost_usd": args.max_cost_usd,
                    "max_requests": args.max_requests,
                    "max_jobs": args.max_jobs,
                    "batch_size": settings.embedding_batch_size,
                    "max_attempts": settings.embedding_job_max_attempts,
                },
            )
        except Exception:  # noqa: BLE001 - audit failure means no provider work at all
            print(
                "ERROR: the worker-start audit event could not be committed; no provider "
                "request was made.",
                file=sys.stderr,
            )
            return 1
        print(f"Worker run {run_id} started (audit event committed).")

        stale = svc.reclaim_stale_jobs(
            db,
            stale_after_seconds=settings.embedding_stale_processing_after_seconds,
            max_attempts=settings.embedding_job_max_attempts,
        )
        if stale:
            print(f"Reclaimed {len(stale)} stale processing job(s): {[str(j.id) for j in stale]}")

        exit_code = 0
        for _ in range(args.max_jobs):
            if lock is not None:
                try:
                    lock.assert_held()
                except EmbeddingOwnershipLostError:
                    print("ERROR: worker lock ownership lost; stopping before any claim.")
                    exit_code = 1
                    break
            result = svc.process_next_job(
                db, provider=provider, spec=spec, budget=budget, config=config
            )
            if result is None:
                print("No due pending document_embedding_job - nothing to do.")
                break
            print(
                f"Processed job: outcome={result.outcome.value} embedded={result.embedded} "
                f"replaced={result.replaced} unchanged={result.unchanged} "
                f"tokens={result.tokens_used} note={result.note}"
            )
            if result.retry_not_before is not None:
                print(f"Next attempt is not before {result.retry_not_before.isoformat()}.")
            if result.retry_after_seconds is not None:
                print(f"The vendor asked for a {result.retry_after_seconds:g}s wait.")
            if result.outcome.value == "held":
                print(
                    "Job placed on operator hold; the provider queue stays closed until it is "
                    "released with release_held_embedding_job."
                )
                exit_code = 1
            if result.abort_run:
                if result.note in _CONFIGURATION_STOP_NOTES:
                    exit_code = 1
                break
        print(f"Run budget: tokens_used={budget.tokens_used} requests={budget.requests_made}")
        return exit_code
    finally:
        db.close()
        # A real provider owns an HTTP client; the fake has nothing to close.
        close_provider = getattr(provider, "close", None)
        if callable(close_provider):
            close_provider()
        if lock is not None:
            lock.release()


def main(argv: list[str] | None = None) -> int:
    from app.config import get_settings
    from app.db.session import SessionLocal
    from app.embeddings.worker_lock import build_postgres_worker_lock

    return run(
        sys.argv[1:] if argv is None else argv,
        settings=get_settings(),
        session_factory=SessionLocal,
        lock_factory=build_postgres_worker_lock,
    )


if __name__ == "__main__":
    sys.exit(main())
