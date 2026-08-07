# Architecture Decision Records — Nexus Credit Intelligence

This file is an append-only log of significant architecture decisions. **History is
never rewritten.** If a decision is later reversed or superseded, a new ADR is added
that says so and references the ADR it supersedes — the original ADR stays, marked
`Superseded`.

Current architecture version: **1.0 (frozen)** — see `PLAN.md` § Architecture Change
Policy for the process required to change it.

Each record covers: context, decision, alternatives considered, tradeoffs,
consequences, and a recommendation for when to revisit it.

---

## ADR-001: Supabase-managed PostgreSQL instead of self-hosted/local Postgres

**Date:** 2026-08-04
**Status:** Accepted

**Context**
The original plan used SQLite via Drizzle for local POC simplicity. Requirements were
revised to require a real hosted Postgres reachable from every environment
(local dev, test, staging, production), with `pgvector` for embeddings and durable
storage independent of any single compute host.

**Decision**
Use Supabase-managed PostgreSQL only, in every environment. No local PostgreSQL
container, no PostgreSQL in Docker Compose, no SQLite anywhere, including local dev.

**Alternatives Considered**
- Self-hosted Postgres in Docker Compose for local dev, managed Postgres in prod —
  rejected: creates two schemas to keep in sync and a dev/prod parity gap.
- SQLite for the POC, migrate to Postgres later — rejected: `pgvector` and
  Postgres-specific features (full-text search, trigram, JSONB) are used from the
  start; migrating later would mean rewriting the data layer mid-project.

**Tradeoffs**
Vendor lock-in to Supabase accepted. Local development requires network connectivity
to Supabase (no fully offline dev loop). In exchange: one schema, one connection
string shape, real `pgvector`/`pg_trgm` behavior from day one, and no
local-vs-hosted Postgres version drift.

**Consequences**
- `DATABASE_URL` (pooled, runtime) and `DIRECT_DATABASE_URL` (direct, Alembic) both
  required in every environment's config.
- A separate Supabase project or schema is used for dev/test vs. staging/production
  where practical, so seed/test data never touches production tables.

**Future Revisit Recommendation**
Revisit only if Supabase's pricing, region availability, or `pgvector` feature
support becomes a blocker at production scale — not a POC-stage concern.

---

## ADR-002: Python/FastAPI/SQLAlchemy 2/Alembic backend on Railway, replacing Node/Hono/Drizzle

**Date:** 2026-08-04
**Status:** Accepted

**Context**
The initial brief specified Node.js/TypeScript/Hono/Drizzle/better-sqlite3. Revised
requirements specified Python 3.12/FastAPI/Pydantic 2/SQLAlchemy 2/Alembic hosted on
Railway, with credentials and feature flags held in Railway environment variables.

