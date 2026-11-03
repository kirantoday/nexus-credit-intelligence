# Milestone 10D.2 — Durable scheduling, policy audit events and GitHub push readiness (2026-11-02)

Status: **implemented and validated offline only.** Embeddings stay disabled;
no provider request, key, database, migration (rendering or application),
integration test, network access, Git write, push or deployment occurred. Live
use remains blocked (§9). 10D.2 stays open; ADR-021 stays `Proposed`; drafts
0021/0022 are untouched, and the new scheduling schema is a separate unapplied
draft, `0023`.

Baseline [read-only Git]: branch `milestone-10d2-document-embeddings`, HEAD
`18435631d9785c682a5b055b18ae53181975af17`, clean tree, nothing staged, no
stashes, `main` at `b2a9f31`. Everything below is uncommitted work from this
session.

## 1. Design: states and transitions (written before the edits)

Job states: `pending`, `processing`, `completed`, `failed`, `blocked_ineligible`
and the new **`held`** (operator hold). Columns added to
`nexus.document_embedding_job`: `retry_not_before` (UTC-aware, only while
`pending`), `provider_wide` (a delay or hold applies to the whole provider/model
queue), `hold_reason`, `held_at`, `released_at`, `released_by`.

| From | Event | To | Attempt | `retry_not_before` | Scope | Other |
|---|---|---|---|---|---|---|
| `pending` | claim (worker holds the lock; job is due, provider queue not blocked) | `processing` | **+1 consumed** | cleared | cleared | `started_at` = injected now |
| `processing` | all batches persisted | `completed` | kept | cleared | cleared | |
| `processing` | transient error (5xx, timeout, network, persistence), attempts < cap | `pending` | kept (consumed) | now + backoff + jitter | **this job only** | one HTTP attempt per call |
| `processing` | **rate limit**, valid or missing vendor delay ≤ 6 h, attempts < cap | `pending` | kept (consumed) | now + **max(vendor delay, backoff)** (never earlier) | **provider-wide** | run stops |
| `processing` | rate limit, vendor delay **> 6 h** | `held` (`retry_after_exceeds_automatic_limit`) | kept (consumed) | none | provider-wide | not truncated, not scheduled |
| `processing` | credentials / quota / spend (`EmbeddingAuthError`) | `held` (`provider_credentials_or_quota`) | **refunded** | none | provider-wide | run stops |
| `processing` | configuration (404, redirect, spec mismatch) | `held` (`provider_configuration` / `provider_spec_mismatch`) | **refunded** | none | provider-wide | run stops |
| `processing` | deterministic input / response / dimension error, or attempts exhausted | `failed` | kept | cleared | cleared | no retry loop |
| `processing` | ineligible (archived, revoked, …) | `blocked_ineligible` | kept | cleared | cleared | never retried |
| `processing` | budget stop | `pending` | **refunded** | none | none | |
| `processing` | worker ownership lost (before sending) | `pending` | **refunded** | none | none | run stops; nothing was sent |
| `processing` | stale (worker died), attempts < cap | `pending` | kept | now + backoff(1) | none | at-least-once; may be billed twice |
| `processing` | stale, attempts spent | `failed` | kept | cleared | cleared | |
| `held` | stale recovery | **unchanged** | | | | stale recovery selects `processing` only |
| `held` | **explicit release** (`release_held_embedding_job --confirm`) | `pending` | **kept** | cleared | cleared | `released_at/by` set; hold history and errors **kept** |

**Attempts.** Consumed at claim. Refunded only where the stop is not the job's
fault and the failed request (if any) is separately in `embedding_call_log`:
budget, credentials/quota/configuration, ownership loss. A rate limit is *not*
refunded, so the cap bounds rate-limited requests per job. A pre-request
failure (local input rejection) is a terminal `failed`, makes no request and is
not counted against the run budget.

**Delay timing.** `due` means `retry_not_before IS NULL OR retry_not_before <= now`
(equality is eligible). All timestamps are UTC-aware; a naive timestamp is
rejected. Vendor delays: numeric seconds or an HTTP-date resolved against an
injected clock; missing, malformed, negative or non-finite values fall back to
backoff (30 s × 2^(attempt−1), cap 1 h, +0–25 % jitter that can only lengthen);
a past HTTP-date means "retry now" but backoff still applies; implausibly
distant values are bounded at 10 years and then fall in the hold branch.

