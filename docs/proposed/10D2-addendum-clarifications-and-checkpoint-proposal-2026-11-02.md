# Milestone 10D.2 — Addendum: clarifications, qualifications and exact checkpoint proposal (2026-11-02)

Status: **proposal / review only.** This addendum qualifies and corrects
`10D2-migration-review-and-approval-packets-2026-11-02.md` (the "packet"),
which is left unedited so its history stays intact. Where they disagree, this
addendum governs. It authorizes nothing: no database, network, migration,
integration run, Git write, security implementation or 10D.3 work.

Evidence labels: **[code]** read from local source; **[git]** read-only local
Git; **[file]** local file/log; **[prior report]** repeated from an earlier
report, not re-verified; **[UNVERIFIED]** needs deployment or database
inspection; **[DECISION]** needs the owner.

## Final corrections (2026-11-02, second pass) — these govern where they conflict with text below

1. **Inventory:** the Word report `Milestone_10D2_Followup_and_Checkpoint_Proposal_Report.docx`
   listed 57 rows with this addendum twice (rows 52 and 53) under a "56 paths"
   heading. The table in §4 below is the single authoritative inventory:
   **56 unique paths = 6 modified + 50 untracked** (re-counted from current Git
   state). Historical reports are not edited.
2. **Commands:** the earlier command block was not executable as written (a
   path-corrupting typo, `"$env:TEMPd2-msg.txt"`, no native-exit-code checks)
   and suggested a pathspec-limited commit. Both are withdrawn. The corrected,
   complete sequence is delivered with the approval request, generated from §4.
3. **Network isolation:** the statement that a socket tripwire "proves no
   outbound call" is withdrawn; see §5.2.
4. **Route policy:** chunk list, chunk search and signed download are now
   specified separately, the inspection flag no longer applies to downloads,
   and production fails closed even when `ENVIRONMENT` is absent; see §1.8.
5. **Remaining anonymous exposure** (metadata and process routes) is scoped in §1.9.
6. Option B is accepted as the planning direction. That does **not** establish
   that the whole API is safe for public exposure.

## 0. Starting inventory and this follow-up's own edits

At the start of this follow-up [git]: branch `main`, HEAD `b2a9f31`, nothing
staged, no stashes, 6 modified tracked files and 49 untracked files (55 paths;
plain `git status` shows 38 lines only because untracked directories collapse).

Edits made in **this** follow-up (documentation only):

1. Created this addendum (new, untracked).
2. `docs/proposed/10D2-offline-sql-0020-to-0022-REVIEW-ONLY-NOT-APPLIED-2026-11-02.sql`:
   removed trailing spaces from 82 generated lines (Alembic output) so
   `git diff --cached --check` would not flag them. No SQL token changed.

3. Second pass (this correction round): edited only this addendum (the sections named
   above). No other repository file was changed.

No code, migration, env.py, model, setting or config file was touched.

## 1. Endpoint security — clarified

### 1.1 What callers can reach today

| Question | Answer |
|---|---|
| Who can call the chunk, chunk-search and download routes? | Anyone able to reach the API. **[code]** no authentication or authorization dependency exists under `app/api`. |
| Identity checks? | None. `auth_enabled: bool = False` exists in `config.py:133` but nothing reads it **[code]**; `.env.example` says auth is "disabled for first demo". There are no `user`/`role` tables **[code]** (`core/types.py`, `models/research*.py` comments, TD-002/TD-025). |
| Document-level authorization? | None on these routes. Chunk routes check only that the extraction exists; download checks only that the document exists **[code]** (`document_extraction.py:99-125`, `research_documents.py:161`). |
| CORS | Restricts browsers only; direct API callers are unaffected **[code]**. |

**Confirmed locally:** the code paths above. **[UNVERIFIED], needs deployment
inspection (no deployed endpoint contacted):** whether the Railway API is
publicly reachable, what `ENVIRONMENT` is set to there, whether any gateway or
proxy adds authentication, and the deployed CORS origins.

### 1.2 Eligibility is not permission

`public_document_approval` + `evaluate_eligibility` answer one question: *may
this document's content go to an external embedding vendor and be returned by
public retrieval?* That is **public-document eligibility**. It says nothing
about whether a particular person may read an internal or restricted document.
"Not on the allowlist" must therefore mean "not available to anonymous
callers", never "available to internal staff": no mechanism identifies staff
today. Internal access requires authentication plus a document-level
authorization rule, neither of which exists.

### 1.3 How each state should affect access

| State | Anonymous / public route | Future authenticated internal access |
|---|---|---|
| Archived | Denied (404) | Allowed only if the authorization policy says so, via an explicit "include archived" path |
| Superseded (non-current) extraction | Denied | Explicit opt-in only |
| Restricted / reclassified after approval | Denied; classification read live, never from the chunk's copy | Per role/classification policy |
| Approval revoked | Denied immediately | Per policy |
| Stored-file checksum differs from approved checksum | Denied (the approved bytes are no longer the stored bytes) | Per policy; flag for review |
| Extraction not `completed` | Denied for chunk routes | Allowed to see status only |
| Extraction belongs to a different document than requested | Denied (404) | Denied |
| Never approved | Denied | Per policy |

### 1.4 Owner's preferred option B (restrict downloads in production) — concrete proposal

Planning preference only; not implementation approval.

- **Approved public document** (active approval, not archived, `standard`,
  checksum matches): download route returns the signed URL as today (300 s
  expiry unchanged) in every environment.
- **Everything else in staging/production:** 404, identical to "not found",
  so existence is not revealed. Never 403.
