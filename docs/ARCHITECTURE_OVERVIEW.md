# Nexus Credit Intelligence — Architecture Overview for New Developers

This is a narrative onboarding guide. It does not replace the project's
authoritative documents — it exists to get a new developer from zero to
productive, and to point to the right authoritative source for everything it
summarizes.

| If you need... | Go to |
|---|---|
| Why Nexus exists, who it's for, product philosophy | `docs/VISION.md` |
| The precise architecture spec, data model, milestone roadmap, current status | `PLAN.md` (**authoritative if anything conflicts**) |
| Why a specific technical choice was made, alternatives considered | `ARCHITECTURE_DECISIONS.md` (ADRs, append-only) |
| What actually happened, milestone by milestone, bugs found and fixed | `BUILD_LOG.md` (append-only engineering journal) |
| The rules you must follow while writing code here | `CLAUDE.md` (permanent operating guide) |
| Running/deploying the app | `README.md` |

Read this document once, top to bottom, before touching code. It will tell
you *how the pieces fit together and why*; the documents above tell you the
authoritative detail once you know where to look.

---

## 1. What this product is, in one paragraph

Nexus is a research platform for distressed-credit and leveraged-finance
investment professionals — analysts who need to know, for a company under
financial stress, what debt it has, where each piece sits in the capital
structure, what just happened (a filing, a court docket entry), and whether
they can trust what's on their screen. The entire engineering discipline of
this codebase exists to serve one non-negotiable rule: **every fact displayed
must carry provenance** — which provider produced it, the exact source
record, when it was reported, when it was retrieved, whether it's fresh or
stale, whether it's a reported fact or a calculated one, and whether it's
public, licensed, synthetic, or AI-extracted. A value that can't carry that
lineage does not get displayed, ever. If you remember only one thing from
this document, remember that — it explains nearly every architectural
decision that follows.

The second governing idea: Nexus is **one continuous workflow**, not a set of
independent pages.

```
Morning Research Brief → Credit Universe → Issuer → Capital Structure
   → Evidence → Supporting Documents → Research Notes → Investment Decision
```

**Credit Universe — a screenable table of every bond and loan Nexus
tracks — is the primary Version 1 workflow and the landing page after
login.** Everything else (Issuer detail, lineage views, alerts, documents) is
a drill-down from it, not a parallel feature. When you're deciding where a
new feature belongs, ask where it sits in this chain before you design it.

Full product philosophy — including "prefer honesty over completeness" (an
honest empty state beats a plausible fabrication) and the AI philosophy
below — lives in `docs/VISION.md`. Read it; it's short and it will save you
from building things the architecture is specifically designed to prevent.

---

## 2. Tech stack, and why each piece was chosen

| Layer | Choice | Why (see ADR) |
|---|---|---|
| Backend language/framework | Python 3.12, FastAPI, Pydantic 2 | ADR-002 — replaced an original Node/Hono/Drizzle plan; Python's data/typing ecosystem fit a data-heavy, provenance-heavy domain better |
| ORM / migrations | SQLAlchemy 2, Alembic | ADR-002 |
| Database | Supabase-managed PostgreSQL, **every environment, including local dev** | ADR-001 — no local Postgres, no Docker Postgres, no SQLite, anywhere, ever |
| Extensions | `pgvector` (embeddings, gated), `pg_trgm` (fuzzy/typo search) | Database-wide shared resources — never dropped/relocated by Nexus migrations |
| Backend hosting | Railway (Docker-built) | — |
| Frontend | React, TypeScript (strict), Vite, Material UI | ADR-003 — replaced an original server-rendered Hono/JSX plan |
| Server state | TanStack Query (all of it — no ad hoc `fetch`-in-`useEffect`) | Consistent caching/loading/error semantics everywhere |
| Dense tabular UI | TanStack Table | Used for Credit Universe and similar institutional grids |
| Frontend hosting | Vercel | Deployed and built **independently** of the backend — the backend never serves frontend assets |
| AI / LLM | Anthropic (Claude), via a provider-agnostic `LLMProvider` protocol | ADR-010 — OpenAI/Azure OpenAI/Ollama are interface stubs only, not implemented |