**Decision**
Backend is Python 3.12, FastAPI, Pydantic 2, SQLAlchemy 2, Alembic, deployed to
Railway with a `GET /health` endpoint for Railway's health check. Railway's
filesystem is never used for durable storage (it's ephemeral).

**Alternatives Considered**
- Keep Node/Hono — rejected per explicit requirement change.
- Django/DRF instead of FastAPI — not evaluated in depth; FastAPI's async-first
  design and native Pydantic 2 integration fit the provider-adapter/IO-heavy workload
  better and was the explicit requirement.

**Tradeoffs**
Full rewrite of the module tree and every code-level design decision made against the
Node stack. In exchange: FastAPI's async IO model suits many concurrent
throttled provider calls (SEC, OpenFIGI, FRED, CourtListener, TRACE) well, and
SQLAlchemy 2 + Alembic is a mature, well-understood migration story for Postgres.

**Consequences**
- All provider adapters, the entitlement engine, and the domain layer are
  implemented in Python, not TypeScript.
- Railway env vars are the credential/config source of truth in deployed
  environments; local dev uses a `.env` file (never committed).

**Future Revisit Recommendation**
No planned revisit. Would only be reopened if Railway itself became unsuitable
(cost, region, cold-start behavior) — a hosting decision, not a language decision.

---

## ADR-003: React/Vite/MUI/TanStack frontend on Vercel, replacing server-rendered Hono JSX

**Date:** 2026-08-04
**Status:** Accepted

**Context**
An earlier plan iteration considered Hono JSX server-rendered HTML to minimize moving
parts. Revised requirements specified a separately deployed React + TypeScript + Vite
+ Material UI + TanStack Query/Table frontend on Vercel.

**Decision**
Frontend is React/TypeScript/Vite/MUI/TanStack Query/TanStack Table, built and
deployed independently on Vercel, talking to the Railway backend over HTTPS via
`VITE_API_BASE_URL`. No server-rendered coupling between frontend and backend.

**Alternatives Considered**
- Hono JSX server-rendered HTML — rejected per explicit requirement change; also a
  weaker fit once the product scope grew to include a data-table-heavy Credit
  Universe screen, a dashboard with charts, and an AI assistant chat UI, all of
  which benefit from a real client-side app shell.

**Tradeoffs**
Two deployable units (Railway + Vercel) instead of one, and CORS configuration
(`CORS_ALLOWED_ORIGINS`, `FRONTEND_URL`) becomes a real concern. In exchange: frontend
and backend scale, deploy, and roll back independently, and MUI + TanStack Table give
a fast path to the sortable/filterable/paginated Credit Universe table this product
is built around.

**Consequences**
- CORS must be explicitly configured and kept in sync between the two deploys.
- The frontend has its own `.env.example` (`VITE_API_BASE_URL`).

**Future Revisit Recommendation**
No planned revisit.

---

## ADR-004: Explicit domain layer — providers never touch SQLAlchemy directly

**Date:** 2026-08-04
**Status:** Accepted

**Context**
Provider adapters (SEC EDGAR, OpenFIGI, FRED, CourtListener, FINRA TRACE, PACER, plus
five disabled licensed-vendor stubs) already carry significant responsibility:
throttling, retry-with-backoff, raw-response persistence, schema validation. Letting
them also own persistence logic risked tangling adapter code with ORM/session
concerns and making normalization untestable without a live database.

**Decision**
Fixed pipeline: External Provider → Provider DTO → Normalizer → Canonical Domain
Object → Repository → SQLAlchemy/Supabase Postgres. Provider modules produce DTOs and
canonical domain objects; only repository modules (`backend/app/repositories/**`)
open a SQLAlchemy session and write. API routes and the AI assistant's tools call
repositories, never the ORM directly.

**Alternatives Considered**
- Providers write directly via SQLAlchemy models — rejected: couples adapters to
  persistence, makes normalization hard to unit-test in isolation, and makes the
  "no code path renders a value without provenance" guarantee harder to audit since
  writes could happen from many places.

**Tradeoffs**
More files and an extra layer of indirection per data type. In exchange:
normalization logic is testable without a database, persistence is centralized and
auditable, and background jobs (Phase 2, §23.5) can reuse the exact same pipeline
instead of a parallel write path.

**Consequences**
- Enforced by code review and directory convention in this POC, not an automated
  lint rule (tracked as TD-001 in `PLAN.md` § Technical Debt).
- Every new data source added later (Bloomberg, Octus, S&P Global, once licensed)
  follows the same pipeline shape.

**Future Revisit Recommendation**
Revisit if TD-001 (no automated enforcement) causes an actual violation in code
review — at that point, add an import-linter/ruff boundary rule rather than relying
on convention indefinitely.

---

## ADR-005: `freshness` computed at read time, not persisted as a stored column

**Date:** 2026-08-04
**Status:** Accepted

**Context**
An earlier `provenance` schema stored `freshness` (`live`/`cached`/`stale`) as a
column set at write time. This value silently goes stale itself — a row written as
`live` stays labeled `live` forever unless something actively recomputes it.

**Decision**
`provenance` stores `retrieved_at` only. `freshness` is exposed as a computed API
property, derived at read time from `retrieved_at` plus a per-provider TTL policy
(`backend/app/core/freshness.py`). If a historical snapshot of freshness-at-a-point-
in-time is ever needed, it is stored under the explicit name `freshness_at_ingestion`,
never reusing the `freshness` name.

**Alternatives Considered**
- Keep `freshness` as a stored column, recompute via a background job — rejected: adds
  a background dependency for a value that's cheap to compute on read, and risks the
  exact staleness bug the field is supposed to prevent.

**Tradeoffs**
Every read path that displays freshness must compute it (a cheap timestamp
comparison), rather than reading a precomputed field. In exchange: the value shown is
always actually correct as of the request, with no possibility of a stale
"freshness" flag.

**Consequences**
- `provenance.freshness` does not exist as a database column.
- TTL policy per provider lives in `backend/app/core/freshness.py`, documented in
  `PLAN.md` §16.

**Future Revisit Recommendation**
Revisit only if per-request freshness computation becomes a measurable performance
problem at scale — not expected in this POC.

---

## ADR-006: Normalized `calculation_input` join table replaces `calculation.input_provenance_ids` JSONB array

**Date:** 2026-08-04
**Status:** Accepted

**Context**
An earlier `calculation` schema stored `input_provenance_ids` as a JSONB array of
provenance IDs that fed a derived value (e.g. which trades fed a VWAP). This supports
display but not referential integrity or lineage queries (e.g. "which calculations
would be invalidated if this specific provenance record changed").

**Decision**
Replace the JSONB array with a normalized `calculation_input` join table:
`calculation_id`, `provenance_id`, `input_role` (nullable), `sequence_number`
(nullable), composite primary key on `(calculation_id, provenance_id)`.

**Alternatives Considered**
- Keep the JSONB array — rejected: no foreign-key integrity, no efficient
  "calculations affected by provenance X" query without scanning/parsing JSON.

**Tradeoffs**
One more table and one more join for calculation-lineage reads. In exchange: real
referential integrity, and lineage queries become ordinary SQL joins instead of JSONB
array scans.

**Consequences**
- `calculation` no longer has an `input_provenance_ids` column.
- Any calculation with ordered inputs (e.g. time-ordered trades feeding a VWAP) uses
  `sequence_number`; inputs with a specific role (e.g. "trade_price" vs.
  "trade_size") use `input_role`.

**Future Revisit Recommendation**
No planned revisit.

---

## ADR-007: `admin_upload` as a distinct provenance provider/ingestion channel

**Date:** 2026-08-04
**Status:** Accepted

**Context**
The original PACER-handling design set `provenance.provider = pacer` on every
manually uploaded court document (uploaded by an admin when RECAP had no copy
available). This falsely implies the system retrieved the document through a real
PACER integration, when in this POC no real PACER retrieval ever happens.

**Decision**
Add `admin_upload` as a valid `provenance.provider` value, used for every manually
uploaded document regardless of what it actually originated from. Add
`provenance.original_source` (`pacer`\|`courtlistener`\|`issuer_site`\|`other`),
`source_attested_by`, and `source_attested_at` to record the admin's claim about
where the document actually came from, explicitly and traceably.
`provider = pacer` is reserved exclusively for documents the system actually
retrieves through a real, future PACER integration.

**Alternatives Considered**
- Keep `provider = pacer` for all court documents regardless of retrieval method —
  rejected: misrepresents provenance, which violates the project's core "every value
  carries accurate provenance" rule.
- Add a boolean `is_admin_uploaded` flag instead of a distinct provider value —
  rejected: `provider` is already the field every other part of the system reads to
  understand ingestion channel; a separate boolean would need to be checked
  everywhere `provider` currently is, doubling the surface for the same information.

**Tradeoffs**
Slightly more schema (three new nullable columns on `provenance`). In exchange: no
provenance record ever falsely claims a retrieval channel that didn't happen.

**Consequences**
- `docket_document` (and any future `research_document` admin upload) always uses
  `provider = admin_upload` when the system didn't fetch the document itself.
- `PACER_ENABLED` stays `false` in this POC; `PacerProvider` exists as an interface
  only (see `PLAN.md` §15).

**Future Revisit Recommendation**
When a real PACER integration is eventually built (see `PLAN.md` §8, future
production requirements), confirm that retrieval path sets `provider = pacer`
directly and does not route through `admin_upload`.

---

## ADR-008: Credit Universe is the primary application workflow

**Date:** 2026-08-04
**Status:** Accepted

**Context**
Early planning treated the issuer detail / source-lineage view as the primary
surface, reflecting the original brief's emphasis on provenance. The actual first
stated business need (from the CFO) is a screenable universe of credits that reduces
manual work for investment professionals.

**Decision**
`CreditUniversePage.tsx` is the landing page after login/demo entry. It supports a
"Loan Universe" filter/view as a filter state within Credit Universe, not a separate
page, since the loan-level data is largely synthetic (no public source) while bonds
are real — the real/synthetic boundary is a filter, not a hidden distinction.

**Alternatives Considered**
- Keep issuer/lineage as the landing page, add Credit Universe as a secondary screen
  — rejected: doesn't reflect the actual primary user need (screening), and buries
  the feature the CFO specifically asked for.
- Separate "Loan Universe" as its own top-level page — rejected: would obscure that
  loan pricing is synthetic-only in this POC; keeping it as a filter within Credit
  Universe keeps the synthetic-data labeling visible in context.

**Tradeoffs**
The issuer/lineage page (originally central) becomes a drill-down destination rather
than the front door. In exchange: the product's primary workflow matches the actual
stated business need from day one.

**Consequences**
- Build order (`PLAN.md` §18) surfaces a working Credit Universe page by milestone 4,
  before most provider adapters beyond SEC are even built.
- Every Credit Universe column still carries the same provenance/classification
  requirements as the rest of the app — moving it to the front door didn't relax the
  provenance-first rule.

**Future Revisit Recommendation**
No planned revisit.

---

## ADR-009: AI Research Assistant restricted to a fixed typed tool set — no arbitrary SQL

**Date:** 2026-08-04
**Status:** Accepted

**Context**
The AI Research Assistant needs to answer analyst questions across issuers,
securities, capital structure, financials, TRACE history, filings, dockets, research
notes, documents, watchlists, and alerts — a broad enough surface that "let the model
write SQL" would be the fastest implementation path, but also the one with the
weakest safety guarantees (entitlement bypass, unbounded query cost, data exposure).

**Decision**
The assistant calls a fixed set of typed tools (`search_credit_universe`,
`get_issuer`, `get_instrument`, `get_capital_structure`, `get_financial_facts`,
`get_trace_history`, `get_sec_filings`, `get_court_dockets`, `get_research_notes`,
`get_documents`, `get_watchlists`, `get_alerts`), each a thin wrapper over an
existing repository/service call. No LLM-authored SQL ever executes.

**Alternatives Considered**
- LLM-authored SQL against a read replica — rejected: even read-only, this bypasses
  the entitlement/`policy_check` gate that every other access path in the system goes
  through, and makes "did this answer only use permitted data" much harder to audit.

**Tradeoffs**
Every new question type the assistant should answer requires a new tool (or a new
parameter on an existing one) rather than "just asking the model to query for it."
In exchange: the assistant's access is exactly as broad as a human user's existing
read APIs, no broader, and every tool call can be gated by `policy_check` before its
result reaches the prompt.

**Consequences**
- `backend/app/ai/tools/` mirrors the repository layer, one thin wrapper per tool.
- Adding assistant capability is a backend change with a repository underneath it,
  not a prompt-engineering-only change.

**Future Revisit Recommendation**
No planned revisit; this constraint is treated as a security boundary, not a
convenience tradeoff to relax later.

---

## ADR-010: `LLMProvider` protocol abstraction; Anthropic implemented first

**Date:** 2026-08-04
**Status:** Accepted

**Context**
Anthropic (Claude) is the default and only LLM vendor needed for this POC, but the
application shouldn't hard-depend on the Anthropic SDK directly, since production use
may eventually need OpenAI, Azure OpenAI, or a self-hosted Ollama model — and chat
completion and embeddings may end up sourced from different vendors.

**Decision**
Define an `LLMProvider` Protocol (`complete`, `call_tools`, `create_embeddings`).
Implement `AnthropicProvider` now; stub `OpenAIProvider`, `AzureOpenAIProvider`,
`OllamaProvider` as interfaces only. `LLM_PROVIDER` env var selects the
implementation at startup; selecting an unimplemented provider raises a clear config
error rather than silently falling back to Anthropic.

**Alternatives Considered**
- Call the Anthropic SDK directly wherever LLM calls are needed — rejected: would
  require a broader refactor later to add a second vendor, and the entitlement/gate
  logic (`llm_gate.py`) is cleaner when it wraps a stable interface rather than a
  vendor SDK's specific shape.

**Tradeoffs**
More upfront structure (a Protocol + a factory) for a POC that only needs one
implementation right now. In exchange: adding a second vendor later is a new class,
not a refactor of every call site.

**Consequences**
- `backend/app/ai/providers/base.py` defines the Protocol; `factory.py` resolves
  `LLM_PROVIDER` to a class.
- Embeddings (`create_embeddings`) are a separate method from chat/tool-calling
  (`complete`/`call_tools`) on the same Protocol, so they can be backed by different
  vendors later without a Protocol change.

**Future Revisit Recommendation**
Revisit when a second provider is actually implemented — confirm the Protocol shape
still fits a real second vendor's constraints (e.g. Ollama's lack of hosted tool-
calling in some configurations) rather than assuming it does.

---

## ADR-011: Phase 2 architecture documented but explicitly deferred out of Version 1 scope

**Date:** 2026-08-04
**Status:** Accepted

**Context**
Five significant future capabilities were identified during architecture discussion:
a canonical `CreditEvent` stream, Time Machine / as-of historical queries, a Portfolio
module, Data Quality scoring, and background job scheduling. Each has real
architectural implications for the current schema (e.g. as-of queries need
`valid_from`/`valid_to` on mutable tables) even though none is needed for Version 1.

**Decision**
Document all five under `PLAN.md` §23 (Future Architecture / Phase 2 Extensions),
explaining how the current V1 architecture already supports or would need to extend
to support each one — without implementing, scheduling, or adding any of them to the
Version 1 build order or module list.

**Alternatives Considered**
- Implement minimal versions now "since we're already touching this area" —
  rejected: explicitly contradicts the instruction to keep V1 scope frozen, and risks
  half-finished features that don't meet the project's own completion-criteria bar.
- Don't document them at all, revisit from scratch later — rejected: several V1
  decisions (e.g. `provenance.as_of_date` vs. `retrieved_at` bitemporal split) were
  made partly *because* they make Phase 2 easier; documenting the connection now
  preserves that reasoning for whoever picks up Phase 2 later.

**Tradeoffs**
`PLAN.md` carries a substantial "not implemented" section that could be mistaken for
scope creep if not clearly labeled. Mitigated with an explicit banner in the file's
intro, a dedicated §23 heading, and a "What I will NOT do" bullet barring any Phase 2
item from this build.

**Consequences**
- No `credit_event`, `position`, `data_quality_score` tables, `as_of_date` repository
  parameters, or job scheduler exist in Version 1.
- Phase 2 work, when it starts, begins from `PLAN.md` §23 plus a new ADR describing
  the actual implementation decision at that time.

**Future Revisit Recommendation**
Revisit §23 in full once Version 1's completion criteria (§20) are met and Phase 2
work is actually scheduled — treat it as a starting proposal, not a locked spec, since
it was written before any V1 implementation experience existed.

---

## ADR-012: Three-document governance system adopted; architecture frozen at v1.0

**Date:** 2026-08-04
**Status:** Accepted

**Context**
With architecture and scope now settled (§1–23 of `PLAN.md`), the project moves from
open-ended design discussion into implementation. Without a formal process, there's a
real risk of architecture drifting silently during implementation (a "just this once"
shortcut that never gets reconciled with the documented plan) and of losing the
reasoning behind decisions once the conversation that produced them scrolls out of
context.

**Decision**
Adopt three synchronized documents: `PLAN.md` (current architecture + status,
non-chronological), `BUILD_LOG.md` (append-only chronological engineering journal),
`ARCHITECTURE_DECISIONS.md` (append-only ADR log, this file). Freeze architecture at
Version 1.0. Any genuinely necessary architecture change during implementation must
stop work, be explained (reason, tradeoffs, roadmap impact, alternatives), get a new
ADR, and get a version bump — before implementation continues on the affected path.
Every milestone must satisfy sixteen gates (`PLAN.md` § Implementation Rules) before
the next one begins, including updating all three documents.

**Alternatives Considered**
- Single `PLAN.md` covering both architecture and chronological history — rejected:
  explicitly identified as a failure mode ("PLAN.md must NOT become a chronological
  engineering log") since it makes "what's the current state" and "what happened and
  when" both harder to find.
- No formal gate before starting the next milestone — rejected: given the project's
  own provenance-first standard for data, it would be inconsistent to hold
  implementation history to a lower bar than the data the app displays.

**Tradeoffs**
Real process overhead per milestone (test/lint/build/commit/three-document-update
before moving on). In exchange: at any point, `PLAN.md` § Project Status answers
"where are we" accurately, `BUILD_LOG.md` answers "how did we get here," and
`ARCHITECTURE_DECISIONS.md` answers "why was it built this way" — without needing to
reconstruct any of that from conversation history or commit archaeology.

**Consequences**
- `PLAN.md` § Project Status, § Milestone Status, § Technical Debt, and § Known
  Issues are living sections updated every milestone, not written once.
- This ADR file already contains ADR-001 through ADR-011 above, backfilled from the
  planning conversation that preceded this governance system, so the historical
  record starts complete rather than at zero.

**Future Revisit Recommendation**
Revisit the process itself (not the architecture) if the sixteen-gate checklist
proves too heavy for the actual pace of a solo/small-team POC — that would be a
process ADR, not an architecture ADR, and wouldn't require an architecture version
bump.

---

## ADR-013: Shared Supabase project, isolated via the `nexus` Postgres schema

**Date:** 2026-08-05
**Status:** Accepted

**Context**
ADR-001 established Supabase-managed Postgres in every environment and noted "a
separate Supabase project or schema is used for dev/test vs. staging/production
where practical," implicitly assuming Nexus would eventually get project(s) of its
own. Before Milestone 2, the project owner directed that Nexus instead reuse an
existing Supabase project that already supports another application, rather than
provisioning a new one — for cost/operational reasons outside this codebase.

**Decision**
Nexus reuses the existing Supabase project. Isolation is enforced at the Postgres
schema level: every Nexus-owned object (tables, indexes, sequences, enum types
where practical, views, and the Alembic version table) lives in a dedicated
`nexus` schema, never in `public` or any schema belonging to the other
application. Concretely:
- `Base.metadata` (`backend/app/db/base.py`, `NEXUS_SCHEMA` constant) defaults to
  schema `nexus`, so every SQLAlchemy model is schema-qualified by construction.
- `backend/alembic/env.py` runs with `include_schemas=True`,
  `version_table_schema="nexus"`, and an `include_name` filter that restricts
  reflection/autogenerate comparison to the `nexus` schema only — Alembic never
  reflects, diffs against, or proposes migrations for the other application's
  objects.
- The connection's `search_path` is set to `nexus, public` (`connect_args` on both
  the app engine and the Alembic migration engine) as a second layer, never relied
  on alone for correctness.
- The initial migration (`0001_enable_extensions`) creates the `nexus` schema
  (`CREATE SCHEMA IF NOT EXISTS`) alongside the `vector`/`pg_trgm` extensions.
  Extensions are database-wide and may be depended on by the other application, so
  migrations only ever `CREATE EXTENSION IF NOT EXISTS` — never drop, downgrade, or
  relocate one, including on downgrade. Downgrade of `0001` drops only the (by then
  empty) `nexus` schema, without `CASCADE`.
- The `nexus` schema is not exposed to PostgREST/the Supabase Data API; the
  frontend continues to reach Nexus data only through FastAPI (§3 domain-layer
  boundary is unaffected).
- Environment variable names follow the existing application's convention rather
  than Nexus's originally planned names: `SUPABASE_SERVICE_KEY` (not
  `SUPABASE_SERVICE_ROLE_KEY`), plus a new `SUPABASE_ANON_KEY` for future
  frontend/RLS use. `DATABASE_URL`, `DIRECT_DATABASE_URL`, and
  `SUPABASE_STORAGE_BUCKET` are unchanged.

