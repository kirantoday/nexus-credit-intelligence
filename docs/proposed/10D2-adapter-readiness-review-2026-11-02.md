# Milestone 10D.2 — OpenAI adapter readiness review and targeted fixes (2026-11-02)

Status: **offline review and fixes only.** Embeddings stay disabled; no real
request, key, database, migration, integration test, network use or Git write
occurred. Live use remains blocked (§5). 10D.2 stays open; ADR-021 stays
`Proposed`; draft migrations 0021/0022 stay unapplied and keep their warnings.

Baseline at start [read-only Git]: branch `milestone-10d2-document-embeddings`,
HEAD `21ff37b51e3f3cd7caa9b545788795836ff78cec`, clean tree, nothing staged, no
stashes. Everything below is uncommitted work from this session.

## 1. Findings (exact locations)

| # | Finding | Evidence | Verdict |
|---|---|---|---|
| F1 | The earlier claim "transient failures are the only ambiguous, possibly billable ones" was **wrong**. A 200 response rejected locally (wrong count/width/model, bad index, malformed JSON, non-unit vector) was raised from inside `embed_documents`, so the processor never saw its `usage`. It was classified deterministic, **not counted in the run budget**, and its valid usage was lost. Likewise 4xx/401/403/404 responses and read/write timeouts were not all treated as possibly billed. | `processor.py` provider-failure branch (before: counted only `classify(exc) == "transient"`); `openai_provider._parse_success` | **Defect, fixed** |
| F2 | `Retry-After` is parsed (numeric only; capped 3600 s) but then **lost**: `_failure` used the rate-limit error only for `abort_run`. The job is requeued with `status=pending`, `started_at=NULL` and no "not before" value, and `claim_next_pending` takes the oldest pending job with no time condition, so any worker or next invocation can reclaim it immediately. Each rate-limited attempt also consumes an attempt (no refund), so a scheduler invoking during a rate-limit window can drive a job to `failed` after `max_attempts`. | `processor._failure`; `document_embedding_job_repository.claim_next_pending` (line 95), `requeue_pending` (line 148) | **Limitation; durable fix needs a new field. Not implemented. Live use blocked.** |
| F3 | The input guard counted **characters**. Non-ASCII text can need several tokens per character, so 8,000 characters is not even a plausible bound for CJK or emoji. | old `MAX_INPUT_CHARS` | **Defect, fixed** (now UTF-8 bytes) |
| F4 | Batch planning split only by input **count**. A batch whose total exceeded the adapter's aggregate cap was rejected whole as a terminal error instead of being split. | old `process_job` loop | **Defect, fixed** (`_plan_batches`) |
| F5 | A blank `EMBEDDING_DIMENSION=` line, as shipped in `.env.example`, makes `Settings()` raise `ValidationError`, so copying the example to `.env` would break **all** application startup although embeddings are disabled. Same for a blank timeout. | reproduced offline with `Settings(_env_file=None)`; `config.py:109` | **Defect, fixed** (blank means unset) |
| F6 | Policy safeguards verified correct already: disabled embeddings never build a client; the LLM key is never read; model, dimension and the exact acknowledgement string fail closed; eligibility is rechecked before every provider call; the acknowledgement is only a string comparison (not identity, not durable acceptance, not blanket permission). | existing tests plus new acknowledgement-exactness and blank-environment tests | **No change needed** |

## 2. Fixes and behavior changes

| File | Change |
|---|---|
| `backend/app/embeddings/errors.py` | `EmbeddingError` gains `request_attempted`, `possibly_billed`, `reported_input_tokens` (class defaults mean "no request was made"). Backwards compatible. |
| `backend/app/embeddings/openai_provider.py` | Marks every error raised after a request was issued; connect-phase failures (`ConnectError`, `ConnectTimeout`, `PoolTimeout`) are `possibly_billed=False` (no delivery), everything else after sending is `True`; a rejected 200 carries the vendor's valid `prompt_tokens`. Size policy is **UTF-8 bytes** (8,000 per input, 300,000 per request); `input_size()` and `max_batch_input_size` expose it. |
| `backend/app/embeddings/processor.py` | Failure accounting from the evidence (matrix §3); `_plan_batches` splits by count and by the provider's size cap; `JobResult.retry_after_seconds` added. |
| `backend/app/scripts/run_document_embedding_worker.py` | Prints the vendor's requested wait and says the queue does not enforce it. |
| `backend/app/config.py` | Blank numeric embedding settings mean "unset" (defaults). |
| tests | `test_embedding_adapter_readiness.py` (new, 64 tests); one earlier test rewritten because it asserted the superseded assumption (below). |