**Rate-limit scope: provider/account, not per job.** A rate-limited requeue
marks `provider_wide`; while that job is pending with a future time, or any
provider-wide job is `held`, **no job for the same provider and model is
claimable** (SQL `NOT EXISTS`, mirrored by `scheduling.claimable_jobs`). The
queue reopens when the delay elapses, or when every provider-wide held job has
been released. Other providers/models are unaffected. Per-job transient errors
delay only that job.

**Concurrency model: one active embedding worker per provider and model,
enforced by a database-backed exclusive lock** (§3), not a flag or a
documentation statement.

## 2. Findings and fixes

| # | Finding (before) | Fix |
|---|---|---|
| S1 | Retry delays were not persisted; any worker could reclaim a rate-limited job at once | `retry_not_before` + `provider_wide`; claim filters on both (`repository._claim_statement`) |
| S2 | Auth/quota/config failures returned the job to claimable `pending` with a refunded attempt (infinite retry across invocations) | New `held` state; never claimable, never touched by stale recovery; explicit release |
| S3 | The claim took *any* pending job, regardless of the worker's provider/model/version | Claim is scoped to the worker's provider, model and version |
| S4 | `held`-style jobs would not have owned the "one active job" slot, so re-enqueueing could bypass a hold | `held` counts as active in the partial unique index and `get_active_job` |
| S5 | No concurrency control at all across workers | PostgreSQL session-level advisory lock on a dedicated connection |
| S6 | No policy/ownership audit | `embedding_worker_started`, extended `document_embedding_requested`, `embedding_job_held`, `embedding_job_released` |
| S7 | Stale recovery re-queued immediately | Reclaimed job is delayed by backoff |
| S8 | `Retry-After` HTTP-date unsupported; numeric capped at 3600 s in the adapter | Single parser (`scheduling.parse_retry_after`), uncapped; policy lives in the scheduler |

Code: `app/embeddings/scheduling.py` (new, pure), `app/embeddings/worker_lock.py`
(new), `app/embeddings/processor.py`, `app/embeddings/errors.py`,
`app/embeddings/openai_provider.py`, `app/embeddings/factory.py`,
`app/repositories/document_embedding_job_repository.py`, `app/models/…`,
`app/domain/…`, `app/core/types.py`, `app/services/document_embedding_service.py`,
`app/scripts/run_document_embedding_worker.py`,
`app/scripts/release_held_embedding_job.py` (new), `app/config.py`, `.env.example`.

## 3. Worker ownership (selected first-release model)

- `pg_try_advisory_lock(key)` where the key is a stable 64-bit hash of
  provider+model, on a **dedicated connection** from a `NullPool` engine built
  from `DIRECT_DATABASE_URL` (a session-mode endpoint; a transaction-pooling
  endpoint cannot hold a session lock). The connection is AUTOCOMMIT, so the
  lock is not inside a transaction and **no row lock or open transaction is held
  over a provider call** (the claim commits first).
- Required for every real provider; the fake provider (local/test only) needs
  none. A real provider with no lock factory fails closed.
- **Second worker:** acquisition returns false → exit status **3**, no audit
  event, no claim, **zero provider requests**.
- **Ownership check:** immediately before every provider request, via a
  provider wrapper (`OwnershipGuardedProvider`), plus once before each claim.
  If the check fails the request is not sent; the processor requeues the job
  (attempt refunded, no accounting) and the run ends with status 1.
- **Crash:** the lock is the database session's, so PostgreSQL drops it when the
  connection or process dies; the abandoned `processing` job is recovered by the
  stale rule with a delay. **Lost connection:** the liveness query fails and
  ownership is treated as lost. **DB error on acquire:** fail closed, no request.
- **Cleanup** (normal exit and every error path): `pg_advisory_unlock`, close
  the connection, dispose the engine, close the provider's HTTP client, close
  the session.
- **Unproven:** actual lock exclusivity, release on crash, behavior behind a
  pooler or after failover, and whether a liveness query detects every loss.
  Unit tests use connection doubles (§7).

## 4. Migration strategy (known and unknown)