- **Explicitly authorized internal access:** not provided in staging/production
  until the authentication prerequisite below exists. No interim shared secret,
  header, query parameter or IP rule is proposed; each would be a new
  unreviewed trust mechanism.
- **Consequence [DECISION]:** the Research Documents view/download UI for
  internal documents stops working in deployed environments until internal
  access exists. The UI needs a deliberate "not available" state.
- **Not covered by B:** document list/detail metadata (titles, descriptions)
  stays anonymous (TD-027); `POST .../process` stays anonymous. B alone does
  not make the system private.

### 1.5 Authentication requirement created by this policy (separately gated)

Any "authorized internal access" needs: verified identity (the config comment
points to Supabase Auth JWTs; server-side verification of signature, expiry
and audience); a user/role store or verified role claims; a per-document
authorization rule mapping role to classification; an `audit_event` row for
each internal download/inspection; and tests that an invalid or missing
token never widens access. **Implementation is a separate gate** (see §6);
this addendum does not assume it exists or schedule it.

### 1.6 The local/test exception and the inspection flag, reconsidered

> **Superseded in part by §1.8.** The recommendation below keyed on
> `ENVIRONMENT` and a flag; §1.8 replaces it (the flag never applies to
> downloads, and an absent `ENVIRONMENT` is treated as production-like).

The earlier plan allowed inspection of non-approved documents when
`ENVIRONMENT in {local, test}` or when a default-off `CHUNK_INSPECTION_ENABLED`
is set. Findings:

- **Who could reach it if enabled on a deployed API?** Every anonymous caller
  who can reach the service, for every document. The flag adds no identity.
- **Can request input influence it?** Not as proposed: both values would come
  from the server's process environment (pydantic settings), and no request
  field participates. That property must be tested, not assumed.
- **Unsafe-bypass risk, confirmed [code]:** `config.py:20` defaults
  `environment` to `"local"`. A deployed service that lacks an `ENVIRONMENT`
  variable would therefore be treated as `local`. An exception keyed on
  `ENVIRONMENT in {local, test}` alone would then **silently open production**.
  Invalid values fail at boot (the type is a `Literal`), but an *absent*
  value does not. Whether the Railway service sets it is [UNVERIFIED].
- **Recommendation:** (1) remove the "environment alone" exception; (2)
  require **both** `ENVIRONMENT in {local, test}` **and** an explicit
  `CHUNK_INSPECTION_ENABLED=true` (default false, absent from deployed config);
  (3) refuse to start if the flag is true while `ENVIRONMENT` is `staging` or
  `production`; (4) never document or enable it for a deployed service — real
  inspection of non-approved documents in deployments waits for §1.5. Optional
  defense in depth: require a loopback client address, only after verifying
  proxy-header handling so a spoofed `X-Forwarded-For` cannot satisfy it.

### 1.7 Recommended access policy and acceptance tests (not implemented)

> **Superseded in part by §1.8**, which holds the final per-route policy and test list.

Policy: P1 approved public documents are served everywhere; P2 all else is
404 in staging/production; P3 local inspection requires the two-condition gate
in §1.6; P4 internal access requires §1.5; P5 decisions use live parent rows.

Acceptance tests (extending the ten cases in
`10D-endpoint-remediation-plan.md` §2): for chunk list, chunk search and
download — each state in §1.3 yields 404 and no signed URL is created; the
approved positive control succeeds; the app started with defaults and **no**
`ENVIRONMENT` variable denies non-approved documents; flag true with
`ENVIRONMENT=production` fails startup; no request header, query parameter or
body field changes the outcome; an unapproved document's existence is
indistinguishable from a missing one; logs contain no chunk text or signed URL.

### 1.8 Final route policy — PLANNED behavior (nothing below is implemented)

**Currently implemented [code]:** all three routes check existence only (§1.1).
Everything in this section is a proposal for a later, separately approved
implementation.

Environment states used by the policy:

- *production-like*: `ENVIRONMENT` is `staging` or `production`, **or is absent
  or unrecognized**. Missing is never treated as local. (Today `config.py:20`
  defaults to `"local"`, which hides absence; telling "explicitly set" from
  "defaulted" needs a code change — e.g. checking `model_fields_set` — or removing
  the default. Gated code change.)
- *explicit local/test*: `ENVIRONMENT` is `local` or `test` **and was set explicitly**.

| Route | Approved public document | Everything else (and all production-like cases) | Inspection exception |
|---|---|---|---|
| Chunk list `GET /api/document-extractions/{id}/chunks` | Returned only if the extraction is the document's current, `completed` extraction, belongs to the document, and live eligibility passes (active approval, not archived, `standard`, checksum matches). No flag required. | 404, identical to a missing extraction | `CHUNK_INSPECTION_ENABLED` under the local prerequisites below |
| Chunk search `.../chunks/search?q=` | Same predicate as list; the query only filters inside the already-eligible set | 404 (not an empty list — an empty list would reveal existence). No query is run for a denied extraction. | Same flag, same prerequisites |
| Signed download `GET /api/research-documents/{id}/download` | Signed URL only if: active approval, not archived, `standard`, stored-file checksum equals the approved checksum. Extraction state is irrelevant (the file, not its text, is served). 300 s expiry unchanged. No flag required. | 404; **no storage call is made**, so no signed URL exists | **None.** `CHUNK_INSPECTION_ENABLED` never applies to downloads. If local download inspection is ever needed it must be a separately named flag (e.g. `LOCAL_DOWNLOAD_INSPECTION_ENABLED`) with its own review, the same prerequisites and its own tests; the recommendation is not to build one (local work can use local fixtures). |