**Alternatives Considered**
- Provision a dedicated Supabase project for Nexus (the original ADR-001
  assumption) — rejected per explicit direction to reuse the existing project;
  also would have meant carrying two sets of Supabase credentials/projects for no
  benefit at this POC's stage.
- Rely on the Postgres role's grants alone (a role scoped to `public`) without a
  distinct schema — rejected: a schema is a stronger, more legible isolation
  boundary than role grants alone, is what Alembic's `version_table_schema`/
  `include_schemas` machinery is designed around, and makes "list everything
  Nexus owns" a one-line `information_schema` query scoped to `nexus`.
- Prefix Nexus table names (e.g. `nexus_issuer`) inside `public` instead of using a
  real schema — rejected: namespacing by naming convention is exactly the kind of
  isolation this project's own provenance/entitlement rules would never accept for
  data; it also does nothing to stop an autogenerate diff from touching the other
  application's tables, which a schema-scoped `include_name` filter does prevent.

**Tradeoffs**
Every Nexus model, query, and migration must be schema-aware (schema-qualified
metadata, `include_name` filtering, explicit `nexus.*` qualification in raw SQL)
rather than assuming a project boundary does the isolation work for free. In
exchange: no second Supabase project to provision, fund, or keep credentials for;
and schema-level isolation is provably auditable (`information_schema` scoped to
`nexus`) rather than resting on "we just didn't create anything in the wrong
project."

