# CLAUDE.md

Permanent operating guide for Claude Code (or any engineer) working in this
repository. This file summarizes and enforces the rules approved in `PLAN.md`; it
does not duplicate the plan in full. When in doubt, read `PLAN.md`.

---

# Project Purpose

Nexus Credit Intelligence is a provenance-first, AI-enabled credit research
operating system for distressed-credit and leveraged-finance investment
professionals. Every fact the application displays carries provenance: provider,
source record ID/URL, as-of date, retrieval timestamp, freshness, transformation
status (reported vs. calculated), and classification (public / licensed / synthetic /
AI-extracted). If a value can't carry that lineage, it doesn't get displayed.

**Credit Universe is the primary Version 1 workflow** — a screenable table of bonds
and loans that reduces manual work for investment professionals. It is the landing
page after login/demo entry, not a secondary feature. Issuer detail, lineage views,
and every other page are drill-downs from it, not replacements for it.

---

# Authoritative Documents

| Document | Responsibility |
|---|---|
| `PLAN.md` | Architecture, technology stack, domain model, provider architecture, AI architecture, security model, milestone roadmap, completion criteria, and current implementation status. Not a chronological log. |
| `BUILD_LOG.md` | Append-only engineering journal — one entry per completed milestone. Never rewritten. |
| `ARCHITECTURE_DECISIONS.md` | Append-only Architecture Decision Records (ADRs) — one per significant architectural choice, with alternatives and tradeoffs. Never rewritten. |
| `README.md` | Developer- and user-facing repository overview: what this is, how to run it, how to deploy it. |
| `CLAUDE.md` (this file) | Permanent implementation instructions for Claude Code. |

**If documents conflict, `PLAN.md` is authoritative.**

---

# Approved Stack

- Python 3.12
- FastAPI
- Pydantic 2
- SQLAlchemy 2
- Alembic
- Supabase-managed PostgreSQL only, in every environment
- pgvector
- pg_trgm
- Supabase Storage (for durable documents and large raw payloads)
- Railway (backend hosting)
- React
- TypeScript
- Vite
- Material UI
- TanStack Query
- TanStack Table
- Vercel (frontend hosting)

**Explicitly prohibited:**

- Local PostgreSQL, in any environment, including local development
- Dockerized PostgreSQL / PostgreSQL in Docker Compose
- SQLite, anywhere, for anything
- Hono
- Drizzle
- The backend serving frontend assets (frontend and backend are deployed and built
  independently)
- Durable use of Railway's local filesystem — Railway's disk is ephemeral; durable
  data lives in Supabase Postgres or Supabase Storage

Docker is permitted only as an optional packaging step for the Railway backend
(a `Dockerfile`), never for running a database.

---

# Architecture Boundaries

Fixed data flow, no exceptions:

```
External Provider
    ↓
Provider DTO
    ↓
Normalizer
    ↓
Canonical Domain Object
    ↓
Repository
    ↓
SQLAlchemy / Supabase PostgreSQL
```

- Providers must **never** perform SQLAlchemy session operations. A provider module
  produces DTOs and canonical domain objects; it does not import `app.db.session` or
  open a session.
- Only repository modules (`backend/app/repositories/**`) touch the ORM/session.
- API routes stay thin — they call services or repositories, not the ORM directly,
  and contain no normalization or business logic of their own.
- AI tools call typed services/repositories exactly like any other caller. They must
  **never** execute arbitrary SQL, and never get broader access than an equivalent
  human-facing API endpoint already has.

---

# Provenance and Entitlement Rules

- No displayed fact may exist without a `provenance` row backing it.
- Calculated values must retain calculation lineage via `calculation` +
  `calculation_input` — never a bare number with no traceable inputs.
- Licensed data must pass `policy_check` before display, export, embedding, prompt
  inclusion, document download, or API exposure.
- No licensed content may be exported, embedded, displayed, or sent to an LLM without
  a passing `policy_check` for that specific action.
- Synthetic data must be clearly labeled `SYNTHETIC_DEMO_DATA` in both the data model
  (`is_synthetic` / `synthetic_reason`) and the UI.
- Freshness (`live`/`cached`/`stale`) is calculated dynamically at read time from
  `retrieved_at` + a provider TTL policy. It is never persisted as a stored fact that
  can silently drift from the truth.
