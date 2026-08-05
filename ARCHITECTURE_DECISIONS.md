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