**Consequences**
- `backend/app/config.py`, `.env.example`, `README.md`, and `PLAN.md` §2/§19 use
  the existing application's env var names (`SUPABASE_ANON_KEY`,
  `SUPABASE_SERVICE_KEY`) instead of Nexus's originally planned
  `SUPABASE_SERVICE_ROLE_KEY`.
- `backend/alembic/versions/0001_enable_extensions.py`'s downgrade no longer drops
  the `vector`/`pg_trgm` extensions (they may be shared); it only drops the
  (by-then-empty) `nexus` schema.
- Live Supabase validation (KI-001) now additionally requires proving schema
  isolation end-to-end (schema exists, `alembic_version` is inside it, no Nexus
  object lands in `public`, no existing non-Nexus table is touched) before
  Milestone 2 begins.
- Supabase Storage is deferred (unchanged from prior plan) but, when enabled, must
  use a new private bucket — never the other application's bucket.

**Future Revisit Recommendation**
Revisit only if the shared project's resource limits, another application's schema
changes, or a compliance requirement (e.g. a hard data-residency/tenant-isolation
mandate) make schema-level isolation insufficient and a dedicated project becomes
necessary — at that point, migration is a `pg_dump`/`pg_restore` of the `nexus`
schema into a new project, not a code rewrite, since every Nexus object is already
schema-qualified.

---

## ADR-014: Domain-layer implementation conventions (Pydantic domain objects, function-style repositories, text+CHECK over native enums)

**Date:** 2026-08-06
**Status:** Accepted

**Context**
Milestone 2 (`provenance`, `calculation`, `calculation_input`, `raw_provider_payload`,
`data_entitlement`) is the first code to actually populate `backend/app/domain/`,
`backend/app/models/`, and `backend/app/repositories/` (§3, §17). PLAN.md fixes
*what* these tables and objects contain but not *how* they're implemented in Python —
four implementation-shape decisions had to be made that every later milestone's
canonical entities (issuer, security, financial_fact, and eventually Bloomberg/S&P
Global/Markit/Octus-backed data) will also follow, so they're recorded here rather
than left as an unstated convention only visible by reading Milestone 2's code.

**Decision**
1. **Canonical domain objects are frozen Pydantic 2 models, not dataclasses.**
   Every `app/domain/**` object (`Provenance`, `RawProviderPayload`,
   `DataEntitlement`, and their `*Create` variants) is a `BaseModel` with
   `model_config = ConfigDict(frozen=True)`. Enum-shaped fields (`provider`,
   `classification`, `transformation`, `environment`, etc.) are typed with the
   `StrEnum` classes in `app/core/types.py`, not bare `str`. `model_validator`
   enforces cross-field invariants (e.g. `calculation_id` set iff
   `transformation == "calculated"`) at construction time, before any I/O.
2. **ORM enum-shaped columns are `Text` + `CheckConstraint`, never native Postgres
   `ENUM` types.** PLAN.md's data model tables explicitly type these fields
   `text`. A native enum type turns "add a new provider" into a schema-altering
   `ALTER TYPE`; a `CheckConstraint` built from the same `app/core/types.py` enum
   is exactly as strict and is an ordinary migration to extend. The Pydantic
   validation in (1) is the primary defense; the DB constraint is deliberate
   defense-in-depth for any write path that bypasses the domain layer (verified
   directly in `tests/integration/test_provenance_repository.py`, which
   constructs an invalid ORM row directly to prove the constraint fires
   independently of Pydantic).
3. **Repositories are module-level functions taking `db: Session` as their first
   argument, not a stateful repository class.** `app/repositories/provenance_repository.py`
   and its siblings export plain functions (`create_provenance`, `get_provenance`,
   ...) that accept and return domain objects only, never a SQLAlchemy model.
   Every function `flush()`s but never `commit()`s — `app/db/session.py`'s
   `get_db()` was updated to commit once at the end of a successful request (or
   roll back on exception), so a single request/unit of work can span several
   repository calls atomically. A class with one `db` attribute and one-line
   delegating methods would add ceremony without changing behavior; plain
   functions are simpler and equally mockable/testable.
4. **Circular foreign keys use `ForeignKey(..., use_alter=True, name=...)`, and
   the corresponding Alembic migration must hand-verify the emitted DDL.**
   `provenance.raw_payload_id` and `raw_provider_payload.provenance_id`
   reference each other by design (PLAN.md 4.1/4.4). Autogenerate's plain
   output embedded the `use_alter=True` constraint inline inside
   `op.create_table(...)` for `raw_provider_payload` — compiling that DDL
   directly (`CreateTable(...).compile()`) proved SQLAlchemy's compiler silently
   *drops* any `use_alter=True` constraint from an inline `CREATE TABLE`
   statement, and autogenerate did not also emit the separate `ALTER TABLE`
   that constraint needs, meaning the FK would never have been created at all.
   `backend/alembic/versions/0002_provenance_entitlement_foundation.py` was
   hand-corrected: the inline FK was removed, and an explicit
   `op.create_foreign_key(...)` was added after both tables exist, with the
   matching `op.drop_constraint(...)` first in `downgrade()`. Confirmed against
   the live database (`alembic upgrade head` / `downgrade 0001` / `upgrade
   head` round-trip, then querying `pg_constraint` directly) rather than trusted
   on autogenerate's output alone.