- Admin-uploaded documents must use `provider = admin_upload` with an explicit
  `original_source` (`pacer`\|`courtlistener`\|`issuer_site`\|`other`), never
  `provider = pacer` — `pacer` is reserved exclusively for documents the system
  actually retrieves through a real PACER integration.

---

# Coding Standards

**Backend**

- Typed Python throughout; no untyped function signatures in application code.
- Ruff, Black, MyPy must pass before a milestone is considered complete.
- Pytest for all test coverage.
- Clear service/repository boundaries — no business logic embedded in routes, no
  persistence logic embedded in providers.
- No hidden global database sessions — sessions come from the `get_db` dependency (or
  an equivalent explicit factory), never a module-level singleton reused across
  requests.
- Structured logging (`app/logging_config.py`), not bare `print`.
- Explicit error handling — no silent `except Exception: pass`; failures either
  propagate with a clear message or are handled with a documented reason.
- No secrets in source code. All credentials and API keys come from environment
  variables (`.env` locally, Railway env vars in deployment), never hardcoded.

**Frontend**

- Strict TypeScript (`strict: true`, `noUncheckedIndexedAccess: true`).
- ESLint and Prettier must pass before a milestone is considered complete.
- Material UI for components; TanStack Query for all server state (no ad hoc
  `fetch`-in-`useEffect` data fetching); TanStack Table for institutional data grids
  (Credit Universe and similar dense tabular views).
- Accessible components — semantic HTML, labeled interactive elements, keyboard
  navigability.
- Every data-fetching view has clear loading, empty, and error states — never a
  blank screen while data is missing or failing to load.

---

# Testing Rules

- Unit tests are required for domain logic and policy logic (`policy_check` and
  anything gating licensed/synthetic data).
- Integration tests are required for repositories and APIs where practical.
- Frontend tests are required for meaningful behavior (not for trivial
  presentational components with no logic).
- All existing tests must continue passing at every milestone boundary.
- No milestone may be marked complete with known failing tests.

---

# Milestone Workflow

Work on one milestone at a time. Before starting the next milestone:

1. Complete the current milestone's scope — nothing more, nothing less.
2. Run tests.
3. Run linting.
4. Run type checking.
5. Run production builds.
6. Verify the backend and frontend both boot.
7. Verify migrations when Supabase credentials are available (if not available yet,
   record it as a known issue rather than skipping silently).
8. Update `PLAN.md` (Project Status, Milestone Status, Technical Debt, Known Issues,
   Next Immediate Goal).
9. Append a new entry to `BUILD_LOG.md`.
10. Append a new ADR to `ARCHITECTURE_DECISIONS.md` — **only if** a significant
    architecture decision actually occurred. Ordinary tooling/dependency/doc changes
    do not need an ADR.
11. Commit changes.
12. Report the commit hash.
13. Stop and wait for approval before starting the next milestone.

---

# Architecture Change Policy

**The Version 1.0 architecture (PLAN.md §1–23) is frozen.**

Claude Code must never silently change architecture. If a material architecture
change becomes necessary during implementation:

1. **Stop** implementation on the affected path.
2. **Explain** the reason the change is needed.
3. **Explain** alternatives considered and their tradeoffs.
4. **Identify** the impact on the roadmap (`PLAN.md` §18).
5. **Propose** a new ADR describing the change.
6. **Wait for approval** before implementing it.

---

# Git Safety Rules

- Never commit `.env` files, secrets, credentials, tokens, licensed datasets, or
  confidential documents.
- Never force-push.
- Never rewrite published history.
- Never delete remote branches without explicit approval.
- Never commit generated caches, virtual environments, build output, or
  `node_modules`.
- Use concise, conventional-style commit messages.
- Keep the working tree clean at milestone boundaries — no stray untracked or
  modified files left behind when a milestone is reported complete.

---

# Current Project State

**Milestone 1 (Foundation) is complete.** Milestone 1 hardening (branch rename to
`main`, `CLAUDE.md`, pre-commit hooks, `README.md`, GitHub templates, GitHub remote
connection) is in progress/complete per the latest `BUILD_LOG.md` entry — check
`PLAN.md` § Project Status and § Milestone Status for the current, authoritative
state.

**Milestone 2 has not started.**

Live Supabase migration verification (`alembic upgrade head` against a real project,
`pgvector`/`pg_trgm` extension creation) remains pending until valid development
credentials are configured — tracked as KI-001 in `PLAN.md` § Known Issues.