**Explicitly and permanently prohibited** (`CLAUDE.md`): local Postgres in
any form, Dockerized Postgres, SQLite anywhere, Hono, Drizzle, the backend
serving frontend assets, and durable use of Railway's ephemeral local disk.
If you find yourself reaching for any of these, stop — the constraint is
deliberate, not an oversight.

### Why Supabase is shared, and what that means for you

This Supabase project also hosts a **different, unrelated application**.
Nexus did not get its own project — isolation is enforced at the **Postgres
schema level** (ADR-013):

- Every Nexus table, index, sequence, view, and the Alembic version table
  lives in the `nexus` schema. Nothing Nexus-owned goes in `public`.
- `Base.metadata` defaults to `nexus`; Alembic runs with
  `include_schemas=True`, `version_table_schema="nexus"`, and an
  `include_name` filter that restricts autogenerate to `nexus` only.
- You must never inspect, modify, or drop anything belonging to the other
  application, never `DROP SCHEMA public`, never `DROP EXTENSION vector` or
  `pg_trgm` (shared, database-wide).
- The `nexus` schema is never exposed to PostgREST — the frontend only ever
  reaches Nexus data through FastAPI.

If you're setting up local development, note there is no "local database" to
stand up — you connect to the real, shared Supabase project via
`DATABASE_URL` (pooled) and `DIRECT_DATABASE_URL` (direct, required for
Alembic). Never rename the fixed environment variable names in `PLAN.md`
§19 — `SUPABASE_SERVICE_KEY` in particular must never be exposed via `VITE_`
variables, frontend code, logs, or API responses.

---

## 3. The one architecture diagram that matters

Every piece of data in this system flows through the same fixed pipeline,
with no exceptions:

```
External Provider (SEC EDGAR, CourtListener, OpenFIGI, FRED, ...)
    ↓
Provider DTO          — raw shape as the provider returns it
    ↓
Normalizer            — provider-specific: DTO → canonical shape
    ↓
Canonical Domain Object — a Pydantic model, provider-agnostic
    ↓
Repository            — the ONLY layer allowed to touch SQLAlchemy/session
    ↓
SQLAlchemy / Supabase PostgreSQL (schema `nexus`)
```

The rule this enforces (ADR-004): **a provider module never imports
`app.db.session` and never opens a session.** It produces DTOs and canonical
domain objects and stops there. Only `backend/app/repositories/**` touches
the ORM. API routes call services or repositories — they contain no
normalization or business logic themselves. This is not a style preference;
it's what makes provenance auditable end-to-end and what lets a new provider
be added without ever touching persistence code by hand.

**AI tools follow the exact same discipline as a human caller.** An AI tool
(e.g. something the future AI Research Assistant calls) is a typed
service/repository call like any other — never raw SQL, never broader
access than an equivalent human-facing API endpoint already has.

### Layered directory map (backend)

```
backend/app/
  providers/<name>/        client.py, dto.py, normalizer.py, provider.py
                             — one directory per external provider
                               (sec_edgar, courtlistener, openfigi, fred)
  domain/                  Pydantic canonical domain objects (immutable)
  models/                  SQLAlchemy ORM models (schema=nexus)
  repositories/            The only layer touching the ORM/session
  services/                Business logic / orchestration, calls repositories
  api/routes/              Thin FastAPI routers — call services, not the ORM
  schemas/                 Pydantic request/response shapes for the API layer
  core/                    Cross-cutting domain logic: entitlement (policy_check),
                             freshness, distress rules, issuer resolution,
                             shared enums (core/types.py)
  ai/                      LLMProvider protocol, provider implementations,
                             model routing, evidence review (see §6 below)
  extraction/              Document Intelligence: Extractor protocol,
                             PyMuPDF4LLM implementation, structure-aware chunker
  storage/                 StorageClient protocol + Supabase Storage implementation
  synthetic/               Generators for explicitly-labeled synthetic demo data
  scripts/                 Standalone entry points (cron jobs, worker, one-off scripts)
  observability/           OpenTelemetry tracing helpers
  db/                      base.py (Base.metadata, schema=nexus), session.py (get_db)
```