Known [local]: `alembic/versions/` ends at `0020`; 0021/0022 exist only in
`alembic/drafts/` (not discoverable); no commit or branch contains 0021/0022 in
`versions/`; reports say "unapplied". **Unknown:** whether 0022 was ever applied
in any environment (no live check is authorized). Therefore **0021 and 0022 are
untouched** and the scheduling schema is a new **inert draft
`0023_embedding_job_scheduling.py`**, `down_revision = "0022"`, `nexus`-qualified,
touching only `document_embedding_job`: six `ADD COLUMN`s, a replaced status
CHECK (adds `held`), three new CHECKs, a replaced "one active" partial unique
index (adds `held`) and a partial index for the blocker lookup. Existing rows
need no backfill (new columns NULL / `provider_wide=false` satisfy every CHECK).
**Downgrade** discards hold and delay history and **aborts if any `held` row
exists** (it will not turn holds into claimable work). Lock durations, the
constant-default column add, CHECK validation time and rollback are
**unverified** until a read-only preflight and a tested environment.
**Activation order (separately approved):** move 0021, 0022, 0023 into `versions/`
together, in order, then apply one at a time. If the owner later confirms 0022
was never applied anywhere, folding 0023 into it is a separate decision. The
provisional vector-schema/`search_path` question (unqualified `vector`,
`vector_dims`, runtime `CAST … AS vector`) is **unchanged and still open**;
no vector width, model, ANN index or retrieval was touched.

## 5. Policy audit events (existing `audit_event`; no new audit schema)

| Event | When | Atomicity / ordering |
|---|---|---|
| `document_embedding_requested` (extended) | enqueue | Same transaction as job creation. An audit failure propagates; the worker rolls back and exits 1, so no orphaned queued job. |
| `embedding_worker_started` | after the lock is held and prerequisites pass, **before any claim or provider request** | Written and **`commit()`ed** before work; a commit/write failure rolls back, exits 1, **zero provider calls**, lock released. |
| `embedding_job_held` | hold transition | Same transaction as the hold; reason **code** only. |
| `embedding_job_released` | release | Same transaction as the release (the script commits both); asserted actor flagged unverified. |

Fields: provider, model, Nexus configuration version, dimension, whether an
acknowledgement is required, the **observed** acknowledgement string, whether it
**matches** the required string, the **observed** policy reference (identifier or
hash), run id, limits. Always present: `policy_acknowledgement_source =
"environment_variable"`, `policy_reference_verified=false`,
`owner_acceptance_verified=false`, `asserted_actor`, `identity_verified=false`.
Never present: keys, document or chunk text, vectors, signed URLs, response
bodies or error text. **An environment string is not owner acceptance, an
identifier is not a verified record, a typed name is not an identity, and an
audit event grants nothing.** For a real provider `EMBEDDING_POLICY_REFERENCE`
is now also required (fail-closed), so a bare flag is not enough; no policy
reference is fabricated and **none exists today, so live activation stays
blocked.** Events from the fake provider in local/test are appropriate and grant
nothing. Missing or mismatching settings are recorded as such; the factory still
refuses a real provider without a match.

## 6. Operator release

`python -m app.scripts.release_held_embedding_job --list` and
`--job-id <uuid> --released-by <name> --confirm`. Requires `--confirm`, a job
id and a non-blank name; builds no provider; sends no request; writes the
`embedding_job_released` event in the same transaction; refuses a job that is not
held; keeps attempt count, error fields, `hold_reason`, `held_at`; sets
`released_at/by`. A provider-wide hold reopens the queue only when **every**
provider-wide held job is released. Releasing approves nothing: policy,
ownership, eligibility and budget checks still apply.

## 7. Validation (offline; `backend/.venv`, Python 3.12.10)

Interpreter confirmed; `ENVIRONMENT=test`, `EMBEDDINGS_ENABLED=false` set
process-locally; no `.env`; `tests/integration` not collected. Doubles for HTTP,
sessions, repositories, connections, clock and jitter; nothing slept; the
diagnostic network tripwire (socket connects, `getaddrinfo`, real httpx
transport raise) covers Python-level attempts in the test process only.

| Command (from `backend`) | Result |
|---|---|
| `python -m pytest tests/unit` | **720 passed**, 0 failed, 0 skipped, 1 third-party warning; exit 0 |
| `python -m ruff check .` | All checks passed; exit 0 |
| `python -m black --check .` | 373 files unchanged; exit 0 |
| `python -m mypy app` | Success, 241 source files; exit 0 |

Run once after the final edit; the historical 588 result was not reused. New
tests: scheduling rules (boundary, timezones, Retry-After forms, backoff, plans,
claim specification), repository behavior with a session double and offline SQL
compilation of the claim, lock and ownership control flow, audit events and
release, failure dispositions and accounting evidence, and the 0023 source.
Existing tests that asserted the superseded "requeue claimable" behavior were
rewritten (not weakened) and marked as superseded. Comment-only: some divider
lines in test files were shortened for the line-length rule.

