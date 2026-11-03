# Milestone 10D.2 — OpenAI embedding adapter: offline implementation report (2026-11-02)

Status: **implemented and validated offline only.** The engineering contract
(OpenAI `text-embedding-3-large`, 1024 dimensions via `dimensions=1024`, cosine
direction, `httpx`, embeddings disabled by default) is approved **for local
development only**. No real request was made, no key exists, no database,
migration, storage or deployment action occurred, and ADR-021 stays
`Proposed`. 10D.2 is not complete; migrations 0021/0022 are unapplied drafts.

## 1. Primary sources (public official documentation, read 2026-11-02)

The raw pages were downloaded to a scratch folder and converted to text with an
inert parser (not an AI summary); none of this repository's content was sent.

| Fact used | Source |
|---|---|
| `POST https://api.openai.com/v1/embeddings`; `input` string or array; **max 2048 array items**; each input ≤ **8192 tokens**, non-empty; **300,000 tokens summed per request**; `dimensions` (≥1, text-embedding-3 and later); `encoding_format` `float` (default) or `base64`; response `data[].embedding/index/object`, `model`, `usage.prompt_tokens/total_tokens` | https://developers.openai.com/api/reference/resources/embeddings/methods/create |
| Default width 3072 for 3-large; `dimensions` is the suggested way to shorten; **manual shortening requires re-normalization**; "OpenAI embeddings are normalized to length 1" | https://developers.openai.com/api/docs/guides/embeddings |
| $0.13 per 1M tokens; `/v1/embeddings` and `/v1/batch` supported; single default snapshot listed | https://developers.openai.com/api/docs/models/text-embedding-3-large |
| 400/401/403 semantics; 429 variants (`credit_balance_exhausted`, `organization_spend_limit_exceeded`, `project_spend_limit_exceeded`, `organization_usage_limit_exceeded`, `insufficient_quota`, plain rate limit, `slow_down`); 500 and 503 `server_is_overloaded`; honor `Retry-After`; "Retrying billing, spend, or quota errors won't restore API access" | https://developers.openai.com/api/docs/guides/error-codes |
| Rate limits are per account tier | https://developers.openai.com/api/docs/guides/rate-limits (not used as universal limits) |

**Discrepancies resolved against the earlier research note.** The earlier
extract listed the 8192 limit only in a table and "per-request limits: not
stated"; the primary reference states 2048 inputs and 300,000 aggregate tokens,
and that empty strings are rejected. The reference **does not state** that a
shortened (`dimensions`) vector is re-normalized; its example (`dimensions: 3`)
returns `[0.26726124, 0.53452248, 0.80178373]`, whose squared sum is 1.0000, and
the guide states normalization generally. The adapter therefore *verifies* unit
length and rejects otherwise — it never rescales. The `x-request-id` header is
not documented in the pages read, so it is not used.

## 2. What was implemented

| File | Change | Origin |
|---|---|---|
| `backend/app/embeddings/openai_provider.py` | **New.** `OpenAIEmbeddingProvider` | this task |
| `backend/app/embeddings/errors.py` | Added `EmbeddingResponseError` (deterministic) | this task |
| `backend/app/embeddings/factory.py` | Registers `openai` with fail-closed prerequisites; unknown names refused | this task |
| `backend/app/embeddings/pricing.py` | `openai`/`text-embedding-3-large` = $0.13 per 1M, source/date commented | this task |
| `backend/app/embeddings/processor.py` | Ambiguous (transient) failures are counted against the run budget | this task |
| `backend/app/scripts/run_document_embedding_worker.py` | Closes a provider that owns an HTTP client | this task |
| `backend/app/config.py`, `.env.example` | `embedding_api_key` (`SecretStr`), `embedding_request_timeout_seconds`, `embedding_external_policy_approval`; placeholders empty; `EMBEDDINGS_ENABLED=false` | this task |
| `backend/tests/unit/test_openai_embedding_adapter.py` | **New.** 134 mocked tests | this task |
| `backend/tests/unit/test_embedding_factory.py`, `test_document_embedding_worker.py` | One test updated for the new refusal wording; one test added | this task |
| `docs/proposed/ADR-021-document-embeddings.md` | Dated amendment note; **status unchanged (Proposed)** | this task |
| `docs/proposed/10D2-embedding-contract-research-and-decision-2026-11-02.md` | Research note | **pre-existing (previous task)** |
| `docs/proposed/10D2-addendum-…-2026-11-02.md` | Dated download-test clarification | **pre-existing (previous task)** |

No schema, model, vector cast, Alembic file, draft migration, route, or
dependency was changed. No package was installed.

## 3. Decisions

**Request.** Fixed URL constant (no endpoint setting); body
`{model: "text-embedding-3-large", input: [...], dimensions: 1024,
encoding_format: "float"}`; `Authorization: Bearer <dedicated key>`; no `user`
field. Documents and queries use the same call (no documented task mode);
the local fingerprint still separates `document` and `query`. Redirects are
disabled and treated as a configuration error, so the key is never resent to
another host. Timeouts are explicit and finite (default 30 s, cap 300 s).