Public approved-document access never depends on any inspection flag. Internal
or restricted documents stay denied in every deployed environment until
verified identity and a document-level authorization rule exist (§1.5).

**Local inspection exception — prerequisites (all required).** A
`local`/`test` label, even with the flag set, is *not* evidence that a service
is reachable only locally. The evidence must be enforced behavior:

1. `ENVIRONMENT` explicitly set to `local` or `test` (not defaulted);
2. `CHUNK_INSPECTION_ENABLED=true`, default false, absent from `.env.example`'s
   deployed-facing guidance and from any deployment template;
3. the server is bound to a loopback address only — asserted at startup from
   the actual bind configuration where available, and re-checked per request
   (peer address is loopback) with proxy-forwarded headers *not* trusted;
4. no deployment-platform marker variables present (the list is established
   during deployment inspection — [UNVERIFIED]);
5. startup refuses to run with the flag on when any of 1–4 fails (fail closed,
   loud), and logs the effective policy without secrets.

How accidental deployed defaults stay safe: flag default false; absent
`ENVIRONMENT` is production-like (deny); a deployed flag without a loopback
bind fails startup; a client cannot supply any of the inputs above.

**Acceptance tests (later implementation).** For each of chunk list, chunk
search and download, unless noted:

- `ENVIRONMENT` missing => non-approved is 404; approved is served.
- `ENVIRONMENT=local` without the flag => non-approved is 404.
- Flag set with `ENVIRONMENT` missing => startup fails or inspection stays off.
- Flag set with `ENVIRONMENT=staging` or `production` => startup fails.
- Flag + explicit local but non-loopback peer => denied; spoofed
  `X-Forwarded-For`/`Forwarded` headers do not satisfy the check.
- Request-controlled inputs (query string, headers, cookies, body, path, `Host`,
  `Origin`) cannot change the decision.
- Every ineligible state returns 404 on all three routes: archived; superseded
  extraction; restricted; reclassified `standard`→`restricted` after approval and
  chunk creation; approval revoked; checksum mismatch; extraction `pending`,
  `processing`, `failed` or `needs_ocr`; extraction of a different document;
  never approved.
- Positive control: an approved, current, completed document is served.
- `CHUNK_INSPECTION_ENABLED` has no effect on download; denied download makes
  no storage call and returns no signed URL.
- Denial is indistinguishable from a missing resource (status and body).
- Logs and error bodies contain no chunk text, signed URL or filename.

### 1.9 Remaining anonymous API exposure — scoped (not an API-wide assessment)

Inspected [code]: `research_documents.py`, `document_extraction.py`,
`schemas/research_document.py`, `schemas/document_extraction.py`,
`document_extraction_service.enqueue_extraction` / `process_one`, and
`document_extraction_repository.create_pending`.

**Metadata routes** (`GET /api/research-documents`, `GET .../{id}`; adjacent:
`GET .../{id}/extractions`, `.../extractions/current`,
`GET /api/document-extractions/{id}`):

- Anonymous callers receive `id`, `issuer_id`, `security_id`, `document_type`,
  `title`, `description`, `original_filename`, `document_date`,
  `confidentiality_classification`, `uploaded_by`, `is_archived`, `archived_at`,
  `archived_by`, timestamps (the list adds issuer legal name and ticker).
  Extraction responses add status, counts, extractor versions, attempt count
  and a free-text `error_message`.
- Not returned: storage path, checksum, file bytes, chunk text.
- Potentially sensitive: titles, descriptions and filenames of *restricted*
  documents; the classification label itself (it enumerates which documents are
  restricted); `uploaded_by`/`archived_by` free text (may be names or emails);
  `error_message` content (its possible contents were not reviewed —
  [UNVERIFIED]); archived documents via `include_archived=true`. The list has no
  pagination or limit. Actual sensitivity depends on uploaded data
  ([UNVERIFIED]).
- Decisions needed: whether restricted documents' metadata is visible to
  anonymous callers (recommended: hidden, or fields reduced, in
  staging/production); whether the classification field and actor fields are
  returned anonymously; a page-size cap. Tests: anonymous list/detail exclude or
  redact restricted documents; no actor fields; pagination bounds.

**Process route** (`POST /api/research-documents/{id}/process`):

- Guards today [code]: 404 if the document does not exist, 409 if archived.
  Nothing else — no authentication, no rate limit, no per-document duplicate
  check (the only unique index on `document_extraction` covers the *current*
  row, not pending ones).
- Each call writes a new `document_extraction` row (`pending`) and an
  `audit_event` whose `user_id` is the client-supplied `requested_by` string
  (attribution can be forged).
- Downstream: the worker later claims each pending row (up to
  `MAX_EXTRACTION_ATTEMPTS = 3`), downloads the stored PDF from Supabase
  Storage (an external service call), parses it locally with PyMuPDF4LLM, and
  writes extraction and chunk rows. No LLM or paid API appears in this path
  [code]. So repeated anonymous calls can create unbounded database rows,
  storage reads and CPU/memory use, and pollute the audit trail.
- [UNVERIFIED]: deployment reachability, any upstream rate limiting or WAF,
  worker concurrency, and whether a worker is running in each deployment.
- Required before public use: deny or require authentication in
  staging/production; until then, de-duplicate pending work per document, cap
  rate, and ignore client-supplied `requested_by` (server-derived identity).
  Tests: N repeated calls create at most one pending row; forged
  `requested_by` is not recorded; denied calls write nothing.