### Frontend map

```
web/src/
  api/           One file per resource — thin fetch wrappers, typed
  queries/       TanStack Query hooks wrapping api/* (this is where all
                   server-state caching lives — never fetch in a component)
  pages/         Route-level components (one per URL)
  components/    Reusable UI (DataTable, ProvenanceBadge, SyntheticDataBadge,
                   SeverityBadge, ConvictionBadge, ...)
  lib/           Formatting, small hooks (debounce, isMobile)
```

Notice `ProvenanceBadge` and `SyntheticDataBadge` are first-class, reusable
components — provenance isn't a backend-only concern, it's meant to be
visible on the screen next to the fact it describes.

---

## 4. The domain model: how "provenance" actually works

This is the part of the codebase you need to understand before changing
anything else, because almost every table and every service ultimately
answers to it.

- **`provenance`** — the spine. Every displayed fact has a row here:
  `provider`, `source_record_id`, `source_url`, `as_of_date` (when the fact
  was true), `retrieved_at` (when Nexus fetched it), `transformation`
  (`reported` vs. `calculated`), `classification` (`public` / `licensed` /
  `synthetic` / `ai_extracted`). See `backend/app/domain/provenance.py`.
- **`calculation` + `calculation_input`** — if a value is `calculated`, it
  must point to a `calculation` row (method + formula note) and that
  calculation's inputs are a normalized join table of the `provenance` rows
  that fed it (ADR-006 replaced an earlier JSONB-array design specifically
  so this lineage is queryable, not just stored). A calculated number with
  no traceable inputs is not allowed to exist.
- **`raw_provider_payload`** — the durable, unmodified raw response from a
  provider call, so a normalizer bug is always recoverable/re-derivable
  without re-fetching from the outside world.
- **Freshness (`live` / `cached` / `stale`)** is **never stored** — it's
  computed at read time from `retrieved_at` plus a per-provider TTL policy
  (`backend/app/core/freshness.py`, ADR-005). SEC filings are "live" for 24h
  and only "stale" after a week (they move slowly); TRACE prints are "live"
  for 15 minutes (they move fast). If you ever see code trying to persist a
  freshness value, that's a bug — freshness must never be allowed to drift
  out of sync with "now."
- **Entitlement / `policy_check`** (`backend/app/core/entitlement.py`,
  §4.8) — a pure function, no I/O, fully unit-testable. Public, synthetic,
  and AI-extracted data are always allowed. Licensed data requires an active
  `data_entitlement` row whose environment, date window, user allow-list,
  and specific permission flag (`display_permission`,
  `redistribution_permission`, `ai_processing_permission`,
  `embedding_permission`) all check out for the specific action being
  attempted (`display`, `export`, `send_to_llm`, `prompt_inclusion`,
  `create_embedding`, `document_download`, `api_expose`). **No licensed
  content reaches an LLM, an export, an embedding, or an API response
  without passing this check for that exact action** — this is the gate the
  future AI Research Assistant must call before putting anything licensed
  into a prompt.
- **Synthetic data** is a first-class concept, not a shortcut: it's tagged
  `is_synthetic`/`synthetic_reason` in the data model and rendered with a
  visible `SYNTHETIC_DEMO_DATA` badge in the UI (`SyntheticDataBadge.tsx`).
  It exists because Nexus sometimes needs realistic demo data (e.g. a
  leveraged-loan capital structure) without a real licensed source, but it
  must never be confused with a real fact on screen.
- **`admin_upload`** as a provenance channel (ADR-007): a human-uploaded
  document is always `provider=admin_upload` with an explicit
  `original_source` (`pacer`/`courtlistener`/`issuer_site`/`other`).
  `provider=pacer` is reserved exclusively for documents the system actually
  retrieves through a real PACER integration — never used for a manual
  upload, even one sourced from PACER originally.

If you add a new fact anywhere in this system, ask: what's its provenance
row, is it reported or calculated, is it public/licensed/synthetic/
AI-extracted, and does a licensed one need a `policy_check`? If you can't
answer all four, the feature isn't ready to display the value yet.

---

## 5. The evidence → alert pipeline (the pattern every new provider follows)