**Compatibility effect of the byte policy.** Nexus chunks are capped at 4,000
characters plus a short header, about 4.3 KB for ASCII and a few hundred bytes
more with typographic characters (3 bytes each), so ordinary chunks fit
within 8,000 bytes with margin, and 64 of them fit within 300,000 bytes; the
planner splits any batch that would not. Only heavily non-ASCII chunks (for
example CJK at 3 bytes per character) are now rejected locally where a
character count would have allowed them: intentionally. If the model's
tokenizer is byte-level (never a token for less than one byte; **not stated in
the documentation read**, so an assumption), N bytes is at most N tokens, which
makes the caps an upper bound. Nothing here is a guaranteed token bound, and a
vendor rejection stays a terminal `EmbeddingInputError`. If exact counts are
needed a tokenizer dependency would have to be approved separately (tradeoffs:
a new dependency and vocabulary file, exact counts, version coupling to the
vendor's tokenizer); none is installed or proposed for implementation here.

## 3. Outcome and accounting matrix

"Call log" = `embedding_call_log` row via `record_call`. "Budget" = the
per-run `EmbeddingRunBudget` (a local counter, not a provider-enforced cap).
Persisted tokens are only ever the vendor's own number or `None`.

| Outcome | Request issued? | Call log | Known usage | Budget (local, conservative) | Retry policy |
|---|---|---|---|---|---|
| Pre-request validation (empty/oversize/blank/unencodable input, batch too large) | No | `success=false`, tokens `None` | none | **Nothing counted** (not an attempt) | Terminal (deterministic); no retry |
| Connection/pool failure (`ConnectError`, `ConnectTimeout`, `PoolTimeout`) | Attempted, not delivered | `success=false`, tokens `None` | none | 1 request, **0 tokens**, cost not added | Transient; job-level, bounded |
| Timeout/drop after sending (`ReadTimeout`, `WriteTimeout`, `ReadError`, `RemoteProtocolError`) | Yes, outcome unknown | `success=false`, tokens `None` | none | 1 request + **estimated** tokens/cost | Transient; job-level, bounded |
| Provider error status (400, 401, 403, 404, 408, 429, 5xx) | Yes | `success=false`, tokens `None` | none | 1 request + **estimated** tokens/cost (no evidence an error is free) | 400/401/403/404, quota 429: terminal or run-stop, never retried; plain 429, 408, 5xx: transient, job-level |
| Valid 200 | Yes | `success=true`, vendor `prompt_tokens`, cost from list price | **actual** | 1 request + **actual** tokens, once | n/a |
| 200 rejected locally (count/width/model/index/JSON/norm) with valid usage | Yes | `success=false`, vendor tokens, cost from list price | **actual** | 1 request + **actual** tokens; added to `JobResult.tokens_used` | Terminal (deterministic); **not retried** |
| 200 rejected locally with missing/invalid usage | Yes | `success=false`, tokens `None` | none | 1 request + **estimated** | Terminal; not retried |
| Retry (next job attempt) | Yes (new request) | new row | per outcome | counted again, visibly | Max `max_attempts`; one HTTP attempt per call (no inner retry) |
| Later batch rejected before sending, earlier batch succeeded | No for the later one | earlier `success=true` rows kept | earlier actual | earlier counted; later nothing | Terminal; earlier rows stay persisted |

No layer double counts: the adapter keeps no counters, the processor records
each issued request exactly once (success or failure path), the worker only
prints. Tests assert `budget.requests_made == HTTP requests`. Unknown stays
unknown in the database; estimates only ever reach the in-process budget. The
successful-usage rule ("use `prompt_tokens`, never add `total_tokens`") is
unchanged.

**Candid limits.** Per-run counters and `len ÷ 4` estimates are not a
cross-run hard monetary ceiling; they do not persist across runs, and multiple
workers each have their own counter. Requests are not exactly-once, a failed
request may still be billed, and an ambiguous failure may be billed while only
an estimate is recorded locally. Provider-side project or organization spend
limits are the only vendor-enforced ceilings (documented in the error-code
page as `project_spend_limit_exceeded` / `organization_spend_limit_exceeded`);
their configuration cannot be inspected here and must be verified by the
account owner before being treated as enforcement.

## 4. Retry-delay trace (adapter → processor → repository → worker)

1. **Adapter** `_retry_after_seconds` (`openai_provider.py:439`): numeric
   seconds only, finite and ≥ 0, capped at 3600; an HTTP-date, text, negative or
   missing value yields `None`. Carried on `EmbeddingRateLimitError`.
2. **Processor** `_failure`: for a rate limit it requeues (`status=pending`,
   `refund_attempt=False`), sets `abort_run=True` and now exposes
   `JobResult.retry_after_seconds`. Quota/billing 429s are
   `EmbeddingAuthError`: requeued with the attempt **refunded**, run stopped,
   **no** delay and never retried. Deterministic response errors are failed, not
   requeued.
3. **Repository** `requeue_pending` (line 148): writes status, note, error
   fields and the attempt refund. It has **no** field for a retry time.
   `claim_next_pending` (line 95): oldest `pending` row by `created_at` with
   `FOR UPDATE SKIP LOCKED`, no time condition. So **the delay is not durable**:
   another worker, a restarted process or a repeated invocation can reclaim the
   job at once. `SKIP LOCKED` prevents two workers holding the same job, but
   several workers can each send a request for *different* jobs, and each has its
   own budget.
4. **Attempt cap**: `claim_next_pending` increments `attempt_count`; after
   `max_attempts` rate-limited attempts the job becomes `failed` (transient).
   Verified by test: three attempts → three requests → `requeued, requeued,
   failed`. Quota/auth attempts are refunded and so are unbounded across
   invocations, but each invocation sends one request and the run stops.
5. **Worker**: prints the requested wait and states it is not enforced. A
   process-local sleep was **not** added: it would not bind other workers, would
   hold a process, and must not be presented as enforcement.

**Why no fix was made.** The only ways to express "not before" with existing
columns would overload `started_at` (null/unused on `pending` rows) and change
the claim SQL, a semantic change to job state that cannot be proven without a
database. That is outside the authorization (no schema or broad job-state
change, no integration tests). **Proposal (not implemented):** a nullable
`retry_not_before timestamptz` on `document_embedding_job` (add to draft 0022
while still unapplied, or a later migration), set by `requeue_pending` from the
vendor delay (or a capped exponential default), and
`claim_next_pending ... WHERE status='pending' AND (retry_not_before IS NULL OR
retry_not_before <= clock_timestamp())`. Acceptance tests: (a) a requeued job is
not claimable before its time and is claimable after; (b) two concurrent
claimers never get the same job and neither gets a delayed job; (c) a stale
reclaim clears or preserves the field per rule; (d) rate-limit requeue does not
refund the attempt while quota requeue does; (e) the cap still ends the job;
(f) a worker restart honours the stored time. These need the gated integration
environment. **Until implemented and integration-tested, live use is blocked.**

## 5. Live-use blockers (all remain; none granted)

1. Durable retry-not-before (§4) and its integration test.
2. Owner acceptance of ADR-021, policy activation, vendor account, dedicated
   key, and provider-side spend limits verified by the account owner.
3. Read-only preflight: pgvector extension schema/`search_path`, runtime
   `CAST(:embedding AS vector)`, applied revision.
4. Migrations 0021 then 0022 (separately approved); integration tests.
5. A first budget-capped live smoke call (public/synthetic input) to confirm
   shortened-vector normalization, usage and error behavior.
6. Audit-event follow-up (§6) — recommended before any live run.
7. Security scope for the anonymous process route, restricted metadata and
   adjacent mutation routes (separate; important before public use).
8. Optional public-document quality evaluation of 1024.

## 6. Policy-audit follow-up — PROPOSED, NOT IMPLEMENTED (separately gated)

An audit event records what happened; it does **not** grant permission.

**Existing facility.** `audit_repository.create_event(AuditEventCreate(user_id,
event_type, entity_table, entity_id, before_state, after_state))` →
`audit_event` with unconstrained `event_type`/`entity_table` text, nullable
`entity_id`, JSONB states, server-side `occurred_at`. **No schema change is
required.** Adding enum members to `AuditEventType` is code-only. Today's
enqueue event (`DOCUMENT_EMBEDDING_REQUESTED`, `document_embedding_service.py`
~148) records only extraction id, model id and version.

**Candidate events** (`entity_table="document_embedding_job"`, `entity_id` the
job id; worker start uses `entity_table="embedding_worker_run"`, `entity_id=NULL`):

| Event | When | `after_state` (no secrets, text, vectors, URLs) |
|---|---|---|
| `DOCUMENT_EMBEDDING_REQUESTED` (extend) | At enqueue, same transaction as the job | existing fields **plus** `provider`, `nexus_config_version` (the `EMBEDDING_MODEL_VERSION` label), `dimension`, `policy_acknowledgement_observed` (the configured string, or `null`), `policy_acknowledgement_matches_required` (bool) |
| `EMBEDDING_WORKER_STARTED` (new) | After the provider is built and before the first claim | same provider/model/version/dimension/observed-acknowledgement fields, budget limits (tokens, cost, requests), `embeddings_enabled`, process-level run id |

**Observed versus accepted.** The event must say *what the worker observed*:
field `policy_acknowledgement_source = "environment_variable"`. It must never be
labeled "owner accepted". Durable owner acceptance would be a separate record:
an owner-authored, dated, versioned policy statement in the repository (accepted
ADR-021 or a policy document) referenced by id/hash in `after_state`
(`policy_reference`). Until that reference exists the events can only show
"observed config", which is exactly what they are.

**Operator attribution.** There is no authenticated identity.
`requested_by`/operator name is client-asserted free text, so store it as
`asserted_actor` with `identity_verified=false`; never as `user_id` implying
authentication (the existing column is reused as-is for the asserted string, with
the flag in `after_state`).

**Ordering and failure handling.** Write the event **before** any provider
request and in the same transaction as the job (enqueue) or committed before the
first claim (worker start). If the audit write fails the run must stop **before**
sending anything (fail closed). Events are append-only; no secrets are logged.

**Acceptance tests (mocked repositories):** event written before the first
provider request; audit failure → zero requests; fields exactly as listed and no
key/text/vector/URL appears; observed-versus-required booleans correct for
matching, missing and mismatching acknowledgements; asserted actor flagged
unverified; no event when embeddings are disabled and no provider built.

**Proposed files:** `backend/app/core/types.py` (new `AuditEventType` member),
`backend/app/services/document_embedding_service.py` (extend enqueue event, add
worker-start recorder), `backend/app/scripts/run_document_embedding_worker.py`
(call it, fail closed), and new unit tests. **Dependencies:** none beyond the
existing audit repository; **no authorization subsystem and no schema change**
are required for the events themselves.

## 7. Validation (offline, `backend/.venv`, Python 3.12.10)

Interpreter confirmed; `ENVIRONMENT=test`, `EMBEDDINGS_ENABLED=false` set for
the process only; no `.env` exists; `tests/integration` is not collected under
`tests/unit`. Mocked `httpx` transport, in-memory job store and the diagnostic
network tripwire (socket connects, `getaddrinfo` and the real httpx transport
raise; it catches Python-level attempts in the test process only and does not
cover UDP, other processes or native code) were used throughout. Nothing slept.

| Command (from `backend`) | Result |
|---|---|
| `python -m pytest tests/unit` | **588 passed**, 0 failed, 0 skipped, 1 third-party warning; exit 0 |
| `python -m ruff check .` | All checks passed; exit 0 |
| `python -m black --check .` | 364 files unchanged; exit 0 |
| `python -m mypy app` | Success, 238 source files; exit 0 |

These were run once after the final code edit; the earlier 524-test result is
historical and not reused. One earlier test
(`test_deterministic_failure_is_not_counted_as_possibly_billed`) asserted the
superseded assumption and was rewritten, not weakened:
`test_a_provider_rejection_is_terminal_but_still_counts_as_an_attempted_request`.
Not run: integration tests, any database, migration rendering, any provider call
or network access.

## 8. Preservation and action audit

- Pre-existing work: none uncommitted at start; all earlier checkpoints intact.
- This session edited: `config.py`, `errors.py`, `openai_provider.py`,
  `processor.py`, `run_document_embedding_worker.py`,
  `tests/unit/test_openai_embedding_adapter.py`; created
  `tests/unit/test_embedding_adapter_readiness.py` and this report; added a dated
  correction note to `10D2-openai-adapter-implementation-report-2026-11-02.md`.
- No network use (no documentation downloads), no provider request, no key or
  `.env` change, no database/Supabase/storage/migration/integration action, no
  dependency or schema change, no Git write, push or deployment. The review used
  documentation already obtained earlier; nothing external was needed.