Adjacent anonymous mutating routes also exist on the same router —
`POST /api/research-documents` (upload), `PATCH .../{id}` (metadata) and
`POST .../{id}/archive` — noted for completeness and **not assessed** here.

Accepting option B secures only the three content routes above. It does not
establish that the rest of the API is safe for public exposure.

## 2. Offline Alembic evidence — what it was and what it was not

### 2.1 Commands as run [prior report; consistent with files]

Working directory `backend/`; `DIRECT_DATABASE_URL` set process-locally to
`postgresql://offline@invalid.invalid/offline`; wrapper
`scratch/offline/run_offline.py` (which patches socket connect functions, then
calls `alembic.config.main`) with `-c scratch/offline/alembic.ini`:

1. `heads` — reported `0022 (head)`.
2. `upgrade 0020:0022 --sql` — exit 0, output `up.sql`.
3. `downgrade 0022:0020 --sql` — exit 0, output `down.sql`.

Both used explicit ranges. No online upgrade/downgrade, `current`, or Supabase
CLI was run.

### 2.2 Revision copies, and what is reproducible now

Scratch files **do exist** [file]: `alembic.ini`, `run_offline.py`, `script/`
(copy of `env.py`, `script.py.mako`, 20 versions, 2 drafts), `up.sql`,
`down.sql`, `up.err`/`down.err` (both empty). Compared by SHA-256 today
against the repository: `env.py` identical; all 20 `versions/*.py` identical;
drafts 0021 and 0022 identical. So the rendered SQL corresponds to the current
repository sources. **Not reproducible from the repo alone:** the scratch
`alembic.ini`, wrapper and directory live in the scratchpad (temporary); they
are not committed. Re-rendering would need them rebuilt; this follow-up did
not regenerate anything.

### 2.3 How the scratch path differs from the real migration path

| Aspect | Real repo path | Scratch path |
|---|---|---|
| `script_location` | `alembic/` (versions only; drafts unseen) | scratchpad dir with versions + drafts together |
| `alembic.ini` | repo file (post-write hooks, full logging config) | minimal ini written for the run |
| `env.py` | `alembic/env.py` | byte-identical copy; its `sys.path.append(...)` points at the scratch parent, so `app` imported via `prepend_sys_path = .` from `backend/` |
| Mode | online in practice (`run_migrations_online`) | offline (`run_migrations_offline`) only — the online branch (engine, `CREATE SCHEMA` + commit, version-table creation) was **never exercised** |
| Database URL | real `DIRECT_DATABASE_URL` | dummy string used only to select the dialect |

### 2.4 Credential isolation and socket guard — coverage and limits

- **Credentials:** no `backend/.env` existed [file]; the shell environment was
  checked by variable *name* for `DATABASE_URL`, `SUPABASE*`, and common
  vendor key names and none were set. The sole URL was the dummy. Credential
  values were never read or printed.
- **Socket guard:** replaced `socket.socket.connect`, `connect_ex` and
  `socket.create_connection` with functions that raise. **Covered:** TCP
  connection attempts made through those Python-level calls in that process.
  **Not covered:** DNS lookups (`getaddrinfo`), UDP `sendto`, subprocesses,
  native extensions that open sockets directly, other processes. It is a
  tripwire, not proof that no network mechanism could run. Stronger
  evidence is structural: offline mode in `env.py` never builds an engine.

### 2.5 What each kind of evidence supports

| Conclusion | Source review | SQL rendering | Model comparison | Needs live validation |
|---|---|---|---|---|
| Chain 0019→0020→0021→0022, one head | yes | yes | | |
| All created objects are `nexus`-qualified | yes | yes | | |
| Columns/nullability/CHECK/index names equal the ORM models | | | yes | |
| Downgrade drops only the four new tables and indexes | yes | yes | | |
| `vector` type and `vector_dims` resolve | | | | **yes** |
| Locks, durations, permissions, pgvector version | | | | **yes** |
| Rollback behavior on real data | | | | **yes** |
| Whether 0021/0022 were applied elsewhere | local refs only (no commit/branch/stash) | | | **yes** |

### 2.6 Qualifications to the packet's statements

**Foreign-key locks (packet M5).** Replace "short because the new tables are
empty" with: creating a foreign key takes a SHARE ROW EXCLUSIVE lock on the
*referenced* table, which waits behind in-flight writers and makes later
writers queue behind it. Affected existing objects: 0021 — `research_document`;
0022 — `research_document`, `document_extraction`, `document_chunk`,
`provenance` (plus the new tables). The new tables being empty keeps the
validation work trivial but does **not** bound the wait; a long transaction on
`provenance` or `document_extraction` (discovery, extraction worker) could
stall the migration and, behind it, ordinary writes. Mitigation is a
`lock_timeout`, a quiet window, and a live check for long-running
transactions — all [UNVERIFIED] until a live preflight.

