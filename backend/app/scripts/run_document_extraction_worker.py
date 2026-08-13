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
"""

from __future__ import annotations

import sys

from app.config import get_settings
from app.db.session import SessionLocal
from app.services import document_extraction_service
from app.storage.factory import StorageConfigurationError, get_storage_client


def main(argv: list[str] | None = None) -> int:
    del argv  # no CLI arguments — this is a scheduler entry point, not an operator tool
    settings = get_settings()

    if SessionLocal is None:
        print("ERROR: DATABASE_URL is not configured.", file=sys.stderr)
        return 1

    try:
        storage_client = get_storage_client(settings)
    except StorageConfigurationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    db = SessionLocal()
    try:
        stale = document_extraction_service.reclaim_stale_jobs(db)
        if stale:
            print(
                f"Reclaimed {len(stale)} stale processing extraction(s): "
                f"{[str(r.id) for r in stale]}"
            )

        result = document_extraction_service.process_one(db, storage_client)
        if result is None:
            print("No pending document_extraction — nothing to do.")
            return 0

        print(
            f"Processed document_extraction {result.id}: status={result.status.value} "
            f"attempt={result.attempt_count} page_count={result.page_count} "
            f"chunk_count={result.chunk_count} table_count={result.table_count} "
            f"extractor={result.extractor_provider}/{result.extractor_version} "
            f"chunking_strategy={result.chunking_strategy_version} "
            f"is_current={result.is_current}"
        )
        if result.status.value in ("failed", "needs_ocr"):
            print(
                f"  error_classification={result.error_classification} "
                f"error_message={result.error_message}"
            )
        return 0
    finally:
        db.close()
        storage_client.close()


if __name__ == "__main__":
    sys.exit(main())
