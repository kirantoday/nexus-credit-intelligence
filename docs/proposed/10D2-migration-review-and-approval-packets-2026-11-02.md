# Milestone 10D.2 — Migration review and approval packets (2026-11-02)

Status: **proposal / review only.** Nothing here authorizes a database
connection, migration, integration run, paid API call, commit, push or
deploy. Companion file:
`10D2-offline-sql-0020-to-0022-REVIEW-ONLY-NOT-APPLIED-2026-11-02.sql`.

Evidence labels: **[source]** read from local files; **[offline-SQL]** from
Alembic `--sql` output; **[unit]** from a local unit test; **[NOT VERIFIED]**
requires a live database or an external decision.

## 1. Local validation (this session, Python 3.12.10, no network/DB)

| Check | Result |
|---|---|
| `mypy app` | Success, 237 files (was 1 error) |
| `ruff check .` | All checks passed |
| `black --check .` | 361 files unchanged |
| `pytest tests/unit` | 389 passed, 0 failed, 0 skipped, 1 third-party warning |
| Focused: extractor + chunker tests | 13 passed |

mypy fix: removed `# type: ignore[import-untyped]` from
`backend/app/extraction/pymupdf4llm_extractor.py:25`. Cause: `pymupdf4llm`
1.28.2 ships no `py.typed`, but `[tool.mypy] ignore_missing_imports = true`
already makes the import `Any`, so the ignore was redundant and
`warn_unused_ignores = true` flagged it. Comment-only; no runtime change.

## 2. Migration review (0021, 0022)

### Findings