**Transaction boundaries (packet §4 "a failed revision rolls back its own
transaction").** Correct that. PostgreSQL DDL is transactional, but the
boundary is set by Alembic: `env.py` does not set `transaction_per_migration`
[code], and the rendered SQL shows a single `BEGIN … COMMIT` around both
revisions. So `upgrade 0020:0022` in one invocation is **one** transaction
(a failure in 0022 also rolls back 0021 and the version update), while
`upgrade 0021` then `upgrade 0022` as separate invocations are separate
transactions. Exceptions [code]: the online branch of `env.py` runs
`CREATE SCHEMA IF NOT EXISTS nexus` and commits *before* migrations (not
relevant to these two revisions, which add no schema), and neither draft
contains non-transactional operations (no `CONCURRENTLY`, no `op.execute`).
Behavior over the real connection (pooler/direct endpoint) is [UNVERIFIED].

**Vector dimension changes (packet M7/dimension section).** Withdraw "a
fixed-width column cannot be changed in place" as a universal statement. More
accurately: the width is part of the column type; changing it is a schema
change whose practicality depends on the eventual contract. With **no rows**,
an `ALTER COLUMN … TYPE vector(n)` or drop/recreate may be cheap
[UNVERIFIED]. With rows, existing vectors from one model are not convertible
to another model's space, so the realistic paths are re-embedding, or a
model-documented truncation/normalization if the vendor's contract defines
one. The `dimension` column, the `CHECK (vector_dims(embedding) = dimension)`
and the (chunk, model, version) uniqueness would also need review, and
coexisting widths need separate columns/tables. The point stands that the
width should be settled before the first production rows exist.

**Schema scope (packet M2).** Distinguish *objects created or modified* from
*references resolved from other schemas*. Created/modified: `nexus.*` tables,
indexes, constraints, and one row in `nexus.alembic_version`. Referenced but
not owned: type `vector` and function `vector_dims()` (extension, location
[UNVERIFIED], created `WITH SCHEMA public` by 0001 [code]); `gen_random_uuid()`,
`clock_timestamp()` and the `~` operator (built in to `pg_catalog` on
supported PostgreSQL versions; the minimum live server version is
[UNVERIFIED]). "Nothing touches `public`" means nothing is *created* there.

### 2.7 Unqualified `vector` / `vector_dims` — dependency and correction strategy

Dependency [code]: 0022 emits `vector(1024)` and `vector_dims(embedding)`
unqualified; `env.py` deliberately sets no `search_path`; and the **runtime**
repository SQL also uses an unqualified `CAST(:embedding AS vector)`
(`document_chunk_embedding_repository.py:72`) under the app engine's
`search_path = nexus, public`. If the live extension is in `extensions`, both
migration and runtime writes would fail to resolve it; if it is in `public`,
both work.

Proposed order for later review (nothing edited now): (a) a read-only
preflight reads the extension's schema and the migration role's
`search_path`; (b) if resolution is not guaranteed, schema-qualify to the
verified schema in the `Vector` type's DDL, the CHECK expression and the
repository CAST, with a unit test asserting qualification; (c) if resolution
is proven for both migration and app roles, document that proof instead and
leave the SQL; (d) avoid `SET search_path` inside migrations, which the
repository already avoided for a documented reason (`env.py` comments).

### 2.8 0021 versus 0022

The dimension decision blocks **0022 only**. 0021 contains no vector type and
references only `nexus.research_document`, so it can be reviewed
independently. Recommendation: do **not** apply 0021 early absent a concrete
operational reason (nothing in production consumes the allowlist until 10D.3;
an earlier apply only adds a permanent table to a shared database). Neither
revision is authorized for application.

## 3. Action audit — reconciled

The completion report's audit row ("Network access or downloads: No (the docx
package was installed … during the earlier report step …)") mixed two
different sessions. Reconciled, by session:

| Session | Actions with network/download or install | Evidence |
|---|---|---|
| **Earlier report-generation sessions** (10D.1 and the 10D.2 local report) | `npm install docx` runs are visible: npm debug logs dated 2026-10-12 21:52 (42 registry fetches) and 2026-10-23 15:04 (21 fetches) local time, matching those reports' file times. | [file] `AppData/Local/npm-cache/_logs`. Not established: what instructions authorized them; those transcripts were not re-read. |
| **2026-11-01 validation/setup session** | (a) `winget` download and install of Python 3.12.10 and (b) `pip` install of project dependencies, both requested by that session's prompt. (c) `npm install docx@9` into the scratchpad at 23:54 local to build the first Word report: log `2026-11-02T04_54_25Z` shows 8 registry fetches; the preceding `npm root --global` log (04:54:09Z) shows none. | [file] logs and `pyvenv.cfg` times; (a)/(b) [prior report]. (c) was done to satisfy the user's "create a word doc" request; that prompt's own authorization text covered Python/pip/winget, not npm, so whether (c) was within the owner's intent is [DECISION], not a conclusion drawn here. |
| **2026-11-02 completion session** (network prohibited) | No install or download evidence: no npm log after 04:54:25Z; the completion report reused the already-installed package. Local checks (mypy, ruff, black, pytest) and Alembic rendering ran offline-by-design; only the Alembic runs had the socket tripwire. pip leaves no comparable log, so absence of pip activity is **not independently provable**. Claude Code's own model traffic is inherent to the session and not a repo action. | [file], [prior report] |
| **This follow-up** | None. Actions: read-only Git, file reads, SHA-256 comparisons, reading local npm log files, one whitespace edit, one new document. Nothing installed or removed. | this session |

Conclusion: the earlier "No" was not accurate as written; the accurate
statement is *no network use is evidenced in the 2026-11-02 completion
session, and one npm download occurred in the 2026-11-01 report-generation
step.* This is neither declared a violation nor a clean audit.

## 4. Exact local Git checkpoint proposal — NOT EXECUTED

Current state [git, re-read 2026-11-02]: branch `main`, HEAD
`b2a9f31f61d07ff4e159cfc101b17cc20f0ba831`, **0 staged**, 0 stashes,
6 modified + 50 untracked (the 49 earlier ones plus this addendum) =
**56 unique proposed paths**, numbered 1–56 below with no duplicates. This
table is the single authoritative inventory.
`.git/hooks` has no active `pre-commit` hook (the repo's hooks are configured
but not installed here), so no hook will run; the equivalent checks were run
manually on 2026-11-02 before documentation-only changes. If hooks are
installed later, the first run clones `pre-commit/pre-commit-hooks` from the
network. `core.autocrlf=true`, so LF→CRLF warnings are expected and harmless.