**Limits.** Batch ≤ configured size (default 64) and ≤ 2048. No tokenizer is
installed (and none may be), so a **conservative character policy** applies:
≤ 8,000 characters per input (≤ ~4,000 tokens if as little as 2 characters per
token) and ≤ 600,000 characters per request (the 300,000-token limit at the same
ratio). This is a heuristic, **not** a guarantee; unusual text can still exceed
8192 tokens, in which case the vendor's 400 is a terminal `EmbeddingInputError`.
Nothing is truncated or sliced.

**Response validation.** JSON object; `model` must equal the approved model
(else `EmbeddingDimensionMismatchError`); `data` count must equal input count;
every `index` must be a non-bool integer, in range, unique; results are
re-ordered by `index`; every vector must be a list of finite, non-bool numbers
of width 1024 and L2 norm within ±0.01 of 1 (documented unit length; no
rescaling). Anything else is rejected without content in the message.

**Usage.** Aggregate `usage.prompt_tokens` only; `total_tokens` is never added;
absent, malformed, negative, boolean, or `prompt_tokens != total_tokens` →
`None` (unknown, never zero). No per-input usage is inferred.

**Errors** (existing types, plus `EmbeddingResponseError`):

| Condition | Mapped to | Retry |
|---|---|---|
| timeout; connection/transport error; 408; ≥ 500 (incl. 503 overload) | `EmbeddingTransientError` | job layer, bounded |
| 429 plain rate limit / `slow_down` (or no parsable body) | `EmbeddingRateLimitError` (+ `Retry-After`, capped at 3600 s) | run stops (existing), job requeued |
| 429 with a quota/billing/spend code or `type=insufficient_quota` | `EmbeddingAuthError` | **never** retried; run stops |
| 401, 403 | `EmbeddingAuthError` | stop |
| 400 and other 4xx | `EmbeddingInputError` | terminal |
| 404, 3xx | `EmbeddingConfigurationError` | terminal |
| malformed JSON/shape/index/number/unit length | `EmbeddingResponseError` / `EmbeddingDimensionMismatchError` | terminal |

Only the vendor's short `error.code`/`error.type` strings are read; messages,
bodies, headers, keys, input text and vectors never appear in an exception.

**Retries.** The adapter makes **one HTTP attempt per call**. Retrying already
exists a layer up (job attempt cap, requeue, and the worker stopping the run on
a rate limit); an inner loop would multiply requests. Tests prove one request
per job attempt (three attempts → three requests).

**Accounting (reviewed, minimal change).** Before: a failed provider call
recorded `success=false` but did not touch the run budget. Now a *transient*
failure — the only ambiguous kind (timeout, dropped connection, 5xx, 429 rate
limit) — adds the **estimated** tokens/cost to the run budget, because the
vendor may have processed and billed it. Terminal failures (400, auth) are not
counted. Successful calls use vendor-reported tokens; if usage is missing the
processor's existing rule uses the estimate for the budget and leaves the call
log's tokens and cost `None`. Limits and caveats: the budget is a **local
per-run counter built on a `len ÷ 4` estimate, not a provider-enforced spending
cap**; it does not survive across runs; requests are not exactly-once; an
ambiguous failure may be billed while recorded only as an estimate. A reliable
hard ceiling would need a vendor-side project spend limit set by the account
owner (documented by OpenAI) and a persisted cross-run ledger — a broader
change, not made here.

**Credentials and policy.** A dedicated `EMBEDDING_API_KEY` (a `SecretStr`, never
printed or logged) is required; the LLM's `OPENAI_API_KEY` is never read or used
as a fallback (tested). The factory builds `openai` only if embeddings are
enabled **and** the model version label is set **and** the key is set **and**
`EMBEDDING_EXTERNAL_POLICY_APPROVAL` equals `openai:text-embedding-3-large`;
otherwise it raises a configuration error before any client object exists.
Disabled embeddings never construct the provider or an `httpx` client (tested).
The fake provider stays local/test only; unknown names are refused.

**How the owner's approval must be recorded before any live run (not
activated here).** (1) The owner states in writing that provider `openai`,
model `text-embedding-3-large`, and the vendor's data-handling terms
(including whether account-level zero retention or residency is wanted) are
approved; (2) ADR-021 is accepted by the owner (not done); (3) only then is the
variable above set in the *operator's* environment, never in the repository.
This variable is a **guard, not an audit record**. The current architecture has
no durable per-run approval record; the smallest follow-up proposal is to log
one `audit_event` at worker start and at enqueue that records the provider,
model, version label and the configured acknowledgement (no secrets) — a small
code change that needs its own approval. Document-level eligibility is
unchanged and still re-checked at queue time and immediately before every
provider call.

`model_version` is a Nexus label identifying local configuration, **not** a
vendor snapshot (OpenAI lists only a default alias). No canary or scheduled
call exists; any later canary needs separate paid-call approval,
tolerance-based interpretation and human review before re-embedding.

