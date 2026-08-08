# Nexus Credit Intelligence

A provenance-first, AI-enabled credit research operating system for distressed-credit
and leveraged-finance investment professionals. Every fact the application displays
carries provenance — provider, source record, as-of date, retrieval timestamp,
freshness, and classification (public / licensed / synthetic / AI-extracted) — so
nothing is shown without a traceable origin.

**Credit Universe** — a screenable, filterable table of bonds and loans — is the
primary Version 1 workflow: the goal is to cut the manual work investment
professionals currently do to screen credits across scattered sources.

---

## Project status

**Milestone 1 (Foundation) is complete.** The backend and frontend scaffolds boot,
pass their full lint/type-check/test suites, and are wired to Supabase — but no
canonical domain tables, provider adapters, or product features exist yet. Those
begin at Milestone 2.

For the authoritative, currently-accurate status (current milestone, progress
percentage, known issues, next goal), see **[`PLAN.md`](./PLAN.md) § Project Status**
— this README is a stable overview and is not re-synced line-by-line every milestone
the way `PLAN.md` is.

**Known limitation:** live Supabase migration verification (`alembic upgrade head`
against a real project, `pgvector`/`pg_trgm` extension creation) is **pending valid
development credentials** and has not yet been run against an actual Supabase
database. See `PLAN.md` § Known Issues (KI-001).

---

## Architecture

```
React/Vite on Vercel
         |
         | HTTPS REST API
         v
FastAPI on Railway
         |
         | PostgreSQL connection
         v
Supabase PostgreSQL + pgvector + pg_trgm  (+ Supabase Storage for large documents)
```

Backend and frontend are deployed and built independently — the backend never serves
frontend assets. Full architecture (domain model, provider architecture, AI
architecture, entitlement engine, security model) is documented in `PLAN.md`.

---

## Technology stack

**Backend:** Python 3.12, FastAPI, Pydantic 2, SQLAlchemy 2, Alembic, hosted on
Railway.

**Database:** Supabase-managed PostgreSQL only, in every environment (local dev,
test, staging, production) — no local or Dockerized Postgres, no SQLite anywhere.
`pgvector` (gated embeddings) and `pg_trgm` (fuzzy search) extensions enabled.
Supabase Storage for durable documents and large raw provider payloads.

**Frontend:** React, TypeScript, Vite, Material UI, TanStack Query, TanStack Table,
hosted on Vercel.

**Dev tooling:** Ruff, Black, MyPy, Pytest (backend); ESLint, Prettier (frontend);
`pre-commit` for fast local checks; GitHub Actions for CI.

See `CLAUDE.md` § Approved Stack for the full list and explicit prohibitions
(no Hono, no Drizzle, no backend-served frontend assets, no durable use of Railway's
local filesystem).

---

## Repository structure

```
backend/
  app/
    main.py            FastAPI app, CORS, router registration
    config.py           pydantic-settings configuration
    logging_config.py    structured logging setup
    db/                   SQLAlchemy 2 base + session
    api/routes/             HTTP routes (thin — call services/repositories)
  alembic/                Migrations (targets DIRECT_DATABASE_URL)
  tests/                    Pytest suite
  pyproject.toml, Dockerfile, railway.toml

web/
  src/
    main.tsx, App.tsx     App entry, routing
    theme.ts                MUI theme
    api/client.ts             Fetch wrapper (VITE_API_BASE_URL)
    queries/                    TanStack Query hooks
    components/, pages/           UI
  package.json, vite.config.ts, vercel.json

.github/
  workflows/ci.yml        Backend + frontend CI
  ISSUE_TEMPLATE/, pull_request_template.md

PLAN.md                   Architecture, roadmap, status (authoritative)
BUILD_LOG.md                Append-only engineering journal
ARCHITECTURE_DECISIONS.md     Append-only ADR log
CLAUDE.md                       Operating guide for Claude Code
.pre-commit-config.yaml           Local fast-check git hooks
```

---

## Prerequisites