This is the second most important pattern in the codebase, and it's the
direct precursor to how AI is used today and how it will be used tomorrow.

```
Provider event (SEC filing / court docket entry / future provider)
    ↓
Layer 1 — deterministic rule engine (app/core/distress_rules.py)
    matches known distress language/patterns, produces RuleMatch
    candidates with a rule-based confidence score. AI is never the
    only detector of anything — a rule must flag it first.
    ↓
ModelRouter.review_evidence (app/ai/model_router.py)
    routes each candidate bundle: too-weak signal → skip;
    high-impact category (Ch. 11, bankruptcy, plan-confirmed) → Sonnet,
    always, no Haiku attempt; everything else → Haiku first, escalate
    to Sonnet only if Haiku fails or reports low confidence.
    ↓
Layer 2 — AI review (app/ai/evidence_review.py)
    reviews ONLY the excerpts a rule already matched, classifies
    severity/confidence, and — critically — decides whether the
    excerpt is actually ABOUT the issuer or about an unrelated third
    party (a customer, vendor, a director's former employer). Fails
    closed on any parse error: falls back to a deterministic templated
    result rather than accepting an ungrounded claim.
    ↓
research_evidence row (provider-agnostic — NOT "distress_evidence",
    ADR-018 — so a new provider never needs its own parallel table)
    ↓
Evidence Bundle → alert_event (grouped, severity-ranked)
    ↓
Morning Research Brief / Alerts Center / Issuer timeline
```

The evidence/alert model was deliberately made **provider-agnostic from the
first implementation** (ADR-018): `research_evidence`, not
`sec_evidence`/`distress_evidence`. When CourtListener was added a milestone
later, it plugged into the exact same pipeline with zero schema change —
only a new `evidence_provider=courtlistener` value. **This is the template
to follow for every future signal source** (TRACE, ratings, macro
data): extend this same pipeline, don't invent a parallel one.

`ai_call_log` (one row per real model API call — model used, route
[haiku/sonnet], routing reason, tokens, estimated cost, latency, success,
retries) makes every AI call in this pipeline fully observable and
cost-attributable. `AiCallBudget` enforces a hard per-run ceiling
(`max_calls`/`max_cost_usd`/`max_sonnet_calls`) checked immediately before
every provider call — a budget-exhausted bundle is marked `deferred`, not
silently downgraded to a weaker deterministic alert, so a later run with
fresh budget can still pick it up (via the same `bundle_key` idempotency
check).

---

## 6. AI architecture — current state and how to extend it

### 6.1 Core philosophy (read this before writing any AI-touching code)

> **AI never invents a fact.** Facts are created only by verified providers.
> Canonical facts produce Research Evidence; Research Evidence produces
> Alerts. AI's role is strictly downstream: it explains, summarizes,
> classifies, compares, prioritizes, and connects already-verified facts. It
> never asserts a conclusion beyond what the underlying evidence supports,
> and it **fails closed** — a malformed or ungrounded AI response falls back
> to deterministic, evidence-only wording rather than silently becoming an
> alert.

This is proven twice already (SEC evidence review, CourtListener evidence
review) and it governs every future AI feature: Universal Search ranking, the
AI Research Assistant, investment memo generation, whatever comes after
those. If a design would let AI output become a displayed fact without a
human-verifiable evidence trail underneath it, the design is wrong — stop and
reread `docs/VISION.md`'s AI philosophy section before proceeding.

### 6.2 The provider abstraction

```python
# backend/app/ai/providers/base.py
class LLMProvider(Protocol):
    def complete(self, request: CompletionRequest) -> CompletionResponse: ...
    def call_tools(self, request: object) -> object: ...          # reserved
    def create_embeddings(self, texts: list[str]) -> list[float]: ...  # reserved
```

No application code imports the Anthropic SDK directly outside
`app/ai/providers/anthropic_provider.py`. `app/ai/factory.py`
(`get_llm_provider`) resolves the `LLM_PROVIDER` env var to a concrete
implementation and **raises a clear config error** for any provider that
isn't implemented yet — it never silently falls back to a different
provider, and it only validates the credentials of the provider actually
selected (an unset `OPENAI_API_KEY` never blocks booting with
`LLM_PROVIDER=anthropic`). OpenAI/Azure OpenAI/Ollama exist today only as
`LLMConfigurationError`-raising stubs — implementing one is a real,
scoped task (add a class implementing the protocol, wire it into the
factory, never touch a caller).