## 4. Validation (offline; real tools in `backend/.venv`, Python 3.12.10)

Interpreter confirmed; embeddings disabled (`EMBEDDINGS_ENABLED=false`) and
`ENVIRONMENT=test` set process-locally; no `.env` exists; fixtures and imports
were checked to contain no database, storage or provider connection (the
integration fixtures are not collected under `tests/unit`).

| Command (from `backend`) | Result |
|---|---|
| `python -m pytest tests/unit` | **524 passed**, 0 failed, 0 skipped, 1 third-party warning; exit 0 (62 s) |
| `python -m ruff check .` | All checks passed; exit 0 |
| `python -m black --check .` | 363 files unchanged; exit 0 |
| `python -m mypy app` | Success, 238 source files; exit 0 |

Earlier results (389 tests) are historical and were not reused. Focused
development runs preceded these; the final four commands were run once after the
last code edit. Not run: integration tests, any database, migration rendering,
any provider call.

Coverage added (134 tests in the new file, plus one worker test; 524 total vs 389 before): request construction (model, width, encoding,
fixed URL, batching, document and query); order restored from indices; wrong
count, width and model; duplicate, missing, negative, non-integer and bool
indices; malformed JSON/shapes; base64, non-numeric, bool, NaN and infinity
values; non-unit vectors; usage present, missing, malformed and not
double-counted; every status mapping; quota-versus-rate-limit 429s;
timeouts/network errors; redirects not followed; one attempt per call and per
job attempt; secret- and content-free diagnostics; key, dimension, batch and
timeout validation; lazy client creation, safe client settings and close
semantics (owned vs injected); factory prerequisites and refusals; settings
defaults and secret non-disclosure; pricing; processor accounting under
success, missing usage, transient and deterministic failure, auth and quota
stops; and **zero provider requests** for archived, superseded, restricted,
reclassified/non-standard, revoked, checksum-mismatched, incomplete
(pending/processing/failed/needs_ocr), wrong-document and missing-extraction
states, plus revocation between batches.

**Network guard.** A module-wide autouse fixture makes socket `connect`,
`connect_ex`, `create_connection`, `getaddrinfo` and the real
`httpx.HTTPTransport.handle_request` raise. It catches Python-level connection
attempts in the test process only; it does not cover UDP, other processes or
native code, and is a tripwire, not proof of isolation. All requests in tests go
through `httpx.MockTransport`.

## 5. Remaining limitations and gates (none granted)

- **1024 quality** is unevaluated for credit documents; an optional
  public-document evaluation is a separate decision (not run).
- **Shortened-vector normalization** is verified by the adapter at runtime but
  not documented explicitly by the vendor for `dimensions`; a first live smoke
  call (separately authorized, budget-capped, public/synthetic input) is the
  proper check, and a failure would be a terminal response error, not silent.
- **Extension schema / `search_path` and runtime cast verification** are still
  pending: unqualified `vector`/`vector_dims` in draft 0022 and
  `CAST(:embedding AS vector)` in the repository need a named-environment
  read-only preflight.
- **Policy activation** (§3), vendor account, key, ZDR/residency terms and spend
  limit are owner actions; none done.
- **Security** remains separate and important: the anonymous process route
  (unbounded enqueue, forged `requested_by`), restricted-document metadata
  exposure and the adjacent anonymous upload/patch/archive routes need a
  concrete security scope before public use. Not implemented here.
- Not done and separately gated: integration environment exception and
  provisioning, read-only preflight, migration 0021 then 0022, integration
  tests, first live call, 10D.3.
- A WIP checkpoint, a pattern scan and these mocked tests are **not** a
  comprehensive implementation review; review remains required before live use.
- Early-exit paths in the worker that return before the run starts do not call
  `close()`; no client exists at that point because it is created lazily.

---

## Corrections dated 2026-11-02 (adapter readiness review)

Historical text above is kept. These statements are **superseded**; see
`10D2-adapter-readiness-review-2026-11-02.md`:

- "A *transient* failure — the only ambiguous kind — adds the estimated
  tokens/cost to the run budget. Terminal failures such as 400 and
  authentication are not counted." Incorrect: any request that was actually
  issued may have been billed, including provider error statuses and a 200
  response rejected locally. The processor now counts every issued request,
  uses the vendor's own valid usage when a rejected response carried it, and
  does not count failures that happened before any request.
- "At most 8,000 characters per input / 600,000 characters per request."
  Replaced by a UTF-8 **byte** policy (8,000 per input, 300,000 per request),
  because characters under-count tokens for non-ASCII text. Still a heuristic.
- "135 mocked tests" / "524 total": historical counts for the checkpoint at
  commit 21ff37b.
- Retry delays: the vendor's `Retry-After` was parsed but not durably applied.
  The queue has no "not before" field; this is now documented, surfaced on the
  job result and worker output, and live use is blocked until a durable field
  exists and is integration-tested.