Content review (offline, values redacted): a pattern scan of all candidates for
key-like strings, JWTs, connection strings with embedded passwords, private
keys and assignments of secret-named variables returned no matches. A pattern
scan is not proof of absence; the diffs of the six tracked files were read
directly (enum additions, settings with `None`/false defaults, comment edits,
import lines, a ruff/black exclusion). `.env.example` contains variable names
with empty or placeholder values only. No `.env`, virtual environment,
`__pycache__`, build output or generated environment file is among the
candidates. Trailing whitespace: none after the SQL fix. Unrelated changes:
none found.

Origin legend: **A** = pre-existing 10D.2 implementation (files last modified
2026-10-23); **V** = A plus 2026-11-01 validation edits (Black reformat or
lint/type fixes); **C** = changed in the 2026-11-02 completion session;
**F** = this follow-up. For untracked files hunk-level separation is not
possible (whole files are added); mixed-purpose files are marked V.

| # | Path | Status | Origin | Rec. |
|---|---|---|---|---|
| 1 | `.env.example` | modified | A | include |
| 2 | `backend/app/config.py` | modified | A | include |
| 3 | `backend/app/core/types.py` | modified | A | include |
| 4 | `backend/app/extraction/pymupdf4llm_extractor.py` | modified | C (1-line comment removal) | include |
| 5 | `backend/app/models/__init__.py` | modified | A | include |
| 6 | `backend/pyproject.toml` | modified | A | include |
| 7 | `backend/alembic/drafts/0021_public_document_approval.py` | untracked | A | include (inert) |
| 8 | `backend/alembic/drafts/0022_document_embeddings.py` | untracked | A | include (inert; dimension unresolved) |
| 9 | `backend/alembic/drafts/README.md` | untracked | A | include |
| 10 | `backend/app/db/vector_type.py` | untracked | A | include |
| 11 | `backend/app/domain/document_chunk_embedding.py` | untracked | A | include |
| 12 | `backend/app/domain/document_embedding_job.py` | untracked | A | include |
| 13 | `backend/app/domain/embedding_call_log.py` | untracked | A | include |
| 14 | `backend/app/domain/public_document_approval.py` | untracked | A | include |
| 15 | `backend/app/embeddings/__init__.py` | untracked | A | include |
| 16 | `backend/app/embeddings/base.py` | untracked | A | include |
| 17 | `backend/app/embeddings/budget.py` | untracked | A | include |
| 18 | `backend/app/embeddings/dimensions.py` | untracked | A | include |
| 19 | `backend/app/embeddings/errors.py` | untracked | A | include |
| 20 | `backend/app/embeddings/factory.py` | untracked | A | include |
| 21 | `backend/app/embeddings/fake.py` | untracked | V | include |
| 22 | `backend/app/embeddings/fingerprint.py` | untracked | A | include |
| 23 | `backend/app/embeddings/pricing.py` | untracked | A | include |
| 24 | `backend/app/embeddings/processor.py` | untracked | V | include |
| 25 | `backend/app/models/document_chunk_embedding.py` | untracked | A | include |
| 26 | `backend/app/models/document_embedding_job.py` | untracked | A | include |
| 27 | `backend/app/models/embedding_call_log.py` | untracked | A | include |
| 28 | `backend/app/models/public_document_approval.py` | untracked | A | include |
| 29 | `backend/app/repositories/document_chunk_embedding_repository.py` | untracked | A | include |
| 30 | `backend/app/repositories/document_embedding_job_repository.py` | untracked | V | include |
| 31 | `backend/app/repositories/embedding_call_log_repository.py` | untracked | A | include |
| 32 | `backend/app/repositories/public_document_approval_repository.py` | untracked | A | include |
| 33 | `backend/app/retrieval/__init__.py` | untracked | A | include |
| 34 | `backend/app/retrieval/eligibility.py` | untracked | A | include |
| 35 | `backend/app/scripts/approve_public_document.py` | untracked | A | include |
| 36 | `backend/app/scripts/run_document_embedding_worker.py` | untracked | V | include |
| 37 | `backend/app/services/document_embedding_service.py` | untracked | A | include |
| 38 | `backend/tests/integration/embedding_db_guard.py` | untracked | A | include |
| 39 | `backend/tests/integration/test_document_embedding_repositories.py` | untracked | V | include |
| 40 | `backend/tests/unit/embedding_support.py` | untracked | A | include |
| 41 | `backend/tests/unit/test_document_embedding_worker.py` | untracked | V | include |
| 42 | `backend/tests/unit/test_embedding_domain_and_settings.py` | untracked | A | include |
| 43 | `backend/tests/unit/test_embedding_eligibility.py` | untracked | A | include |
| 44 | `backend/tests/unit/test_embedding_factory.py` | untracked | A | include |
| 45 | `backend/tests/unit/test_embedding_fingerprint.py` | untracked | A | include |
| 46 | `backend/tests/unit/test_embedding_migration_drafts.py` | untracked | V | include |
| 47 | `backend/tests/unit/test_embedding_pricing_budget.py` | untracked | A | include |
| 48 | `backend/tests/unit/test_embedding_processor.py` | untracked | A | include |
| 49 | `backend/tests/unit/test_embedding_provider_contract.py` | untracked | A | include |
| 50 | `docs/proposed/10D-database-approval-plan.md` | untracked | A | include |
| 51 | `docs/proposed/10D-endpoint-remediation-plan.md` | untracked | A | include |
| 52 | `docs/proposed/10D2-documentation-updates.md` | untracked | A | include (proposed doc updates; PLAN/BUILD_LOG/ADR **not** edited or marked complete) |
| 53 | `docs/proposed/10D2-migration-review-and-approval-packets-2026-11-02.md` | untracked | C | include (historical; superseded in part by this addendum) |
| 54 | `docs/proposed/10D2-offline-sql-0020-to-0022-REVIEW-ONLY-NOT-APPLIED-2026-11-02.sql` | untracked | C + F (whitespace) | **include (recommended)** — its header states REVIEW ONLY / NOT APPLIED, how it was rendered offline and from which files, that the 1024 width is provisional and that offline SQL is not live proof; no credentials or connection strings found; Alembic never scans `docs/proposed/` |
| 55 | `docs/proposed/ADR-021-document-embeddings.md` | untracked | A | include (proposal, not accepted) |
| 56 | `docs/proposed/10D2-addendum-clarifications-and-checkpoint-proposal-2026-11-02.md` | untracked | F | include |