**What these do not prove (all UNVERIFIED until integration):** the SQL claim
and `FOR UPDATE SKIP LOCKED` under concurrency; the NOT EXISTS blocker; advisory
lock exclusivity, crash release, pooler and failover behavior; real commit
durability and rollback; restart behavior; 0023 against a real schema.

### Future integration-test matrix (synthetic data, approved isolated target)

| # | Guarantee | Test |
|---|---|---|
| I1 | Delay respected at the boundary | job with `retry_not_before = T`: not claimable at `T−ε`, claimable at `T` |
| I2 | Provider-wide delay/hold | one delayed provider-wide job blocks other jobs of the same provider/model; not another provider; reopens at time / after release |
| I3 | Concurrent claim | N claimers, M due jobs: each job claimed once; delayed jobs never claimed |
| I4 | Advisory lock exclusivity | second session's try-lock false; released when first connection is killed (`pg_terminate_backend`) |
| I5 | Lock via the intended endpoint | fails or is shown unsupported through a transaction pooler; works on the direct URL |
| I6 | Stale recovery | processing job aged out → pending with delay; held job untouched; spent attempts → failed |
| I7 | Hold / release | hold survives restart; claimed never; release → pending; evidence preserved |
| I8 | Re-enqueue cannot bypass a hold | unique index blocks a second job while held |
| I9 | Audit atomicity | enqueue with failing audit leaves no job; worker-start event visible to another session before any claim |
| I10 | Migration 0023 | upgrade on a 0022 schema with sample rows; CHECKs hold; downgrade aborts with a held row; lock durations measured |
| I11 | Attempt cap across invocations | rate-limited job fails after `max_attempts`; quota hold does not consume |
| I12 | Transaction scope | no open transaction / row lock during a (mocked) provider call |

## 8. Limitations (honest)

- Per-run counters and estimates remain **not** a cross-run monetary ceiling;
  provider-side spend limits must be verified by the account owner.
- At-least-once: a crashed worker's batch may be re-sent and billed twice.
- `held` conditions are operator-resolved; the queue stays closed until then
  (by design). No alerting exists.
- The liveness check detects a dead connection, not every possible loss.
- Rate-limit scope is per provider+model queue, not literally per account: two
  models on one account are separate queues, and `fake`/other providers are not
  coordinated. First-release use is one real provider/model.
- 1024-dimension quality is still unevaluated; vector `search_path`/cast items
  stay open; security routes unchanged.

## 9. Live-use blockers (all remain; none granted)

Accepted policy record (ADR-021 acceptance) plus `EMBEDDING_POLICY_REFERENCE`,
account, dedicated key and provider spend limits; an approved isolated
integration environment and the §7 matrix passing; read-only preflight
(revision state, extension schema/version, roles/`search_path`, lock privileges,
pooler vs direct endpoint, backup); migrations 0021→0022→0023 applied one at a
time; a separately authorized synthetic smoke call; the security scope for
anonymous process enqueue, restricted metadata and adjacent mutation routes.

## 10. GitHub private feature-branch push readiness (read-only, local evidence)

**Remote and destination.** `origin` = `https://github.com/kirantoday/nexus-credit-intelligence.git`
(fetch and push; no credentials in the URL). No upstream is configured for the
feature branch; `main` tracks `origin/main`. Intended destination ref:
`refs/heads/milestone-10d2-document-embeddings` on `origin`. The remote account
`kirantoday` differs from the local Git identity, so **push access, credentials
and that this repository is the intended private one are owner checks** (local
files cannot show repository privacy, organization settings, webhooks or hosting
integrations).

**Branch relationship.** HEAD is 3 commits ahead of local `main` (`b2a9f31`,
equal to the local `origin/main`, which may be stale). Accumulated change vs
`main`: 62 files, +10,307/−5 (before this increment), no binaries, largest file
~49 KB, all under `.env.example`, `backend/`, `docs/proposed/`. No merge, rebase
or history rewrite is involved; a normal fast-forward-from-nothing push of a new
ref.