**Alternatives Considered**
- Plain `dataclasses` for domain objects instead of Pydantic — rejected:
  Pydantic 2 is already a first-class project dependency (`config.py`), and its
  validators give real, fail-fast correctness at the normalizer/repository
  boundary (exactly where a malformed canonical object would otherwise silently
  reach the database) for effectively no extra dependency cost.
- Native Postgres `ENUM` types for `provider`/`classification`/etc. — rejected:
  contradicts PLAN.md's explicit `text` typing and makes adding a fourteenth,
  fifteenth, ... provider (an expected, frequent event given the target
  integration list: Bloomberg, S&P Global, Markit, Octus, FRED, SEC,
  CourtListener, TRACE) a schema-altering operation instead of an ordinary
  migration.
- Class-based repositories (`class ProvenanceRepository: def __init__(self, db)`)
  — rejected as unnecessary ceremony for this POC's needs; revisit only if a
  real need for swappable repository implementations (not just testability,
  which plain functions already provide) emerges.
- Trusting Alembic autogenerate's output verbatim for the circular FK — rejected
  after directly proving (by compiling the DDL) that the naive output would
  have silently produced a table with a missing constraint; a migration that
  "runs successfully" but silently omits a constraint is worse than one that
  fails loudly, since nothing would have surfaced the gap until a bad write
  succeeded that should have been rejected.

**Tradeoffs**
More boilerplate per canonical entity (a `*Create` Pydantic model, an ORM model
with `CheckConstraint`s duplicating the same enum values, and a repository module
with explicit `_to_domain` mapping functions) than a thinner approach (e.g.
dataclasses with no validation, or exposing ORM models directly to callers). In
exchange: every future canonical entity gets fail-fast validation, a
DB-independent domain layer that's trivially unit-testable, and a persistence
layer that can never silently accept or emit an ORM object to code outside
`app/repositories/**`.

**Consequences**
- `app/core/types.py` is the single source of truth for every enum value used in
  a `provenance`-family CHECK constraint or Pydantic field; a new provider or
  classification value is added there once and both layers pick it up.
- Every future `app/models/**` file that declares a circular or otherwise
  order-sensitive FK must be paired with a hand-verified (not blindly
  autogenerated) migration, per point 4 above.
- `app/repositories/**` functions are the only sanctioned way to read or write
  these tables; `app/api/routes/**` and future `app/ai/tools/**` call them
  directly, never the ORM.

**Future Revisit Recommendation**
Revisit the function-vs-class repository choice only if a concrete need for
swappable/mockable repository implementations arises (e.g. contract testing
against multiple backends) — not anticipated for this POC. Revisit the
text+CHECK vs. native enum choice only if constraint-based validation is proven
too slow at a row count this project isn't expected to reach.

---

## ADR-015: A second provider identifying a more specific entity creates a new row, not a mixed-provenance enrichment of an existing one

**Date:** 2026-08-06
**Status:** Accepted

**Context**
`security` (PLAN.md §4.5) carries a single `provenance_id` per row, not
per-field provenance (Technical Debt TD-007, recorded in Milestone 4).
Milestone 4 predicted TD-007 would need resolving in Milestone 5, once the
OpenFIGI adapter had a concrete case to attribute individual fields
(`cusip`/`isin`/`figi`) to a different provider than the rest of an existing
row. That case arrived: Milestone 4 already created one `security` row for
Apple Inc. representing SEC EDGAR's aggregate long-term-debt figure (no
CUSIP/ISIN/FIGI/maturity/coupon — a real API limitation, TD-008). Milestone
5's OpenFIGI adapter then identified five real, *specific* Apple bond issues
(each with its own real FIGI and maturity/coupon). The naive move — set
`figi`/`maturity_date`/`coupon` directly on the existing SEC-sourced row —
was rejected before being implemented: that row's `description` and
`amount_outstanding` describe Apple's whole aggregate balance-sheet debt
figure, not any one of these five specific bonds. Attaching one specific
bond's FIGI to it would assert "this aggregate figure *is* this specific
bond," which is false, and would misattribute the fact under a
`provenance_id` that in reality only vouches for the SEC-sourced fields.

**Decision**
When a provider identifies an entity that is genuinely distinct from an
already-existing row (not the same fact re-observed, but a more specific or
different real-world thing), it becomes a **new** canonical row, entirely
sourced from that provider — never a partial-field write onto an existing
row whose `provenance_id` only covers a different provider's facts. A
`security` row's single `provenance_id` remains correct precisely because
every field on that row traces to the same ingestion event. This is a
narrower, immediately-actionable version of the eventual TD-007 fix
(per-field provenance) that requires no schema change: it avoids the
mixed-provenance problem instead of solving it.

**Alternatives Considered**
- Implement full per-field provenance now (a `security_field_provenance`
  join table, analogous to `calculation_input`, PLAN.md §4.3) — rejected for
  Milestone 5: it's real, necessary work for the case TD-007 actually
  describes (attributing *different fields of the same real-world
  instrument* to different providers), but that case didn't arise this
  milestone. Building the join table now, with no real caller needing
  multiplicity, would repeat the exact mistake ADR-014 warned against
  (speculative infrastructure with nothing to validate its shape against).
- Overwrite the existing aggregate row's `cusip`/`isin`/`figi`/
  `maturity_date`/`coupon` fields with one arbitrarily-chosen OpenFIGI bond's
  values — rejected: factually false (the aggregate figure is not that one
  bond), and would make `amount_outstanding` (the whole aggregate) sit
  alongside one specific bond's `maturity_date`, an internally inconsistent
  row no honest UI label could fix.
- Silently drop the aggregate SEC row once OpenFIGI data exists — rejected:
  the aggregate figure is real, independently useful data (a company-wide
  leverage figure) with its own provenance; nothing about a newer, more
  granular source invalidates an older, differently-scoped fact.

**Tradeoffs**
An issuer with both an aggregate SEC-sourced figure and several
OpenFIGI-identified specific bonds now has multiple `security` rows that a
naive reader might assume double-count `amount_outstanding` if summed
carelessly — mitigated by `description` explicitly stating which kind of
figure each row is (`"... (SEC XBRL aggregate; not a specific instrument)"`
vs. a real bond ticker string), and by every row's own `provenance` making
the source unambiguous on inspection.

**Consequences**
- TD-007 remains open, unblocked but unresolved: the per-field provenance
  table is still deferred until a milestone has a *genuine* multi-provider,
  single-entity case (e.g. a future provider reporting a *coupon change* on
  one of these same five OpenFIGI-identified bonds, which would need to
  update that specific row's `coupon` while preserving `figi`'s original
  OpenFIGI provenance).