**Provider-specific credentials, never a shared generic secret** (ADR-017):
there is no generic `LLM_API_KEY`. Each provider has its own named
credential (`ANTHROPIC_API_KEY`, and future `OPENAI_API_KEY`, etc.) so
adding a second provider is additive configuration, not a breaking rename.

`complete()` is **synchronous today**, a deliberate, documented deviation
from an original async sketch (TD-004: this whole backend is sync
SQLAlchemy). Revisit only alongside TD-004, and only when a genuinely
async-shaped consumer — the interactive AI Research Assistant chat over
FastAPI is the anticipated one — makes it worth the change everywhere at
once, not one caller at a time.

### 6.3 Model routing and cost control

`app/ai/model_router.py`'s `ModelRouter` is **the only sanctioned way** to
reach AI evidence review — no caller should ever call
`review_evidence_candidates` directly except through the router. It owns:

- **Routing policy**: deterministic confidence floor (too weak → skip
  entirely) → high-impact categories go straight to Sonnet, always → default
  path is Haiku first, escalate to Sonnet once if Haiku fails or its
  self-reported confidence is below threshold.
- **Hard budget enforcement**, checked immediately before every call so no
  caller can bypass it.
- **Full observability**: exactly one `ai_call_log` row per real API call.

This exists because of a real incident (Milestone 7.5.3): unmonitored AI
calls with no routing and no budget is a cost and reliability risk the moment
volume gets real. **Any future AI feature that calls an LLM in a batch or
background context should go through an equivalent routed, budgeted,
logged path** — don't build a second unmonitored call site.

### 6.4 The fail-closed response pattern

`app/ai/evidence_review.py` is the reference implementation for **every**
future structured-AI-output feature:

1. A strict, explicit JSON-shape system prompt, with an instruction to
   return bare JSON (no markdown).