Explicit exclusions: `backend/.venv`, every `__pycache__`, anything in
`C:\Users\saket\Documents\Nexus` (outside the repo), the scratchpad. Nothing
else in the repository is proposed.

Unresolved review concerns: (1) 0022's dimension is provisional and the
unqualified `vector` dependency is unverified, so the checkpoint commits
*drafts only*; (2) the review-only SQL artifact is a `.sql` file in the tree — it is
inert and prominently labelled, and is included (row 54); (3) V-files mix 10D.2
logic with later formatting/lint fixes and cannot be split by hunk; (4) per
`CLAUDE.md`, milestone completion requires `PLAN.md`/`BUILD_LOG.md` updates;
this checkpoint is explicitly **work in progress** and does not do them.

Branch: `milestone-10d2-document-embeddings`.

Commit message (complete; WIP; identical to the message file the command
sequence writes):

```
Milestone 10D.2 WIP: embedding foundation, disabled by default

Work in progress. This is NOT milestone completion.

- Embeddings are disabled by default (EMBEDDINGS_ENABLED=false); only a
  fake provider exists and no real vendor is chosen or implemented.
- Draft migrations 0021 and 0022 are in backend/alembic/drafts/ and are
  NOT applied and not discoverable by Alembic. The vector width (1024) is
  provisional; the embedding contract (vendor, model, dimension) is
  unresolved, so 0022 stays blocked.
- No existing endpoint is changed. Public-retrieval and endpoint
  restrictions are proposals only (10D.3 and later, separately gated).
- Includes review-only proposal documents and a review-only SQL rendering
  under docs/proposed/ (NOT APPLIED).
- PLAN.md, BUILD_LOG.md and ADR acceptance are intentionally not updated.

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
```

Attribution check: `CLAUDE.md` and `README.md` contain no commit-attribution
rule. History shows the `Co-Authored-By: Claude … <noreply@anthropic.com>`
convention (84 commits name "Claude Sonnet 5"; one names "Claude Sonnet 5.5").
The model that produced this work identifies itself as Claude Sonnet 5.5, so
that is the name used; no other model name is invented. Past commits are
authored by a different identity than the one in this machine's current Git
configuration, so the author name/email that will be recorded is a
**[DECISION]** for the owner to confirm before execution; the sequence prints
it and refuses to continue if either is empty.

Commands: this document intentionally carries **one** path inventory (the
table above) rather than a second copy of 56 paths. The complete, executable
PowerShell sequence is delivered with the approval request and is generated
from this table together with a manifest of the 56 files' Git blob ids as
reviewed, so execution can prove the content staged is the content reviewed.
Its required behavior:

- Confirms repository root, branch `main`, the full HEAD hash above, an empty
  index and the exact working-tree inventory (6 modified + 50 untracked, and
  nothing else); any difference stops it.
- Checks every native `git` exit code explicitly (no reliance on PowerShell's
  error handling) and stops on the first failure.
- Creates the branch only inside the approved execution; refuses if it exists.
- Stages exactly the 56 explicit paths (`git add -- <explicit list>`); never
  `git add .` or `-A`.
- Compares staged names to the approved list with consistent normalization
  (forward slashes, ordinal, case-sensitive), checks the 6/50 modified/added
  split, runs `git diff --cached --check`, prints the full staged diff for
  review, and checks that each staged blob equals the reviewed blob and that no
  unstaged change remains.
- Writes the message to a uniquely named new file (never overwrites), commits
  only after the checks pass, then verifies the commit's file list, hash,
  branch and a clean final status.
- **Single stop rule:** if anything is already staged, anything differs from
  this inventory, or any check fails, it stops and a revised proposal is
  returned. It never unstages, resets, stashes or cleans. The earlier
  suggestion to use a pathspec-limited commit in that case is withdrawn.
- Nothing is pushed; hooks are not installed, so none run; `--no-verify` is
  never used.

## 5. Decision gates (concise; reuse `10D-database-approval-plan.md`)

### 5.1 Embedding contract — still missing

Vendor and model id/version; the vendor's *documented* output dimension(s) and
whether truncation/Matryoshka widths are officially supported; the input-type
(document vs query) behavior; token limits and batch limits; pricing per
million tokens for `pricing.py`; the data-handling/retention terms for sending
public-document text to the vendor; the adapter work (a real
`EmbeddingProvider`, factory entry, rate-limit/auth error mapping, secret
variable name). 1024 stays **provisional** and 0022 **blocked**. Choosing a
model needs a separate authorization for *documentation research* (reading
vendor docs, no paid API call, no API key); a later, separate approval would be
needed for any real embedding call.

