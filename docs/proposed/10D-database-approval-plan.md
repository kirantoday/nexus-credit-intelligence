# Milestone 10D — Future approval plan: shared-database migration and integration tests

Status: **proposal for a separate approval.** 10D.2 applied no migration, ran
no integration test, and connected to no database. This plan exists so that
approval can be requested deliberately, with eyes open to the shared-database
risk. It does not authorize anything by itself.

## Why this needs its own approval

`CLAUDE.md` forbids local PostgreSQL and `ADR-013` forbids a separate Supabase
project, so the only place the new SQL (partial unique indexes, the guarded
upsert, `vector_dims` CHECK, `FOR UPDATE SKIP LOCKED`) can ever be proven is the
**shared Supabase `nexus` schema**, which also serves another application. A
rolled-back test transaction does not make that risk-free: it takes locks,
counts toward connection limits, and any applied migration is permanent until
downgraded.

## Preconditions (all required)

1. Provider/model decision approved, so the vector width in draft `0022` is
   confirmed or corrected (a width cannot be changed in place afterwards).
2. Read-only live checks completed and reviewed: installed `pgvector` version;
   `nexus.alembic_version` is at `0020` (and `0019`/`0020` really applied); row
   counts for `research_document`, `document_extraction`, `document_chunk`;
   count of `restricted` documents; no other Nexus object named like the new
   tables; `nexus` not exposed through PostgREST.
3. A recent restorable backup or Supabase point-in-time-recovery window confirmed
   by the person who owns the project, with the other application's owner told.
4. Python 3.12 environment working and the full local suite green.
5. Drafts re-validated offline (see below).

## Offline validation before any execution

- `tests/unit/test_embedding_migration_drafts.py` (structure, chain, schema,
  extension-safety, vector-width parity).
- Generate the SQL without a connection and review it by eye:
  `alembic upgrade 0020:0022 --sql` using a throwaway scripts dir that copies
  `alembic/versions` plus the two drafts (so the real `versions/` is never
  touched), and `alembic downgrade 0022:0020 --sql`. Alembic's offline mode only
  needs a URL string for the dialect (`alembic/env.py:78-92`). **Not yet run:**
  it needs the project's dependencies, which require Python 3.12.
- Confirm the downgrade SQL contains only `DROP INDEX`/`DROP TABLE` for the
  four new Nexus tables (`public_document_approval`, `document_embedding_job`,
  `document_chunk_embedding`, `embedding_call_log`) and their indexes, never an
  extension or schema statement.

## Execution plan (when approved)

1. Move the two drafts into `alembic/versions/` in a **local, uncommitted** branch
   state; run the offline checks again.
2. `alembic upgrade 0021` then verify, then `alembic upgrade 0022` then verify
   (one revision at a time). Verification is read-only: the four tables exist in
   `nexus`, constraints/indexes present, nothing created in `public`, extension
   version unchanged.
3. Run **only** the gated suite:
   `NEXUS_ALLOW_EMBEDDING_DB_TESTS=1 pytest tests/integration/test_document_embedding_repositories.py`.
   It exercises: one active approval per document and revocation; eligibility
   facts through reclassification, supersession, archive and revocation; the
   one-active-job-per-target index and retained history; claim/attempt/refund;
   the guarded upsert (insert, no-op, in-place replace) and rejection of a
   wrong-width vector; ledger totals with unknown costs.
4. Decide, with the results, whether to keep the migrations applied (they are
   additive and idle while `EMBEDDINGS_ENABLED=false`) or roll back.

## Rollback

- `alembic downgrade 0020` drops only the four new Nexus tables and their
  indexes. It never touches the `vector` extension, the `nexus` schema, or any
  existing table. Because no embedding data exists before a pilot run, the
  downgrade loses nothing; after a pilot run it deletes the embeddings and the
  allowlist rows (re-creatable, but record the audit_event rows first — they are
  in an existing table and are not removed).
- If a migration fails midway: Alembic runs each revision in a transaction on
  PostgreSQL, so a failed revision leaves no partial objects; verify with the
  read-only checks before retrying.

## Schema ownership and coordination

- All objects live in `nexus`; ownership follows the existing migration role.
- No change to `public`, to the other application's tables, or to extensions.
- Do not run during the nightly discovery window (10 PM America/New_York) or
  an active extraction run, to avoid contention on `document_extraction`.

## What 10D.2 explicitly did not do

No `alembic upgrade`, no `alembic` command of any kind, no `psql`, no SQL
against Supabase, no test run against `DATABASE_URL`.