2. Defensive parsing that still handles reality: Haiku, empirically,
   wraps JSON in a ` ```json ` fence despite being told not to — the parser
   strips it rather than trusting the prompt to be obeyed 100% of the time.
3. Any parse failure, missing field, out-of-range value (e.g. confidence
   not in `[0, 1]`) → return `None`. The caller is required to have a
   deterministic fallback for `None` — never a partially-trusted AI guess.
4. A dedicated boolean field (`issuer_is_subject`) specifically added after
   a real production error where an AI review confidently mis-attributed a
   third party's bankruptcy language to the issuer itself — a concrete
   lesson: **attribution/subject-matching is its own explicit field to
   verify, never assumed from "the excerpt mentions distress language."**

Copy this shape (strict system prompt + fail-closed parse + a caller-owned
deterministic fallback) for any new structured AI extraction task.

### 6.5 Document Intelligence — the newest layer, and the on-ramp to RAG

`backend/app/extraction/` (Milestone 10C, most recent completed work) is the
foundation the roadmap's RAG/embeddings/AI Research Assistant milestones will
sit on top of:

- `Extractor` protocol (mirrors `LLMProvider`'s shape) — currently
  implemented by `PyMuPDF4LLMExtractor`, producing per-page Markdown-like
  text (headings, pipe-syntax tables) as a generic `ExtractionResult`.
- `chunker.py` (`chunking_v1`) — a pure, structure-aware function: pipe
  tables are never split, headings carry a `section_path`/`section_title`
  forward onto their body chunks (so a citation can say "ARTICLE VI /
  Financial Covenants / Section 6.11"), long sections split at a target size
  while retaining section context.
- A dedicated **extraction-worker** (`app/scripts/run_document_extraction_worker.py`,
  its own Railway service on a 5-minute cron) does the actual
  extract → chunk → validate → persist pipeline out-of-band —
  **never inline in an HTTP request**. The API route only enqueues a
  `pending` row and returns immediately.
- Every extraction is wrapped in an OpenTelemetry span
  (`app.observability.tracing.document_intelligence_span`).

> **Validation status (2026-10-10): implemented, not production-verified.** No extraction has
> ever completed in production and `document_chunk` has zero rows. The extraction worker has
> never reached the database since it was deployed (PLAN.md KI-005 — root cause under
> investigation; diagnostic structured logging was added to the worker entry point). Treat the
> chunker and extractor as proven only against synthetic fixtures until a real document has been
> processed end to end. The worker now logs `worker_started` → `config_validated` →
> `database_connected` → claim/`no_eligible_job` → `worker_finished outcome=…` (identifiers,
> counts and durations only — never document text or credentials). Cancellation is not a
> supported lifecycle operation (TD-035).

This gives the future RAG milestone exactly what it needs: real, chunked,
structure-aware, citable text with a stable identity (`extraction_id`,
`document_chunk` rows) to embed — without that milestone having to build its
own ingestion pipeline first.

### 6.6 What's next on the AI roadmap, and how to build it without breaking the pattern

Per `PLAN.md` §9/§10/§13 and `docs/VISION.md`, in the order the architecture
anticipates:

1. **Gated embeddings** (`pgvector`, already provisioned as an extension) —
   `create_embeddings` on `LLMProvider` is already reserved for this.
   Embedding a licensed document chunk must pass `policy_check` with action
   `create_embedding` (its own, narrower permission flag —
   `embedding_permission` — distinct from general `ai_processing_permission`)
   before it's ever embedded.
2. **RAG** over an issuer's evidentiary record — built on top of Document
   Intelligence's chunks (§6.5) plus embeddings. Every retrieved chunk used
   in a generated answer must carry its provenance back to the source
   document/record, exactly like every other displayed fact.
3. **AI Research Assistant** (`PLAN.md` §9) — the biggest AI surface, and the
   one most likely to be delegated to a new developer. Its architecture is
   already specified, not open for reinterpretation:
   - **A fixed, typed tool set only** — `search_credit_universe`,
     `get_issuer`, `get_instrument`, `get_capital_structure`,
     `get_financial_facts`, `get_trace_history`, `get_sec_filings`,
     `get_court_dockets`, `get_research_notes`, `get_documents`,
     `get_watchlists`, `get_alerts` — each a thin wrapper over an existing
     repository/service call. **No arbitrary SQL, ever** (ADR-009). The
     assistant's access is exactly as broad as a human user's existing read
     API, never broader.
   - Every underlying record must pass `policy_check` (`prompt_inclusion`,
     then `send_to_llm`) *before* it's allowed into the prompt context at
     all — a licensed record that fails the check is simply excluded, and
     the answer says so rather than silently working around the gap.
   - Every answer must cite its internal source records (provider + as-of
     date), and must never blend reported facts, calculated values,
     synthetic data, AI-extracted facts, and analyst opinions (research
     notes) into one undifferentiated sentence — these are always
     distinguishable in the response.
   - When data is missing, the assistant states that plainly. It does not
     guess or extrapolate. (Same "prefer honesty over completeness" rule as
     everywhere else in the product.)
4. **Investment memo generation** — the workflow's eventual endpoint: from
   accumulated evidence to a defensible written thesis. Treat it as the
   AI Research Assistant's output mode, not a separate AI subsystem.

**A practical checklist for any new AI feature you're asked to build here:**

- [ ] Does it call `LLMProvider` through the existing factory/router, or does
      it need its own routing/budget logic (only if it's a genuinely
      different call shape — batch review vs. interactive chat)?
- [ ] Does every fact it touches already have a `research_evidence`/
      `provenance` row, or is this feature at risk of inventing a fact?
- [ ] Does it check `policy_check` for every licensed record, for the
      *specific* action (`prompt_inclusion`/`send_to_llm`/
      `create_embedding`), before that record enters an AI-facing context?
- [ ] Does a malformed/ungrounded model response fail closed to a
      deterministic fallback, per §6.4's pattern?
- [ ] Does it log an `ai_call_log`-equivalent row for cost/observability, or
      does it fit into the existing `ai_call_log` table?
- [ ] Does it use a fixed, typed tool/query surface rather than constructing
      SQL from user input?
- [ ] Does the UI distinguish reported/calculated/synthetic/AI-extracted/
      analyst-opinion content, rather than rendering it as one undifferentiated
      block of text?

If you can check every box, you're building it the way the rest of this
codebase already builds AI features. If you can't, that's the signal to stop
and raise it — per `CLAUDE.md`'s Architecture Change Policy — rather than
build a parallel, less-governed AI path.

---

## 7. Deployment topology

Four independently-deployed Railway services, all built from the same
backend `Dockerfile`, plus a separately-deployed Vercel frontend:

| Service | Start command | Schedule |
|---|---|---|
| API | `uvicorn app.main:app` | always-on, `/health` healthcheck |
| Extraction worker | `python -m app.scripts.run_document_extraction_worker` | cron, every 5 minutes |
| Nightly discovery (EDT) | `python -m app.scripts.run_nightly_scheduled_discovery` | cron, 2am |
| Nightly discovery (EST) | same script | cron, 3am |

The two nightly-discovery services (EDT/EST) exist as a DST-safe wrapper pair
around the same script — a real incident (KI-004, 2026-08-13, see
`BUILD_LOG.md`) is the reason this isn't a single naive cron entry.

The **frontend never touches the database or Supabase directly** — it only
calls the FastAPI backend, and it is built/deployed entirely independently
on Vercel (`CLAUDE.md`'s explicit prohibition on the backend serving
frontend assets). Railway's local disk is ephemeral and never used for
anything durable — durable state is Supabase Postgres (`nexus` schema) or
Supabase Storage (documents, via `StorageClient`).

---

## 8. Current state, and where the edges of "done" are

As of the most recent commits, roughly the first ten-and-a-half of sixteen
planned Version 1 milestones are complete: provenance/entitlement
foundation, SEC EDGAR/OpenFIGI/FRED/CourtListener adapters, Credit Universe,
Issuer Detail + Capital Structure, Research Universes + the overnight
distress filing monitor (with AI-assisted evidence review and Haiku/Sonnet
cost-routed model routing), Watchlists, Alerts Center, Research Notes +
Audit Trail, Research Documents + Supabase Storage, Universal Search, and —
most recently — Document Intelligence (canonical extraction + chunking).
**Not yet started**: the TRACE adapter, the AI Research Assistant + gated
embeddings, and disabled licensed-provider capability cards. Authentication
is intentionally disabled for V1 (`AUTH_ENABLED=false`, TD-002) — every
request is currently treated as an implicit administrator in a single shared
analyst workspace; this is a known, documented limitation, not an oversight.

Always check `PLAN.md`'s **Project Status** and **Milestone Status** tables
for the current, authoritative numbers before assuming anything above is
still accurate — this document is a snapshot, PLAN.md is live.

**The Version 1.0 architecture is frozen** (`CLAUDE.md`'s Architecture
Change Policy). If you find yourself needing to change something described
in this document at a structural level — not add a new provider or feature
using the existing patterns, but change the patterns themselves — the
process is: stop, explain why, explain alternatives, identify roadmap
impact, propose a new ADR, and wait for explicit approval before
implementing. This isn't bureaucracy for its own sake — nearly every ADR in
`ARCHITECTURE_DECISIONS.md` exists because an earlier, less-considered
version of that decision caused a real problem.

---

## 9. How work actually gets done here (the milestone workflow)

Every milestone follows the same 13-step sequence documented in full in
`CLAUDE.md`: scope it exactly (nothing more, nothing less) → tests → lint →
type-check → production builds → verify both apps boot → verify migrations
→ update `PLAN.md` → append to `BUILD_LOG.md` → append an ADR *only if* a
real architectural decision occurred → commit → report the commit hash →
**stop and wait for approval** before starting the next milestone. The
"stop and wait" step is not a formality — read `BUILD_LOG.md`'s entries and
you'll see multiple milestones that were explicitly paused mid-stream by
direct user instruction (e.g. requiring AI cost control before a backfill
was allowed to proceed). Don't self-authorize the next milestone because the
current one went well.