### 5.2 Integration environment — disposable isolated option

Policy exceptions needed: `CLAUDE.md` forbids local PostgreSQL, Dockerized
PostgreSQL and SQLite "in every environment"; `ADR-013` forbids a project
separate from the shared one (and `CLAUDE.md` says Nexus reuses an existing
project); the test guard also assumes a database URL. A disposable instance
needs a written exception (or a new ADR) naming the engine, version, host,
lifetime and owner.

| | Disposable isolated database | Shared Supabase `nexus` schema |
|---|---|---|
| Risk to shared data | None | Locks, connection use, permanent DDL on a shared database |
| Fidelity | Must match Supabase's pgvector version, extension schema, roles and search_path to prove anything | Highest |
| Policy | Needs exceptions to CLAUDE.md and ADR-013 | Allowed by policy, highest operational risk |
| Cost/effort | Provisioning and parity checking | Backup, coordination, windows |

Proposals for review (provision nothing): setup — an empty instance with
`vector` installed **in the same schema as the real project** and the same
non-superuser role; migration — baseline `0001–0020` then 0021, verify, then
0022 after the dimension decision; data — synthetic issuers/documents only,
fake provider; cleanup — destroy the instance, or in a shared schema
per-test rollback plus a post-run row-count diff; evidence — pytest output,
object lists before/after, `alembic_version`, the extension schema query.

### 5.2a Network isolation for a future integration run (corrects the earlier claim)

The earlier wording "a socket tripwire proves no outbound call" is
**withdrawn**. An application-level socket hook cannot prove network
isolation.

*Actual coverage and gaps* of a Python-level guard that raises on
`socket.connect`, `connect_ex` and `create_connection`: it catches
TCP connects made through those calls in the one process. It does not cover
DNS resolution (`getaddrinfo`), UDP, other processes or subprocesses, native
extensions that open sockets directly, a resolver or proxy outside the
process, or code that captured the original functions before the patch.
Connect calls to the *approved* database would also be blocked unless
allowlisted, so a naive hook either breaks the test or is bypassed.

*Allowed versus prohibited traffic.* Allowed: the specifically approved test
database endpoint (one named host and port, TLS) and nothing else.
Prohibited: any embedding vendor, any LLM, Supabase Storage, the web, and
the shared production database when the approved target is different.

*Proposed isolation strategy (nothing is installed or configured now):*

1. Layer 1 — environment-level egress control permitting only the named
   database endpoint (an OS or network firewall rule, or a disposable
   container/VM with an egress allowlist), owned and verified by the person
   who provisions the environment. This is the only layer that can restrict
   traffic from all processes.
2. Layer 2 — an in-process guard that allowlists the single approved
   `host:port`, rejects every other connect, and also guards DNS resolution;
   treated as a tripwire and a diagnostic, not as proof.
3. Layer 3 — no provider credentials in the environment (asserted by name),
   the factory configured for the fake provider only, and provider adapters
   absent.
4. Layer 4 — code and fixture inspection plus mocks: confirm the test and
   worker paths import no HTTP client or vendor SDK, and fail the run if one
   appears.
5. Evidence: egress-control rule listing, a pre/post connection log from the
   database side, and the inspection result.

*Checkable locally now (no authorization needed):* an import scan found no
HTTP client or vendor SDK in `app/embeddings`, `app/retrieval`,
`document_embedding_service`, the worker or approval scripts, or the embedding
repositories (the only keyword hits are `max_requests` budget counters);
`factory.py` builds only the fake provider, only when `ENVIRONMENT` is local
or test, and raises for any other provider name; the integration fixture
`db_session` wraps each test in an outer transaction that is rolled back, with
commits turned into savepoints. *Not yet checkable (needs later environment
authorization):* the egress rule, the database-side connection log, actual
rollback and leftover-row behavior on a live database, and the target's
extension and role setup.

*Corrections to earlier statements about the DB guard.* `embedding_db_guard.py`
does **not** currently refuse a non-allowlisted host. It requires the explicit
opt-in `NEXUS_ALLOW_EMBEDDING_DB_TESTS=1`, a configured `DATABASE_URL`, and the
presence of the four new tables, and otherwise skips. A host allowlist is a
proposed addition for the future environment gate, not an existing check.
Because the opt-in tests run against whatever `DATABASE_URL` points to, the
approval must name the target and prove `DATABASE_URL` points only there.

*Future test plan keeps (unchanged):* per-test parent-row rollback with an
assertion of zero leftover rows in every touched table; no commit outside the
test transaction (savepoint semantics checked); provider refusal; and a
pre/post row-count comparison for tables the test does not own.
*Evidence limitations:* sequences/identity counters and statistics may advance
despite rollback; locks and connection counts on a shared database cannot be
undone; the egress controls and database-side logs must be provided by the
environment owner.

### 5.3 Approvals — each separate, none granted

1. Provider documentation research (if needed).
2. Policy exception and environment provisioning/access.
3. Named-environment read-only preflight — not requested until the target and the exact permitted queries are concrete.
4. Each migration application (0021 and 0022 separately) and its prerequisites.
5. Exact integration test execution and cleanup scope.
6. Local Git checkpoint execution (§4). Never authorizes database actions.
7. Any later security implementation (including §1.5 authentication) or 10D.3 work.
