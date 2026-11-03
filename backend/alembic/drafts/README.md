# Draft migrations (NOT applied, NOT discovered by Alembic)

Files here are **drafts** for Milestone 10D. Alembic only scans
`alembic/versions/`, so nothing in this directory can be applied by
`alembic upgrade head` — on purpose. This project applies migrations to the
shared Supabase project from a developer machine (KI-001), so a draft left
in `versions/` could be applied by an unrelated `upgrade head`.

| Draft | State |
|---|---|
| `0021_public_document_approval.py` | Schema settled. Ready to move once the database approval plan is approved. |
| `0022_document_embeddings.py` | **DRAFT pending provider/model approval.** The `vector(N)` width (`EMBEDDING_DIMENSION`) is a pilot value that must be confirmed against the chosen model before this is moved. |

To promote a draft (only after the separate database approval — see
`docs/proposed/10D-database-approval-plan.md`): move the file into
`alembic/versions/`, keep its revision ids, re-run the offline checks, then
follow the approved execution plan. Never edit the `vector` extension.

`tests/unit/test_embedding_migration_drafts.py` guards this directory: it
fails if a draft appears in `versions/`, if the revision chain breaks, if a
draft touches an extension or `public`, or if the draft's vector width
disagrees with `app.embeddings.dimensions.EMBEDDING_COLUMN_DIMENSION`.

## Draft 0023 (scheduling) — added 2026-11-02

| Draft | State |
|---|---|
| `0023_embedding_job_scheduling.py` | Draft, **NOT applied**, not discovered. Adds `retry_not_before`, `provider_wide`, hold/release columns and the `held` status to `nexus.document_embedding_job`; revises the status CHECK and the "one active job" partial index. Chained on `0022`. |

Local evidence cannot show whether `0022` was ever applied in any environment,
so `0023` is a **separate revision on top of `0022`** rather than an edit to it.
If the owner later confirms `0022` was never applied anywhere, folding `0023`
into it is a separate decision. When separately approved, 0021, 0022 and 0023
move to `alembic/versions/` together, in that order, and are applied one at a
time. The downgrade of `0023` aborts if any `held` job exists and discards hold
history otherwise; rollback and lock behavior are unverified until tested.
`tests/unit/test_embedding_scheduling_migration_draft.py` guards it.