- Every future provider adapter facing this same shape of decision (a new
  provider identifies something that might be "the same thing, more
  detail" or "a genuinely different thing") should default to treating it
  as a new row unless the two facts are provably about the identical
  real-world instrument.

**Future Revisit Recommendation**
Implement the `security_field_provenance` join table (or an equivalent) the
first time a real caller needs to attribute two fields on the *same*
`security` row to two different providers — not before. This ADR's pattern
(new row when in doubt) is the interim answer for every provider adapter
until that happens.

---

## ADR-016: Research Universes and Watchlists share one `collection`/`collection_membership` table pair, discriminated by `collection_type`

**Date:** 2026-08-06
**Status:** Accepted

**Context**
Milestone 6.5 needed organization-wide, curated "Research Universes" —
distinct from the personal/team "Watchlists" `PLAN.md` §4.7/§14 already
approved for Milestone 8 (eleven named lists, not yet built). Both are
fundamentally the same shape: a named group of issuers with a rationale for
each membership. Building Research Universes now, ahead of Watchlists,
raised the question of whether to give it its own dedicated table or to
generalize the already-approved-but-unbuilt watchlist shape to cover both.

**Decision**
One `collection`/`collection_membership` table pair for both concepts, with
a `collection_type` discriminator (`research_universe`\|`watchlist`\|
`benchmark`). `collection` carries `scope` (`organization`\|`personal`\|
`team`), `visibility`, `curation_method`, `verification_status`, and
`owner_user_id` (nullable — no `user` table exists yet, TD-002) so the same
table can honestly represent an org-wide, system-seeded, publicly-visible
Research Universe and a future personal, user-created, private Watchlist
without either concept needing to fake fields that don't apply to it.
`collection_membership.rationale`/`rationale_as_of_date` is a dated
curatorial decision, never a current-status assertion — it never states an
issuer *is* currently distressed, in Chapter 11, or high yield; that comes
only from `research_evidence`/`alert_event` (ADR-018). `alert_rule` (§4.11)
is deliberately **not** created this milestone — it is a different concept
(user-defined threshold rules) with no real caller yet; adding it now would
repeat the speculative-infrastructure mistake ADR-006/ADR-015 already
warned against.

**Alternatives Considered**
- A dedicated `research_universe`/`research_universe_membership` table pair,
  built independently of the future `watchlist` table — rejected: the two
  concepts differ only in scope/ownership/curation metadata, not in shape.
  Two nearly-identical table pairs would mean duplicating every future
  feature (filtering, membership rationale, verification) twice, and would
  leave Milestone 8 deciding whether to unify them retroactively (a harder,
  live-data migration) instead of deciding now with no data at stake yet.
- A single `watchlist` table with no `collection_type` distinction, treating
  Research Universes as "system watchlists" — rejected: conflates two
  concepts a user needs to tell apart at a glance (an org-wide curated
  research group vs. a personal tracking list), and the eventual Watchlist
  UI (Milestone 8) would need to filter out Research Universes by some other
  means anyway.

**Tradeoffs**
`collection` carries a few columns that only make sense for one
`collection_type` (e.g. `owner_user_id` is meaningless for
`collection_type = research_universe`, `priority` is not yet used for
Watchlists) — accepted as a normal generalized-table tradeoff, the same
shape as `research_evidence.filing_id` being nullable because not every
future evidence provider has a filing to point to.

**Consequences**
- Milestone 8 (Watchlists) builds directly on this schema — no migration
  needed to introduce the concept, only new rows with
  `collection_type = watchlist` and a CRUD UI.
- Any future `collection_type` (e.g. a shared "peer group" concept) is a new
  enum value plus UI, not a new table.

**Future Revisit Recommendation**
If a `collection_type` ever needs materially different columns (not just
different values of existing ones), split it into its own table at that
point — this ADR's generalization is justified by real shape overlap, not a
permanent commitment to one table for every future grouping concept.

---

## ADR-017: `LLMProvider` Protocol pulled forward from Milestone 13, scoped to backend evidence review only, with provider-specific (not shared) credential configuration

**Date:** 2026-08-06
**Status:** Accepted

**Context**
Milestone 6.5's governed-AI evidence review layer needed an LLM call
(`app/ai/evidence_review.py`) years ahead of Milestone 13 (AI Research
Assistant), which is where `PLAN.md` §10 originally scoped the
`LLMProvider` Protocol and provider abstraction. A real `ANTHROPIC_API_KEY`
already existed in `backend/.env`, but `app/config.py` looked for a generic
`LLM_API_KEY` that was never actually set — a naming mismatch that left AI
review silently unusable. The user explicitly directed fixing the naming
mismatch with provider-specific variables rather than adding a duplicate
secret name.

**Decision**
Pull `LLMProvider` (§10's `complete`/`call_tools`/`create_embeddings`
Protocol) and a real `AnthropicProvider` forward into this milestone, scoped
narrowly to backend evidence classification — no chat, no RAG, no
user-facing assistant, no embeddings (`call_tools`/`create_embeddings` raise
`NotImplementedError("reserved for Milestone 13")`). Configuration is
provider-specific, not a shared secret: `ANTHROPIC_API_KEY`/
`ANTHROPIC_MODEL`, `OPENAI_API_KEY`/`OPENAI_MODEL`,
`AZURE_OPENAI_API_KEY`/`AZURE_OPENAI_ENDPOINT`/`AZURE_OPENAI_MODEL`, plus a
separate `EMBEDDING_PROVIDER` (reserved, unused — chat and embeddings may
end up on different vendors later). `app/ai/factory.py` reads
`LLM_PROVIDER`, validates only that selected provider's own required
credentials, and raises a clear `LLMConfigurationError` if they're missing —
it never falls back to a different provider and never logs a key. When no
provider is configured, the overnight monitor runs in deterministic-only
mode — a fully supported, intentionally operational state, not a degraded
one (`app/scripts/run_overnight_filing_monitor.py` catches
`LLMConfigurationError` at startup specifically to guarantee this).

**Alternatives Considered**
- Keep the generic `LLM_API_KEY` and just point it at whichever provider is
  active — rejected: a shared secret name across providers means switching
  providers silently changes what a stale/leaked `LLM_API_KEY` grants
  access to, and means "is Anthropic configured?" can't be answered without
  also knowing what `LLM_PROVIDER` currently says. Explicitly rejected by
  the user during planning.
- Defer AI evidence review entirely to Milestone 13, ship Layer 1
  (deterministic) only this milestone — rejected: a real, working
  `ANTHROPIC_API_KEY` already existed, and the two-layer design (deterministic
  candidates reviewed by governed AI) was a specific, approved requirement
  for this milestone, not an optional enhancement.
- Build a full multi-provider abstraction with all of OpenAI/Azure OpenAI/
  Ollama actually implemented now — rejected: no real caller needs them yet;
  `factory.py` raises a clear "selected but not implemented" error for those
  provider names directly, which is the same user-visible behavior as a full
  stub implementation with none of the speculative code.

**Tradeoffs**
Milestone 13's eventual AI Research Assistant will need to extend this same
`LLMProvider`/`AnthropicProvider` with `call_tools`/`create_embeddings` —
accepted, since the Protocol shape was already approved for that purpose and
this milestone only implements the subset it actually calls.

**Consequences**
- Every future AI-calling feature in this codebase reads its own
  provider-specific env vars and goes through `app/ai/factory.py` — no
  feature should introduce a second, competing credential-configuration
  pattern.
- `app/ai/evidence_review.py`'s fail-closed behavior (malformed/ungrounded
  AI response never becomes an alert, falls back to the deterministic
  template) is the precedent for how every future AI-assisted feature in
  this codebase must degrade.

**Future Revisit Recommendation**
Implement `call_tools`/`create_embeddings` on `AnthropicProvider` (and add
real `OpenAIProvider`/`AzureOpenAIProvider` implementations) when Milestone
13 has a concrete caller — not before.

---

## ADR-018: The evidence/alert model is provider-agnostic from the start — `research_evidence`, not `distress_evidence`, with alerts grouped via an internal Evidence Bundle concept rather than a hard filing FK

**Date:** 2026-08-06
**Status:** Accepted

**Context**
Milestone 6.5's overnight monitor is SEC-filing-specific today, but
`PLAN.md`'s roadmap already commits to future evidence sources for the same
kind of distress-signal research: CourtListener docket events (Milestone
7), ratings actions, macro/FRED-derived signals, and eventually AI-extracted
signals from research notes/documents (Milestone 9). Naming the new tables
and alert-grouping logic after SEC filings specifically (`distress_evidence`,
alerts keyed to a `filing_id`) would mean redesigning both the schema and
the alert-synthesis logic the first time a second evidence source arrives.

