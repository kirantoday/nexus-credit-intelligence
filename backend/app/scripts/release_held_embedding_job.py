"""Operator release of a held embedding job (Milestone 10D.2 scheduling).

    python -m app.scripts.release_held_embedding_job --list
    python -m app.scripts.release_held_embedding_job --job-id <uuid> \\
        --released-by <name> --confirm

A job is *held* when credentials, quota/spend limits, provider configuration,
a provider/spec mismatch or a vendor delay longer than the automatic limit
make automatic retries pointless or unsafe. A held job is never claimed and is
never touched by stale recovery. This script is the only way back to `pending`.

It sends **no provider request** and builds no provider. It requires an
explicit `--confirm`, records an `embedding_job_released` audit event in the
same transaction as the release, and keeps the job's lifetime evidence
(attempt count, error fields, hold reason and time). `--released-by` is a
free-text name that is **not verified** (there is no authentication), and is
recorded as such. Releasing does not approve anything: the worker still
applies its policy, ownership, eligibility and budget checks.

A provider-wide hold closes the provider/model queue; the queue reopens only
when every provider-wide held job has been released.

Output is ids, reason codes and counts only.
"""

from __future__ import annotations

import argparse
import sys
import uuid
from collections.abc import Callable
from typing import Any


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="release_held_embedding_job",
        description="List or release held document embedding jobs (explicit, no provider call).",
    )
    parser.add_argument("--list", action="store_true", help="List held jobs and exit.")
    parser.add_argument("--job-id", type=uuid.UUID, default=None)
    parser.add_argument("--released-by", default=None)
    parser.add_argument("--confirm", action="store_true")
    return parser


def run(
    argv: list[str],
    *,
    session_factory: Callable[[], Any] | None,
    service: Any | None = None,
    repository: Any | None = None,
) -> int:
    args = build_parser().parse_args(argv)
    if session_factory is None:
        print("ERROR: DATABASE_URL is not configured.", file=sys.stderr)
        return 1

    import importlib

    svc = service or importlib.import_module("app.services.document_embedding_service")
    repo = repository or importlib.import_module(
        "app.repositories.document_embedding_job_repository"
    )

    if args.list:
        db = session_factory()
        try:
            jobs = repo.list_held(db)
        finally:
            db.close()
        if not jobs:
            print("No held embedding jobs.")
        for job in jobs:
            print(
                f"held job {job.id} reason={job.hold_reason} provider_wide={job.provider_wide} "
                f"held_at={job.held_at.isoformat() if job.held_at else None} "
                f"attempts={job.attempt_count}"
            )
        return 0

    if args.job_id is None or not args.released_by or not args.released_by.strip():
        print("ERROR: --job-id and a non-empty --released-by are required.", file=sys.stderr)
        return 1
    if not args.confirm:
        print("ERROR: --confirm is required to release a held job.", file=sys.stderr)
        return 1

    db = session_factory()
    try:
        try:
            job = svc.release_held_job(db, job_id=args.job_id, released_by=args.released_by.strip())
            db.commit()
        except repo.JobNotHeldError:
            db.rollback()
            print("Refused: the job is not held.")
            return 1
        except Exception:  # noqa: BLE001 - nothing is released if the audit write fails
            db.rollback()
            print("ERROR: release failed; the job was not released.", file=sys.stderr)
            return 1
        print(f"Released job {job.id}; status={job.status.value} (no provider request was made).")
        return 0
    finally:
        db.close()


def main(argv: list[str] | None = None) -> int:
    from app.db.session import SessionLocal

    return run(sys.argv[1:] if argv is None else argv, session_factory=SessionLocal)


if __name__ == "__main__":
    sys.exit(main())