**Automation (local files only).** `.github/workflows/ci.yml` triggers on
`push` to **`main` only** and on **any `pull_request`**; it uses no secrets, no
database or Supabase variables, no deploy, publish or paid-service step, and
runs ruff, black, mypy and `pytest -v` (database-backed tests skip without
`DATABASE_URL`). So pushing the feature branch triggers **no** workflow; opening
a PR triggers CI only. No push hooks exist locally (`pre-commit` is configured
but not installed; no `core.hooksPath`). Deployment manifests exist
(`backend/railway*.toml`, `backend/Dockerfile*`, `web/vercel.json`) but they
declare no branch triggers; **whether Railway or Vercel GitHub integrations
deploy or preview feature branches is configured outside the repository and is
UNVERIFIED** (owner check). A remote branch `deploy/extraction-worker-diag`
exists, which suggests a `deploy/*` convention; the proposed name does not match
it. Migrations are not run by any manifest or workflow, and there is no
embedding worker service or cron, so a deploy of this branch would not run
embeddings or migrations (but would ship the code).

**Content.** Pattern scan of everything the branch would add (committed and
working tree; values redacted) found only deliberate fake test strings
(`sk-test-…`, `sk-LLM-KEY-…`) and a dummy `postgresql://u:p@host/db` in a lock
test; none match a real provider key format. No `.env`, virtual environment,
cache, binary or private document is tracked (`.gitignore` covers `.env` and
`.venv`). A scan is not proof of absence; owner awareness: `docs/proposed/`
contains internal planning text and a rendered SQL review file; the repository's
privacy decides who sees it.

**Preconditions to push (all required, none satisfied by this report):**
1. Owner confirms `origin` is the intended **private** repository and that
   `kirantoday/nexus-credit-intelligence` is the right destination account.
2. Owner confirms Railway/Vercel/other integrations will not deploy or expose
   the feature branch (or accepts it).
3. The local checkpoint is committed and reviewed; checks green.
4. A read-only remote verification (below) has been separately approved and run.

**Exact intended command (not executed; no force, no `--all`, no `--mirror`, no tags):**

```
git push --set-upstream origin refs/heads/milestone-10d2-document-embeddings:refs/heads/milestone-10d2-document-embeddings
```

Re-check branch, HEAD and clean status immediately before running; never push
`main`.

**Draft PR (not published):** title: `WIP: Milestone 10D.2 document embeddings
(offline foundation, disabled by default)`. Body: milestone 10D (10D.2, open);
adds the embedding job/worker foundation, an OpenAI `text-embedding-3-large`
(1024) adapter with mocked tests, durable retry scheduling, operator holds, a
single-worker advisory lock and policy audit events; **embeddings are disabled
by default; no real provider call, key or live use; migrations 0021–0023 are
unapplied drafts in `backend/alembic/drafts/`; integration behavior (SQL claim,
locking, migrations) is unverified;** security routes unchanged; PLAN.md,
BUILD_LOG.md and ADR-021 intentionally not updated; do not merge.

**Remote verification needing network (proposed, separate approval):**
`git ls-remote --heads origin` (read-only: confirm the ref does not exist and
`main` matches), and, if GitHub access is authorized, a read-only repository
metadata check (private visibility, default branch, branch protection, installed
apps/webhooks). No push, fetch-merge or API write.

## 11. Ordered follow-up (each separately gated; none executed)

1. Security implementation scope: anonymous process enqueue, restricted
   metadata, adjacent anonymous mutation routes (before any public exposure).
2. Isolated integration environment: policy exception and provisioning.
3. Named-environment read-only preflight.
4. Each migration application with artifacts, rollback/abort plan and approval.
5. Integration tests (§7 matrix) with synthetic data and controlled egress.
6. Separately authorized synthetic provider smoke test (request count/budget).
7. Optional quality evaluation, later 10D.3 retrieval and public rollout.

## 12. Preservation and action audit

- Pre-existing uncommitted work at start: none. Earlier checkpoints intact.
- Edited: `config.py`, `core/types.py`, `domain/document_embedding_job.py`,
  `embeddings/{errors,factory,openai_provider,processor}.py`,
  `models/document_embedding_job.py`,
  `repositories/document_embedding_job_repository.py`,
  `services/document_embedding_service.py`,
  `scripts/run_document_embedding_worker.py`, `alembic/drafts/README.md`,
  `.env.example`, and tests. New: `embeddings/{scheduling,worker_lock}.py`,
  `scripts/release_held_embedding_job.py`, draft `0023`, six new test files,
  this report, plus a dated note in the readiness review.
- No network use of any kind, no provider request, key, `.env` change, database
  or Supabase/Storage contact, service start, migration rendering/application,
  integration test, dependency/SDK installation, CI/CD change, Git write, push,
  merge or deployment.
