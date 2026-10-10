"""Document Intelligence extraction worker — standalone entry point
(Milestone 10C).

    python -m app.scripts.run_document_extraction_worker

Railway Cron invokes this every 5 minutes (Railway's shortest supported
cron interval, live-verified against Railway's own docs before choosing
it — see `backend/railway.extraction-worker.toml`). Each invocation:

1. Reclaims any `processing` extraction stuck past the stale-job
   threshold (a worker that died mid-attempt, e.g. a Railway redeploy).
2. Claims and fully processes at most **one** pending extraction
   (bounded memory/behavior, per the milestone brief — this is
   deliberately not a drain-the-whole-queue loop).
3. Exits.

**Exit code discipline, directly informed by the 2026-08-13 incident**:
this script exits `0` whenever it completed its own work without an
unhandled exception — including when the extraction it processed ended in
`failed`/`needs_ocr`. Those are normal, already-classified, already-
persisted outcomes (exactly what `document_extraction.status` exists to
record), not script failures — conflating "one document's outcome was
'failed'" with "this cron invocation crashed" is precisely the false-
alarm pattern that incident's root cause report (`BUILD_LOG.md`,
2026-08-13) flagged as worth avoiding here. A non-zero exit is reserved
for a genuine, unclassified crash of the worker process itself (e.g. no
DATABASE_URL configured, an unhandled exception escaping
`document_extraction_service.process_one`).

**Observability (Milestone 10C recovery)**: this entry point logs through
the standard `logging` module (stdout, line-buffered) *before* importing
anything heavy — `app.services.document_extraction_service` pulls in
PyMuPDF4LLM, which is a large import — so a process that dies, hangs, or
is killed during import still leaves a "worker_started" line behind. Every
later stage (config validated, DB connected, stale-job reclaim, claim or
"no eligible job", result, duration) logs one structured line. Logs carry
only identifiers, counts, durations and error categories — never document
text, credentials, or connection strings. A `SIGTERM` handler logs the
signal, so a platform-initiated kill is distinguishable from a silent
`SIGKILL`/OOM (which leaves `worker_started` with no terminal line).
"""

from __future__ import annotations

import faulthandler
import logging
import os
import signal
import sys
import time
from types import FrameType

logger = logging.getLogger("nexus.document_extraction_worker")

# Exit/outcome categories — a fixed vocabulary so a log search for
# `outcome=` is enough to triage a run.
OUTCOME_NO_JOB = "no_eligible_job"
OUTCOME_PROCESSED = "processed"
OUTCOME_CONFIG_ERROR = "config_error"
OUTCOME_DB_ERROR = "db_connection_error"
OUTCOME_UNHANDLED = "unhandled_error"


def _log_sigterm(signum: int, frame: FrameType | None) -> None:
    del frame
    logger.warning("worker_signal signal=%s outcome=terminated_by_platform", signum)
    logging.shutdown()
    os._exit(128 + signum)  # noqa: SLF001 - exit immediately, as the default handler would


def _configure_process() -> None:
    # Line-buffered stdout so each log line reaches Railway immediately,
    # even if the process is killed moments later.
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(line_buffering=True)
    faulthandler.enable()  # native crash (segfault in a C extension) -> stderr traceback
    from app.logging_config import configure_logging

    configure_logging()
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _log_sigterm)


def main(argv: list[str] | None = None) -> int:
    del argv  # no CLI arguments — this is a scheduler entry point, not an operator tool
    started = time.monotonic()
    _configure_process()
    logger.info(
        "worker_started pid=%s python=%s environment=%s",
        os.getpid(),
        sys.version.split()[0],
        os.environ.get("ENVIRONMENT", "unset"),
    )

    try:
        return _run(started)
    except Exception:
        logger.exception(
            "worker_finished outcome=%s elapsed_s=%.1f",
            OUTCOME_UNHANDLED,
            time.monotonic() - started,
        )
        return 1


def _run(started: float) -> int:
    from sqlalchemy import text

    from app.config import get_settings
    from app.db.session import SessionLocal
    from app.storage.factory import StorageConfigurationError, get_storage_client

    settings = get_settings()

    if SessionLocal is None:
        logger.error(
            "worker_finished outcome=%s detail=DATABASE_URL_not_configured elapsed_s=%.1f",
            OUTCOME_CONFIG_ERROR,
            time.monotonic() - started,
        )
        return 1

    try:
        storage_client = get_storage_client(settings)
    except StorageConfigurationError as exc:
        # The exception message names missing variables (never their values).
        logger.error(
            "worker_finished outcome=%s detail=%s elapsed_s=%.1f",
            OUTCOME_CONFIG_ERROR,
            exc,
            time.monotonic() - started,
        )
        return 1
    logger.info(
        "config_validated bucket=%s extractor=pymupdf4llm log_level=%s",
        settings.supabase_storage_bucket,
        settings.log_level,
    )

    # Imported only now, after "worker_started"/"config_validated" are
    # already in the log — see the module docstring.
    import_started = time.monotonic()
    from app.services import document_extraction_service

    logger.info("extraction_modules_imported import_s=%.1f", time.monotonic() - import_started)

    db = SessionLocal()
    try:
        try:
            db.execute(text("SELECT 1"))
            db.rollback()
        except Exception:
            logger.exception(
                "worker_finished outcome=%s elapsed_s=%.1f",
                OUTCOME_DB_ERROR,
                time.monotonic() - started,
            )
            return 1
        logger.info("database_connected")

        stale = document_extraction_service.reclaim_stale_jobs(db)
        logger.info("stale_jobs_reclaimed count=%d ids=%s", len(stale), [str(r.id) for r in stale])

        result = document_extraction_service.process_one(db, storage_client)
        elapsed = time.monotonic() - started
        if result is None:
            logger.info("worker_finished outcome=%s elapsed_s=%.1f", OUTCOME_NO_JOB, elapsed)
            return 0

        logger.info(
            "worker_finished outcome=%s extraction_id=%s research_document_id=%s status=%s "
            "attempt=%d page_count=%s chunk_count=%s table_count=%s extractor=%s/%s "
            "chunking_strategy=%s is_current=%s error_classification=%s elapsed_s=%.1f",
            OUTCOME_PROCESSED,
            result.id,
            result.research_document_id,
            result.status.value,
            result.attempt_count,
            result.page_count,
            result.chunk_count,
            result.table_count,
            result.extractor_provider,
            result.extractor_version,
            result.chunking_strategy_version,
            result.is_current,
            result.error_classification,
            elapsed,
        )
        if result.status.value in ("failed", "needs_ocr"):
            # error_message is "ExceptionType: message" from our own
            # extractor/storage layers — never document content.
            logger.warning(
                "extraction_not_completed extraction_id=%s status=%s error_classification=%s "
                "error_message=%s",
                result.id,
                result.status.value,
                result.error_classification,
                result.error_message,
            )
        return 0
    finally:
        db.close()
        storage_client.close()


if __name__ == "__main__":
    sys.exit(main())