**Decision**
`research_evidence` (not `distress_evidence`) carries an explicit
`evidence_provider` column (SEC EDGAR is the first value, not the only one
the schema anticipates) and a nullable `filing_id` FK — this milestone's one
concrete source pointer, following the same nullable-source-FK precedent
TD-007/ADR-015 already established, so a future provider adds its own
nullable FK the same way rather than forcing a polymorphic association table
before a second real source exists. Evidence is grouped into an internal
**Evidence Bundle** (`app/domain/evidence_bundle.py`,
`group_evidence_into_bundles` — domain-only, not a persisted table) before
becoming one `alert_event`; today's grouping key is `(issuer_id,
evidence_provider, source_type, filing_id)`, which happens to mean "one
bundle per filing" because that's the only real grouping key that exists
yet, but the function itself has no SEC-specific logic, so a future
milestone can change the grouping key (e.g. same issuer + overlapping time
window across two providers) without touching alert-synthesis code
downstream. `alert_event` has **no** `filing_id` column at all — it carries
`evidence_ids` (the real source of truth for what caused the alert) plus a
denormalized `primary_source_label`/`primary_source_url` convenience pair
built by whichever provider's evidence triggered the bundle
(`filing_monitor_service._describe_sec_source` is the one place SEC-specific
label formatting happens, injected into the otherwise provider-agnostic
`app/services/alert_synthesis_service.py`). The UI resolves "which filing(s)
caused this alert" by joining through `evidence_ids` →
`research_evidence.filing_id`, never by a direct alert-to-filing pointer.

**Alternatives Considered**
- Name the tables/columns after SEC filings directly
  (`distress_evidence.filing_id` NOT NULL, `alert_event.filing_id`) —
  rejected: cheaper today, but CourtListener (the very next milestone) would
  either need its own parallel `distress_evidence`-like table or a
  disruptive rename/migration of live, permanently-committed data the first
  time a second provider arrives.
- A fully polymorphic evidence-source association
  (`source_type` + `source_id` with no FK constraint) instead of a nullable
  `filing_id` FK — rejected as overbuilt for one real source, the same
  reasoning ADR-015 used for `security`: build the general mechanism when a
  second real source needs it, not speculatively.
- Persist `EvidenceBundle` as its own table — rejected: nothing outside the
  alert-synthesis code path needs to query "what bundle is this evidence
  part of" independently of the alert it produced; `alert_event.evidence_ids`
  already answers that once a bundle becomes an alert, and a bundle that
  produces no alert (e.g. all-low-confidence evidence, or a duplicate on
  re-run) has no reason to be a durable row.

**Tradeoffs**
`primary_source_label`/`primary_source_url` are denormalized, provider-shaped
text rather than a normalized reference — accepted because the alternative
(the UI joining through evidence to the provider-specific source table on
every render) would leak SEC-specific joins into the generic alert list/
Morning Research Brief views, exactly the coupling this ADR exists to avoid.

**Consequences**
- Milestone 7 (CourtListener) adds `evidence_provider = courtlistener`,
  its own nullable source FK (e.g. `docket_entry_id`) on `research_evidence`,
  and its own `_describe_courtlistener_source`-shaped function injected into
  `alert_synthesis_service` — no schema change to `alert_event` and no
  change to the bundling function's signature.
- The Morning Research Brief page's heading ("New Research Alerts," not "New
  Distress Filings") and its evidence-provider filter (defaulted to "all
  providers," today only `sec_edgar` populated) were written against this
  same assumption at the UI layer — see `PLAN.md` §24.9.

**Future Revisit Recommendation**
Revisit the `(issuer_id, evidence_provider, source_type, filing_id)`
bundling key the first time two evidence records from *different*
providers genuinely need to join into one bundle (e.g. a CourtListener
docket event and an SEC 8-K about the same bankruptcy filing, on the same
day) — that is a real grouping-logic change, not a schema change, and
belongs in `group_evidence_into_bundles`, not a new migration.

---

## ADR-019: CourtListener docket discovery is a curated, live-verified linking step — not an automatic per-issuer watermark feed like SEC filings

**Date:** 2026-08-06
**Status:** Accepted

**Context**
`app.services.filing_monitor_service` (Milestone 6.5) discovers new SEC
filings automatically: every issuer in a Research Universe has a real CIK,
and SEC's `filings.recent` endpoint answers "what has issuer X filed since
date Y?" directly. Milestone 7 needed the equivalent for CourtListener —
but no equivalent question-answering endpoint exists. Confirmed live during
development: CourtListener's Search API (`/api/rest/v4/search/?type=r`) is
free-text, not identifier-keyed — there is no "list every new PACER case for
issuer X" call, and building one would require either a paid PACER account
with named-party monitoring (real monetary cost, explicitly out of scope per
PLAN.md section 22) or a maintained internal party-name-to-issuer index this
project doesn't have. A second real constraint, also confirmed live: the
Search API works anonymously, but the actual docket-entries/RECAPDocument
detail endpoints (the only source of the granular "what happened in court"
events `court_docket_entry` needs) return `401 Unauthorized` without a real
`COURTLISTENER_API_TOKEN` — read access to the data this milestone actually
needs is gated behind registration, unlike SEC EDGAR's fully open APIs.

**Decision**
Docket discovery is a separate, explicit, curated step
(`app.scripts.link_court_dockets`), not part of the automatic overnight
monitor: a real candidate (an issuer already seeded with a genuine,
independently-confirmed distress event — e.g. a real Chapter 11 filing
already evidenced via live SEC EDGAR data in Milestone 6.5's backfill) is
searched for by name via the real Search API, live-verified against an
expected `courtlistener_docket_id` before linking (the same
live-verification discipline `app.scripts.seed_research_universes`
established for SEC issuer identity — never a hand-typed/guessed docket
id), and only then does `court_docket.issuer_id` get set. Once linked,
`app.services.court_docket_service.sync_one_docket` (driven by
`app.scripts.sync_court_dockets`) is the repeatable, idempotent half —
exactly mirroring `filing_monitor_service`'s per-issuer error isolation and
provenance-per-match pattern, applied per docket instead. Idempotency is
per-entry via CourtListener's own stable `courtlistener_entry_id` (the same
role `sec_filing.accession_no` plays for SEC), so no separate
`docket_monitor_run`/watermark table was added to PLAN.md section 4.5 — a
re-sync is always safe and only ever processes genuinely new entries,
without needing to track "since when."

**Alternatives Considered**
- Build an automatic per-issuer docket-discovery feed anyway, polling the
  Search API by issuer legal name on a schedule — rejected: free-text party
  name search is unreliable for automatic linking (the same issuer's name
  can match unrelated cases, e.g. a labor lawsuit instead of the actual
  bankruptcy case — encountered live searching "Diebold Nixdorf," which
  returned an unrelated 2019 employment case ahead of the real 2023 Chapter
  11 docket). Automatic, unverified linking would violate this project's
  core "never fabricate or fuzzy-merge identity" rule (PLAN.md section 8's
  Universal Search principle, applied here to dockets).
- Require a paid PACER/CourtListener account with named-party monitoring to
  get true automatic discovery — rejected: real monetary cost per PLAN.md
  section 22's explicit "never perform a real PACER purchase in this
  build," and not needed for a v1 real-data demonstration.
- Add a `docket_monitor_run` table mirroring `filing_monitor_run` for
  watermark tracking — rejected: nothing to watermark. A docket's entries
  are the unit of idempotency, not a discovery run's timestamp; adding the
  table now would be schema built for a delta-detection problem CourtListener
  docket sync doesn't actually have.

**Tradeoffs**
New real distress dockets are not discovered automatically the way new SEC
filings are — an analyst/admin must identify and link a new docket before
its entries start flowing into the evidence/alert pipeline. This is a real,
honest scope limitation, not a hidden one: `app.scripts.link_court_dockets`
documents it in its own module docstring, and the Research Universe/Morning
Research Brief UI never implies CourtListener coverage is exhaustive.

**Consequences**
- `court_docket.issuer_id` stays nullable specifically to support this
  two-step discover-then-link flow — a docket search result can exist
  transiently (via `search_dockets`) without ever becoming a linked,
  monitored docket if a human/script never confirms the match.
- A future milestone that wants broader automatic coverage (e.g. a licensed
  PACER monitoring subscription, or a maintained party-name index) plugs in
  as a new discovery mechanism feeding the same `link_docket` function —
  `sync_one_docket`/`court_docket_service` need no changes.
- `app.core.distress_rules.DOCKET_EXCLUDED_RULE_IDS` follows directly from
  this same "a linked docket is already a confirmed case" premise: rules
  designed for SEC filings' *ambiguous*-context detection (e.g. a bare
  "chapter 11" mention that might mean the tax code) are actively wrong for
  docket-entry text, where the case's chapter is never ambiguous — see
  BUILD_LOG.md for the real, live-caught noise problem (83 near-duplicate
  alerts from one docket's 429 routine entries) this exclusion fixes.

**Future Revisit Recommendation**
If a future milestone adds a licensed PACER monitoring subscription capable
of real per-party alerting, revisit whether `link_court_dockets`'s curated
step can be replaced or supplemented by that subscription's own discovery
feed — `sync_one_docket` itself would not need to change, only what feeds
it a linked `court_docket` row.

---

## ADR-020: Automatic CourtListener docket linking on a hierarchy of identity evidence — superseding ADR-019's blanket prohibition on automatic linking

**Date:** 2026-08-07
**Status:** Accepted

**Context**
ADR-019 (Milestone 7) established that CourtListener docket discovery must
be a curated, live-verified linking step — never automatic — because a
real live test searching "Diebold Nixdorf" returned an unrelated 2019
employment case ahead of the actual 2023 Chapter 11 docket, demonstrating
that free-text party-name search alone is not a safe automatic-linking
signal. Milestone 7.5 requires a reusable automatic enrichment pipeline
that runs every applicable provider (SEC, CourtListener, OpenFIGI) for
every issuer it discovers or already knows about, without a human having
to remember to trigger CourtListener manually. This creates a direct
tension with ADR-019's blanket prohibition, which this ADR resolves by
replacing "never automatic" with "automatic only on a hierarchy of
independent strong identity signals, never a single fuzzy one" —
`app.core.court_docket_matcher` implements the actual signal evaluation;
`app.services.court_docket_service.attempt_auto_link` is the orchestration
entry point.

A draft of this design initially proposed requiring court/jurisdiction
correspondence to the issuer as one of three mandatory signals. This was
corrected during planning: a debtor legitimately files bankruptcy wherever
is legally/strategically convenient — Delaware, S.D.N.Y., and S.D. Tex. are
extremely common venues with no necessary relationship to a company's
headquarters. A hard jurisdiction requirement would have systematically
rejected real, correct matches by construction. The accepted design below
reflects that correction: jurisdiction/court is a supporting or
contradiction-detection signal only, never a required one.

**Decision**
`attempt_auto_link` is only ever invoked for an issuer with at least one
`DOCKET_RELEVANT_EVIDENCE_TYPES` research-evidence row already on file
(bankruptcy/restructuring-relevant SEC evidence) — CourtListener enrichment
is scoped to distressed/restructuring-relevant issuers, not attempted
uniformly for every issuer regardless of evidence. Given that evidence, a
live `search_dockets` call returns candidates, each evaluated against a
hierarchy of independent strong identity signals
(`app.core.court_docket_matcher.evaluate_candidate`):

1. Normalized legal-name match (word-boundary + corporate-suffix
   normalization — the same discipline as the CIK resolver's
   Yellow/Yellowstone fix).
2. An exact case-number reference in the triggering SEC evidence text.
3. A date correlation between the docket's filing date and the evidence's
   `as_of_date` (within 14 days).
4. Court/jurisdiction referenced *in the evidence text itself* — evidence-
   derived, not HQ-derived, so it never encodes a false jurisdiction
   assumption; used as a supporting/contradiction-detection signal only,
   never counted toward the passing threshold and never required.

Case-type consistency (the candidate docket must itself be a bankruptcy
case — CourtListener reports a `chapter`) is a hard requirement. Above
that: an exact case-number match is strong enough to pass alone; otherwise
at least two of {name match, case-number match, date correlation} must
agree with no contradiction. The result must additionally be a *unique*
passing candidate — if more than one candidate independently clears the
bar, the outcome is `ambiguous_manual_review`, never a coin flip. Every
attempt (verified, no-match, or ambiguous) is persisted in
`court_docket_link_attempt` with its full evaluated signal set
(`match_signals`, jsonb) — a complete, honest audit trail, not a black box.
Only `verified_docket_match` proceeds to `link_docket` + a real
`sync_one_docket` call; the existing curated `app.scripts.link_court_dockets`
flow is retained unchanged as a manual override path, consistent with this
project's "curated universes are still allowed alongside system-discovered
ones" principle (PLAN.md Milestone 7.5).

**Alternatives Considered**
- Automatic linking on a single fuzzy signal (e.g. name similarity alone)
  — rejected: this is exactly the risk ADR-019 already demonstrated live
  (the Diebold Nixdorf unrelated-case result). A single weak signal is not
  an improvement over the status quo it would replace.
- Requiring court/jurisdiction correspondence to the issuer's headquarters
  as a mandatory signal — rejected during planning (see Context): would
  systematically reject real matches, since bankruptcy filings routinely
  occur far from a debtor's HQ for legitimate legal/strategic reasons.
- Leaving CourtListener fully manual (extending ADR-019 unchanged) —
  rejected: defeats Milestone 7.5's explicit requirement that newly
  discovered and already-known issuers alike automatically enter a
  reusable enrichment pipeline without a human remembering to trigger each
  provider by hand.

**Tradeoffs**
The signal hierarchy is a heuristic, not a certainty — it is deliberately
biased toward `ambiguous_manual_review` over a wrong `verified_docket_match`
(a false positive is treated as strictly worse than a missed automatic
link), which means some real matches will still require manual
confirmation via the existing curated flow rather than linking
automatically. This is an accepted, honest limitation, not a hidden one.

**Consequences**
- `court_docket_link_attempt` is a new table distinct from
  `issuer_enrichment_status`'s single current-state row, so a rejected or
  ambiguous attempt remains individually diagnosable rather than being
  overwritten by the next retry.
- `app.scripts.link_court_dockets`'s curated `_CANDIDATES` flow is
  unchanged and remains the path for a human to confirm a match the
  automatic signal hierarchy correctly declined to guess at.
- `DOCKET_EXCLUDED_RULE_IDS` (ADR-019) continues to apply unchanged once a
  docket is linked, by either path — the "a linked docket is already a
  confirmed case" premise holds regardless of whether linking was manual
  or automatic.

**Future Revisit Recommendation**
If live operation shows the signal hierarchy is systematically too
conservative (too many real matches falling to `ambiguous_manual_review`)
or, more dangerously, produces a real false positive, revisit the specific
signal weights and the passing threshold — the underlying architecture
(`court_docket_matcher` as a pure, independently testable module) is
designed to make that a parameter change, not a redesign.