| # | Finding | Evidence |
|---|---|---|
| M1 | Chain is linear: `0019 -> 0020 -> 0021 -> 0022`, single head `0022` in the scratch script dir; drafts are outside `alembic/versions/` so `upgrade head` cannot see them. | [source][offline-SQL] |
| M2 | Every object is `nexus.`-qualified; no statement touches `public`, extensions, or the other application. Downgrade drops only the 4 new tables and their indexes. | [offline-SQL] |
| M3 | Migration SQL matches the SQLAlchemy models exactly for all 4 tables: columns, nullability, CHECK names, index names. | compared programmatically |
| M4 | `vector(1024)` and `vector_dims(...)` are **unqualified**. Migration 0001 creates the extension `WITH SCHEMA public`, and `env.py` deliberately sets no `search_path`. If the live `vector` extension is in `extensions` (Supabase dashboard default) and the role's search_path lacks it, 0022 fails at `CREATE TABLE` (transactional, no partial objects). | [source]; live location [NOT VERIFIED] |
| M5 | New tables add FKs to `research_document`, `document_extraction`, `document_chunk`, `provenance`. FK creation takes a brief SHARE ROW EXCLUSIVE lock on each referenced table (blocks writes for the DDL's duration; new tables are empty so it is short). Avoid the extraction worker / nightly window. No table rewrite, no existing-data backfill. | PostgreSQL behavior; [NOT VERIFIED] live |
| M6 | Upgrades are additive and fully reversible while tables are empty. Downgrade is **destructive**: `0022 -> 0021` deletes all embeddings, jobs and the call-cost ledger; `0021 -> 0020` deletes the allowlist (what was approved, by whom). Restore from backup, not downgrade, once real data exists. | [offline-SQL] |
| M7 | No ANN index, so no pgvector index-build lock/memory risk. Extension version assumptions: `vector` type + `vector_dims()` only; installed version [NOT VERIFIED]. | [source] |
| M8 | No `ON DELETE` actions: deleting a `research_document`/`document_chunk` with embeddings will be refused by FK. Intentional (no silent cascades) but note for any cleanup tooling. | [source] |
| M9 | Whether 0021/0022 were applied elsewhere: local evidence says **no** (no commit or branch containing them, drafts README says not applied, 0 stashes). This is not proof; live `nexus.alembic_version` is [NOT VERIFIED]. A read-only check precedes any approval. Never rewrite an applied migration. | [source] |

No migration, env.py, model, schema or setting was modified.

### Offline SQL status

Generated and inspected: `upgrade 0020:0022 --sql` and
`downgrade 0022:0020 --sql`, explicit ranges, scratch script dir containing
copies of all 20 versions + the 2 drafts, wrapper that raises on any socket
connect, inert dialect URL `postgresql://offline@invalid.invalid/offline`
(env var, process-local), no `.env`/credentials present. Exit 0 both ways.
Limitation: this proves SQL shape only. It does not prove pgvector presence,
search_path resolution, permissions, lock behavior, or rollback on live data.

### Dimension decision (1024) — UNRESOLVED, blocks 0022

Trace: `alembic/drafts/0022` (`EMBEDDING_DIMENSION = 1024`, hard-coded on
purpose) = `app/embeddings/dimensions.py:36 EMBEDDING_COLUMN_DIMENSION` =
`.env.example` comment = `FakeEmbeddingProvider` default = test fixtures; a
unit test pins draft-vs-code agreement. `EMBEDDING_DIMENSION` setting is
`None` by default. `EmbeddingModelSpec` rejects any model whose dimension is
not 1024.

Local evidence supporting 1024: only ADR-021's statement that "both leading
candidate vendors support it natively". **No vendor or model is named
anywhere locally**, `pricing.py` has no real entries, and no real provider
adapter exists. So 1024 is an assumption, not a verified property of any
chosen model. Undecided: vendor, model id/version, native/truncated width,
price. A fixed-width column cannot change in place; a wrong guess costs a new
column/table plus re-embedding. **Required before 0022 approval:** written
vendor+model decision with its documented output dimension.

## 3. Security plan (existing endpoints) — recommendations only

### Confirmed findings (verified in code)

| ID | Finding | Evidence |
|---|---|---|
| S1 | No authentication or authorization dependency exists anywhere in `app/api`. All routes are anonymous; `CORSMiddleware` (`main.py:49`) restricts browsers only, not API callers. | grep of `app/api` for auth dependencies: none |
| S2 | `GET /api/document-extractions/{id}/chunks` and `/chunks/search` return full chunk text for any extraction id after an existence check only. No archived/superseded/restricted/allowlist check. | `document_extraction.py:99-125` |
| S3 | `GET /api/research-documents/{id}/download` issues a 300 s signed URL for the whole stored PDF after an existence check only; includes restricted and archived documents. | `research_documents.py:161`, `research_document_service.py:84` |
| S4 | The allowlist's source of truth is `nexus.public_document_approval`, written only by `app.scripts.approve_public_document` (requires `--confirm`, `--approved-by` free text). Eligibility is recomputed from live parent rows. Enforcement exists at **enqueue** and **before each provider call** (`document_embedding_service.py:116, 226`). Retrieval-time and citation-time enforcement are **not built** (10D.3). Fail-closed: `evaluate_eligibility` denies unless all facts hold [unit]. | source |
| S5 | The fake embedding provider is refused unless `ENVIRONMENT` is `local`/`test`; embeddings default off. | `factory.py:30,63` |

### Assumptions / open questions (not findings)

- Whether the deployed API is reachable by untrusted callers (public Railway URL?) — assumed yes; confirm.
- Whether the backend DB role bypasses RLS (service-role/owner) — assumed yes; `nexus` is documented as not exposed to PostgREST; confirm in Supabase settings.
- `approved_by` is unauthenticated free text; acceptable only while the operator script is the sole writer.
- Tenant concept: none exists (single-tenant). "Cross-tenant" risk reduces to cross-document.

### Remediations (all need approval; none implemented)

| # | Remediation | Components | Acceptance criteria | Approval |
|---|---|---|---|---|
| R-A | Chunk routes: allowlist-only; non-approved => 404 unless server-side `ENVIRONMENT in {local,test}` or default-off `CHUNK_INSPECTION_ENABLED` | `document_extraction.py`, a shared live-join predicate, `ChunkInspectorPage` 404 state | The 10 regression cases in `10D-endpoint-remediation-plan.md` §2 pass; predicate/`evaluate_eligibility` parity test; client cannot enable inspection | 10D.3 scoped approval (breaks deployed Chunk Inspector for internal docs) |
| R-B | Download route: product decision A/B/C | `research_documents.py` | Decision recorded; if B, same mechanism as R-A | Product owner before enabling public retrieval |
| R-C | Retrieval + citation-resolution enforcement points | 10D.3 retrieval service | Denied for every ineligible state; negative tests first | 10D.3 |
| R-D | Never log chunk text/vectors/signed URLs; keep `SUPABASE_SERVICE_KEY` backend-only | logging config review | grep-based test that logs/responses contain none | with R-A |
| R-E | Real authentication | out of 10D (TD-002/025/027) | n/a | separate milestone |

Negative tests to write first (10D.3): archived, superseded extraction,
restricted, reclassified-after-approval, never approved, revoked, checksum
mismatch, extraction of a different document, non-completed extraction,
plus a positive control.

## 4. Shared Supabase approval packet — NO DATABASE ACTION FOLLOWS FROM THIS

- **Target:** the existing shared Supabase project, schema `nexus` only
  (ADR-013). Project ref/environment: **[NOT VERIFIED]** — not read from
  credentials. Operator must name it explicitly in the approval.
- **Scope/order:** (1) read-only preflight; (2) `0021` alone, verify; (3)
  `0022` alone, verify — only after the dimension decision. SQL artifact: the
  REVIEW-ONLY file. Drafts move to `alembic/versions/` only in a local,
  uncommitted state at execution time.
- **Prerequisites:** vendor/model/dimension approved; Python 3.12 suite green
  (done); read-only preflight results reviewed: `pgvector` installed version
  and **schema of the `vector` extension (M4)**, `nexus.alembic_version = 0020`,
  no existing objects with the new names, migration role's privileges, `nexus`
  not exposed via PostgREST, row counts of the 4 referenced tables.
- **Backup/restore (proposed, none taken, none assumed to exist):** owner =
  Supabase project owner. Confirm PITR is enabled with a restore point within
  minutes of the change, or take a logical `pg_dump --schema=nexus` of the
  `nexus` schema to encrypted storage, retained ≥ 30 days. Restore
  verification: restore into a scratch project, compare `nexus` table row
  counts and `alembic_version`. The other application's owner is told in
  advance.
- **Coordination/timing:** outside the 10 PM America/New_York discovery job
  and any active extraction; announce a window; set `lock_timeout` ~5 s and
  `statement_timeout` ~60 s for the migration session so it fails fast
  instead of queueing behind writers.
- **Abort thresholds:** any non-empty diff outside `nexus`; any error; lock
  wait over the limit; verification mismatch => stop, do not retry blindly.
- **Rollback:** failed revision rolls back its own transaction. After success
  with no real data: `alembic downgrade` is safe. After data exists:
  downgrade deletes embeddings/allowlist — restore from backup or forward-fix
  instead.
- **Success checks (read-only):** 4 tables in `nexus`, constraints/indexes
  present, nothing new in `public`, extension version unchanged,
  `alembic_version = 0022`.
- **Go / No-go:** GO only if every prerequisite is checked, the dimension is
  approved in writing, backup is confirmed by the owner, and the user approves
  that named environment and operations. NO-GO on any [NOT VERIFIED] item
  remaining open.
- **Responsible operator:** user (project owner) for approval and backup;
  Claude Code only for the specifically approved commands.

**Approval checklist:** ☐ project/environment named ☐ dimension+model decided
☐ preflight approved (read-only) ☐ backup owner/method confirmed ☐
window/other-app owner informed ☐ 0021 approved ☐ 0022 approved (separate)
☐ rollback/abort rules accepted.

## 5. Git checkpoint proposal — AWAITING APPROVAL (nothing staged or run)

HEAD `b2a9f31` on `main`; nothing staged; At proposal time: 6 modified +
49 untracked files incl. this packet and the SQL artifact (lists below). Secret scan (patterns for keys, JWTs,
connection strings with passwords, private keys) over all candidates: no
matches. No `.env`, `.venv`, caches or build output among candidates
(`backend/.venv` is git-ignored).

Provenance of changes: everything is from earlier sessions (10D.2
implementation and the 2026-11-01 validation fixes) **except** this session's:
`pymupdf4llm_extractor.py` (1-line comment removal) and the 2 new artifacts
below. Git will warn about LF→CRLF on that file (autocrlf); harmless.

Proposed allowlist (explicit paths, no `git add .`/`-A`):
- Modified (6): `.env.example`, `backend/app/config.py`,
  `backend/app/core/types.py`, `backend/app/models/__init__.py`,
  `backend/pyproject.toml`, `backend/app/extraction/pymupdf4llm_extractor.py`.
- New, 10D.2 code: `backend/app/db/vector_type.py`; four
  `backend/app/domain/{document_chunk_embedding,document_embedding_job,embedding_call_log,public_document_approval}.py`;
  four matching `backend/app/models/*.py`; four matching
  `backend/app/repositories/*.py`; `backend/app/embeddings/` (excluding
  `__pycache__`); `backend/app/retrieval/` (excl. `__pycache__`);
  `backend/app/scripts/{approve_public_document,run_document_embedding_worker}.py`;
  `backend/app/services/document_embedding_service.py`.
- New, drafts: `backend/alembic/drafts/` (3 files, inert by design).
- New, tests: 2 files in `backend/tests/integration/`, 10 in
  `backend/tests/unit/` (as listed in `git status`).
- New, docs: `docs/proposed/` (4 earlier files + 2 artifacts from this session).
- Stage by exact filename from `git ls-files -o --exclude-standard` plus
  `git add -- <6 modified>`; exclude `__pycache__` (already ignored).

Branch: `milestone-10d2-document-embeddings` (local). Message:
`Milestone 10D.2: document embedding foundation (draft migrations, disabled by default)`
with the repo's required `Co-Authored-By` trailer. Local actions only:
`git switch -c <branch>`, `git add -- <paths>`, `git diff --cached --stat`
review, `git commit`. No push.

Caveats before committing: CLAUDE.md requires `PLAN.md`/`BUILD_LOG.md`
updates at milestone completion — **not proposed here** because 10D.2 is not
closed (see §7); this would be a work-in-progress checkpoint, which the
approval must acknowledge. Clean-tree rule is satisfied by committing all
files above; nothing is excluded other than ignored caches.

**Request:** approve this checkpoint (branch name, paths, message) — or amend.

## 6. Integration-testing authorization request (separate from §4/§5)

- **Preferred target:** a disposable isolated Postgres+pgvector environment
  (not provisioned; conflicts with CLAUDE.md "no local PostgreSQL" and ADR-013
  "no second Supabase project", so using one needs an explicit exception).
  Fallback: the shared `nexus` schema under §4's controls. Owner: user.
- **Scope:** `NEXUS_ALLOW_EMBEDDING_DB_TESTS=1 pytest tests/integration/test_document_embedding_repositories.py`
  — fixtures use synthetic issuers/documents; expected writes: rows in the 4
  new tables plus parents (`issuer`, `research_document`, `document_extraction`,
  `document_chunk`, `provenance`) per test; cleanup via per-test rollback
  (verify the guard in `embedding_db_guard.py` before approval). Providers:
  fake only; no paid API.
- **Must prove live:** migration ordering 0020→0022; vector width and
  `CAST(:embedding AS vector)` writes; wrong-width rejection;
  `vector_dims` CHECK; partial unique indexes; `FOR UPDATE SKIP LOCKED` claim;
  guarded upsert; eligibility facts through reclassify/supersede/archive/revoke.
  Endpoint allowlist behavior belongs to 10D.3 tests.
- **Evidence retained:** pytest output, pre/post table lists, `alembic_version`.
  Pass = all pass + no objects outside `nexus`. Abort = any error outside test
  tables, lock wait, or leftover rows.
- **Separate gates (each approved independently):** G1 environment access
  (read-only preflight), G2 migration application (0021, then 0022),
  G3 integration execution, G4 Git checkpoint (§5). None implies another.

## 7. Before 10D.2 can close and 10D.3 can begin

Open: vendor/model/dimension decision; read-only live preflight (esp. `vector`
schema, applied revision, pgvector version); backup confirmation; approved
migration application; passing integration run; resolution of the 0021
allowlist/`approved_by` trust model; download-route decision (R-B); user
sign-off on R-A scope; docs updates (`PLAN.md`, `BUILD_LOG.md`, ADR-021
acceptance). Unit tests passing is necessary, not sufficient, for either
milestone.