- Python 3.12 (exact minor version matters — the project pins `>=3.12,<3.13`)
- Node.js 20+ and npm
- Git
- A Supabase project (for anything beyond `/health` and the frontend shell) — see
  [Supabase configuration](#supabase-configuration)

---

## Environment setup

Copy the example env files and fill in real values as they become available (never
commit the copies — both are already git-ignored):

```bash
cp .env.example backend/.env
cp web/.env.example web/.env
```

`backend/.env` holds the full backend configuration (database, provider API keys,
feature flags — see `.env.example` for the complete list). `web/.env` holds only
`VITE_API_BASE_URL`. With no `backend/.env` at all, the backend still boots and
`/health` still works — nothing in Milestone 1 requires the database.

---

## Backend — local run

```bash
cd backend
python -m venv .venv
./.venv/Scripts/pip install -e ".[dev]"      # Windows
# source .venv/bin/activate && pip install -e ".[dev]"   # macOS/Linux

./.venv/Scripts/python -m uvicorn app.main:app --reload   # Windows
# uvicorn app.main:app --reload                            # macOS/Linux, venv active
```

Backend runs at `http://localhost:8000`. Verify with `curl http://localhost:8000/health`.

**Backend commands**

```bash
cd backend
./.venv/Scripts/python -m pytest -v          # tests
./.venv/Scripts/python -m ruff check .       # lint
./.venv/Scripts/python -m black --check .    # format check
./.venv/Scripts/python -m mypy app           # type check
./.venv/Scripts/python -m alembic upgrade head   # migrations (needs DIRECT_DATABASE_URL)
```

---

## Frontend — local run

```bash
cd web
npm install
npm run dev
```

Frontend runs at `http://localhost:5173` and expects the backend at
`VITE_API_BASE_URL` (default `http://localhost:8000`).

**Frontend commands**

```bash
cd web
npm run lint            # ESLint
npm run typecheck       # tsc -b
npm run format:check    # Prettier check
npm run build            # production build (tsc -b && vite build)
npm audit                 # dependency vulnerability check
```

---

## Pre-commit hooks

Fast local checks (lint/format/type-check, scoped to whichever half of the repo
changed) run automatically on `git commit`. Full test suites and production builds
stay in CI, not in the hook, so commits stay fast.

```bash
python -m pip install pre-commit
pre-commit install
pre-commit run --all-files   # run everything on demand, e.g. after first install
```

See `.pre-commit-config.yaml` for exactly what runs and why (including a Windows-
specific path-escaping note for the backend hooks).

---

## Supabase configuration

This project uses **Supabase-managed PostgreSQL only** — in local development,
test, staging, and production alike. There is no local or Dockerized Postgres
fallback.

**This project reuses an existing Supabase project that also supports another
application.** Nexus does not get (and does not need) a dedicated Supabase
project — it is fully isolated inside its own Postgres schema, `nexus`. Every
Nexus table, index, sequence, and the Alembic version table live in
`nexus.*`; Nexus never reads, writes, migrates, renames, or drops anything in
`public` or any other schema, and never drops or recreates the `vector` /
`pg_trgm` extensions (they're database-wide and may be relied on by the other
application). See `ARCHITECTURE_DECISIONS.md` ADR-013 for the full rationale.

1. Use the existing Supabase project — no new project is created for Nexus.
2. Enable the `pgvector` and `pg_trgm` extensions if not already enabled (the
   initial Alembic migration, `0001_enable_extensions`, does this via
   `CREATE EXTENSION IF NOT EXISTS` and also creates the `nexus` schema via
   `CREATE SCHEMA IF NOT EXISTS`; the project's Postgres role needs privilege to
   run both).
3. Set `DATABASE_URL` (pooled connection, used by the running app) and
   `DIRECT_DATABASE_URL` (direct connection, used by Alembic — get it from
   Supabase Dashboard > Connect > "Direct connection") in `backend/.env` locally,
   or as Railway environment variables in deployment.
4. Set `SUPABASE_URL`, `SUPABASE_ANON_KEY` (reserved for future frontend/RLS use),
   and `SUPABASE_SERVICE_KEY` (backend-only, never exposed to the frontend) from
   the same Supabase project's API settings.
5. `SUPABASE_STORAGE_BUCKET` is optional at this milestone — Supabase Storage
   integration (a new, private bucket, e.g. `nexus-private-documents`; never the
   other application's bucket) is deferred to the document/provider milestone
   that needs it.
6. Run migrations: `cd backend && ./.venv/Scripts/python -m alembic upgrade head`.
   This requires `DIRECT_DATABASE_URL` to be set.

**Not yet verified end-to-end against a real Supabase project** — see
[Project status](#project-status).

---

## Railway backend deployment (overview)

`backend/railway.toml` configures a Dockerfile build (`backend/Dockerfile`) with a
`/health` healthcheck. Deployment steps:

1. Create a Railway service pointed at this repository with `backend/` as the root
   directory.
2. Set the environment variables from `.env.example` as Railway service variables
   (never commit real values). **`CORS_ALLOWED_ORIGINS` must include the deployed
   Vercel frontend's exact origin** (e.g.
   `CORS_ALLOWED_ORIGINS=https://nexus-credit-intelligence.vercel.app`) — the FastAPI
   `CORSMiddleware` (`backend/app/main.py`) only allows origins in this list, never a
   wildcard, so preflight (`OPTIONS`) and actual requests from any other origin,
   including an unset/default-only value, are correctly rejected by the browser.
3. Railway builds `backend/Dockerfile` and runs the container; `/health` gates
   deploy health.

Deployed: https://nexus-credit-intelligence-production.up.railway.app.

---

## Vercel frontend deployment (overview)

`web/vercel.json` configures the Vite build (`npm run build`, output `dist/`) with
SPA rewrites. Deployment steps:

1. Create a Vercel project pointed at this repository with `web/` as the root
   directory.
2. Set `VITE_API_BASE_URL` to the deployed Railway backend's URL.
3. Vercel builds and serves the static output; the backend must have
   `CORS_ALLOWED_ORIGINS` (see above) set to this project's deployed origin, or
   requests from the browser will be blocked by CORS regardless of how correctly
   the frontend itself is configured.

Deployed: https://nexus-credit-intelligence.vercel.app.

---

## Data sources

Public, real-data providers planned for later milestones (see `PLAN.md` for verified
endpoint contracts): SEC EDGAR, OpenFIGI, FRED, CourtListener/RECAP, FINRA TRACE
(via a legally-obtained sample dataset, since FINRA TRACE has no free public API).
Licensed-provider interfaces (S&P Global, Octus, Bloomberg, LSEG LPC) are built as
disabled stubs — "unavailable, license required" — never as silent synthetic
substitutes. PACER is built as an inactive interface (`PACER_ENABLED=false`);
CourtListener/RECAP is the primary docket source, with an admin manual-upload path
for documents RECAP doesn't have.

### Real-data vs. synthetic-data policy

- Synthetic data is used **only** where the brief explicitly allows it — primarily
  leveraged-loan pricing fields, since loan pricing has no public data source.
- Every synthetic record is tagged `SYNTHETIC_DEMO_DATA` in both the data model and
  the UI. It is never presented as if it were a real market fact.
- The application stays functional when any single provider is unavailable.

---

## Security and provenance principles

- No displayed fact exists without a `provenance` record (provider, source, as-of
  date, retrieval timestamp, freshness, classification).
- Calculated values retain calculation lineage (inputs, method) rather than
  appearing as bare numbers.
- Licensed data passes a single `policy_check` gate before display, export,
  embedding, LLM prompt inclusion, or API exposure — enforced once, not
  re-implemented per feature.
- Freshness is computed dynamically at read time; it is never a stored value that
  can silently go stale.
- No secrets are committed. Credentials come from environment variables locally and
  from Railway/Vercel environment configuration in deployment.

Full detail: `PLAN.md` § Provenance and Entitlement engine sections; enforcement
summary: `CLAUDE.md` § Provenance and Entitlement Rules.

---

## Milestone roadmap (summary)

Sixteen milestones, one vertical slice at a time — Foundation → provenance/
entitlement engine → SEC adapter → Credit Universe → OpenFIGI/FRED → issuer detail +
Capital Structure → CourtListener → watchlists → research notes/documents → alerts →
TRACE → universal search → AI Research Assistant → licensed-provider stubs →
deployment validation → end-to-end completion-criteria verification.

Full roadmap with current status per milestone: `PLAN.md` § Milestone Status.

---

## Further reading

- **[`PLAN.md`](./PLAN.md)** — architecture, technology stack, domain model, provider
  architecture, AI architecture, security model, milestone roadmap, completion
  criteria, and current implementation status. Authoritative if any document
  conflicts with another.
- **[`BUILD_LOG.md`](./BUILD_LOG.md)** — append-only engineering journal, one entry
  per completed milestone.
- **[`ARCHITECTURE_DECISIONS.md`](./ARCHITECTURE_DECISIONS.md)** — append-only
  Architecture Decision Records.
- **[`CLAUDE.md`](./CLAUDE.md)** — permanent operating guide for Claude Code
  contributing to this repository.
