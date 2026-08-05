# Build Log — Nexus Credit Intelligence

This is the engineering journal for the project. **Entries are never rewritten** —
each completed milestone appends a new dated section below the previous one. If a
prior decision or entry turns out to be wrong, a later entry says so explicitly; it
does not edit history.

For the current architecture and roadmap, see `PLAN.md`. For the reasoning behind
specific architectural choices, see `ARCHITECTURE_DECISIONS.md`. This file answers a
different question than either of those: *what actually happened, in what order, and
what did it take.*

## Entry format

Each entry uses this template:

```
## [Date] — Milestone N: <name>

**Summary**

**Features Completed**

**Files Created**

**Files Modified**

**Database Changes**

**API Endpoints Added**

**Frontend Pages Added**

**Environment Variables Added**

**Tests Added**

**Test Results**

**Commands Executed**

**Deployment Validation**

**Problems Encountered**

**Solutions**

**Remaining Work**

**Git Commit Hash**

**Approximate Time Spent**

**Developer Notes**
```

Fields that don't apply to a given entry are kept and marked `N/A` rather than
omitted, so the template stays scannable across entries.

---

## 2026-08-04 — Milestone 0: Architecture & Planning

**Summary**

No application code exists yet. This entry logs the planning phase that produced the
approved, frozen Version 1.0 architecture in `PLAN.md`, and the three-document
governance system (`PLAN.md` / `BUILD_LOG.md` / `ARCHITECTURE_DECISIONS.md`) this
project is now managed under. Everything here is documentation and decision-making,
not implementation — logged as its own milestone because it's real project history,
not because it satisfies the Implementation Rules gate (it doesn't need to; there's no
code to test, lint, or build yet).

**Features Completed**

- Initial brief translated into a data-model-first PLAN.md: canonical provenance
  model, entitlement/AI-safety engine, public-provider adapter interfaces (SEC EDGAR,
  OpenFIGI, FRED, CourtListener), disabled licensed-provider stubs (S&P Global,
  Octus, Bloomberg, LSEG LPC).
- Stack revised end-to-end: from an initial Node/TypeScript/Hono/Drizzle/SQLite plan
  to Python 3.12/FastAPI/SQLAlchemy 2/Alembic on Railway, Supabase-managed
  PostgreSQL + pgvector + pg_trgm, React/Vite/MUI/TanStack on Vercel.
- Eleven demo watchlists defined (ten coverage lists + one investment-grade benchmark
  list), candidate issuers listed pending real-data verification at implementation
  time.
- PACER handling scoped as inactive-but-documented: `PacerProvider` interface +
  `PACER_ENABLED` flag, no real login/retrieval in MVP, admin manual-upload path for
  RECAP-unavailable documents.
- Scope expanded to a full product surface: Credit Universe (primary workflow),
  Dashboard, Capital Structure, Universal Search, AI Research Assistant with a typed
  tool layer and `LLMProvider` protocol abstraction, Research Notes/Documents with
  versioning, Alerts, Users/Roles/Audit.
- Explicit domain layer adopted: Provider DTO → Normalizer → Canonical Domain Object
  → Repository → SQLAlchemy, so provider adapters never touch the ORM directly.
- Data-model corrections: `freshness` moved from a stored column to a computed
  read-time API property; `calculation.input_provenance_ids` (JSONB array) replaced
  by a normalized `calculation_input` join table; admin-uploaded documents corrected
  to use `provider = admin_upload` + `original_source` instead of being mislabeled
  `provider = pacer`.
- Phase 2 / Future Architecture documented (not implemented, not scheduled): canonical
  `CreditEvent` stream, Time Machine / as-of query architecture, a future Portfolio
  module, Data Quality scoring, background job architecture.
- Architecture frozen at Version 1.0; three-document governance system established
  (this file and `ARCHITECTURE_DECISIONS.md` created; `PLAN.md` restructured with
  Project Governance, Project Status, Milestone Status, Technical Debt, Known Issues,
  Next Immediate Goal, Implementation Rules, and Architecture Change Policy sections).

**Files Created**

- `PLAN.md`
- `BUILD_LOG.md` (this file)
- `ARCHITECTURE_DECISIONS.md`

**Files Modified**

- `PLAN.md` (multiple revisions across the planning conversation — stack swap,
  scope expansion, data-model fixes, governance sections added)

**Database Changes**

N/A — no migrations exist yet. Full target schema is documented in `PLAN.md` §4.

**API Endpoints Added**

N/A — no backend exists yet. Target routes documented in `PLAN.md` §17.

**Frontend Pages Added**

N/A — no frontend exists yet. Target pages documented in `PLAN.md` §17.

**Environment Variables Added**

N/A — no `.env.example` file created yet; the full target variable set is documented
in `PLAN.md` §19.

**Tests Added**

N/A.

**Test Results**

N/A — nothing to run yet.

**Commands Executed**

N/A — planning/documentation only, no shell commands run against the project.

**Deployment Validation**

N/A — no deployable artifact exists yet.

**Problems Encountered**

- Initial stack choice (Node/Hono/Drizzle/SQLite) was superseded mid-planning by a
  hard requirement for Supabase-managed Postgres in every environment, Railway
  backend hosting, and a React/Vite/MUI/TanStack frontend on Vercel — required a full
  stack-and-module-tree rewrite of `PLAN.md` rather than an incremental patch.
- Original PACER handling design mislabeled every manually uploaded court document's
  provenance as `provider = pacer`, which falsely implied a real PACER retrieval.
  Caught during a later architecture review and corrected before any code was
  written (see ADR in `ARCHITECTURE_DECISIONS.md`).
- `calculation.input_provenance_ids` as a JSONB array was flagged as insufficient for
  referential-integrity lineage queries; replaced with a normalized join table before
  implementation began.

**Solutions**

- Rewrote `PLAN.md` in full rather than patch it piecemeal when the stack changed,
  since nearly every module and data-model detail was stack-specific.
- Introduced `admin_upload` as a distinct `provenance.provider` value with
  `original_source` / `source_attested_by` / `source_attested_at` fields, reserving
  `provider = pacer` exclusively for a real future PACER integration.
- Added `calculation_input` as a normalized many-to-many join table between
  `calculation` and `provenance`.

**Remaining Work**

Everything. See `PLAN.md` § Next Immediate Goal and § Milestone Status — Milestone 1
(Foundation) has not started.

**Git Commit Hash**

N/A — repository not yet initialized.

**Approximate Time Spent**

N/A — planning happened across an interactive design conversation, not a timed work
session.

**Developer Notes**

Architecture is now frozen at v1.0 (see `ARCHITECTURE_DECISIONS.md` and `PLAN.md` §
Architecture Change Policy). No further scope or stack changes should happen silently
during implementation — any genuinely necessary architecture change stops work,
gets explained, and gets a new ADR before continuing. Next real engineering entry in
this file should be Milestone 1.

---

## 2026-08-05 — Milestone 1: Foundation

**Summary**

Scaffolded the runnable vertical slice for Milestone 1: a FastAPI backend
(SQLAlchemy 2 + Alembic wired to Supabase, `/health`, structured config/logging) and
a React/Vite/MUI/TanStack Query frontend (routed app shell, placeholder navigation for
every future page, a live backend-status widget on the home page). Full scope match
against the Milestone 1 brief — no SEC/Credit Universe/providers/AI/watchlists/
research/dashboard work included, as instructed. Every gate in `PLAN.md` §
Implementation Rules that doesn't require a live Supabase connection is satisfied;
the Supabase-dependent gates are tracked as KI-001 pending real project credentials.

**Features Completed**

- FastAPI app (`backend/app/main.py`) with CORS middleware driven by
  `CORS_ALLOWED_ORIGINS`, and a dependency-free `GET /health` liveness endpoint.
- `pydantic-settings`-based `Settings` covering the full env var contract from
  `PLAN.md` § Environment Variables — every field optional/defaulted so the app boots
  in a bare environment.
- Structured logging setup (`app/logging_config.py`), level driven by `LOG_LEVEL`.
- SQLAlchemy 2 `Base` + a `get_db` session dependency that raises a clear error if
  `DATABASE_URL` is unset, rather than failing obscurely — and doesn't prevent the
  app from booting when it is unset (nothing in Milestone 1 touches the DB).
- Alembic wired to `DIRECT_DATABASE_URL`, with an initial migration (`0001`) that
  enables the `pgvector` and `pg_trgm` extensions the frozen architecture depends on.
  No tables yet — none are in Milestone 1's scope.
- React app shell: MUI theme, `react-router` routing, a `Layout` with a permanent nav
  drawer listing every future page (Credit Universe, Dashboard, Capital Structure,
  Watchlists, Search, Research Workspace, Alerts, Research Assistant) as disabled
  "Soon" placeholders, and a home page that calls `/health` via TanStack Query and
  displays live backend status — a concrete, visible proof the two halves of the
  stack can talk to each other.
- Dev tooling: Ruff, Black, Mypy (backend); ESLint (flat config) + Prettier + `tsc`
  (frontend) — all clean.
- Test suite: `pytest` + `TestClient` covering `/health`'s status code and payload
  shape.
- `backend/Dockerfile` + `backend/railway.toml` (Dockerfile builder, `/health`
  healthcheck) for Railway; `web/vercel.json` (SPA rewrites, Vite framework preset)
  for Vercel.
- `.github/workflows/ci.yml`: separate backend (ruff/black/mypy/pytest) and frontend
  (eslint/prettier/build) jobs.
- Root `.env.example` (backend) and `web/.env.example` (`VITE_API_BASE_URL`),
  matching `PLAN.md` § Environment Variables exactly.

**Files Created**

Backend: `backend/pyproject.toml`, `backend/alembic.ini`, `backend/Dockerfile`,
`backend/railway.toml`, `backend/app/__init__.py`, `backend/app/main.py`,
`backend/app/config.py`, `backend/app/logging_config.py`, `backend/app/db/__init__.py`,
`backend/app/db/base.py`, `backend/app/db/session.py`, `backend/app/api/__init__.py`,
`backend/app/api/routes/__init__.py`, `backend/app/api/routes/health.py`,
`backend/alembic/env.py`, `backend/alembic/script.py.mako`,
`backend/alembic/versions/0001_enable_extensions.py`, `backend/tests/__init__.py`,
`backend/tests/conftest.py`, `backend/tests/test_health.py`.

Frontend: `web/package.json`, `web/tsconfig.json`, `web/tsconfig.app.json`,
`web/tsconfig.node.json`, `web/vite.config.ts`, `web/index.html`,
`web/eslint.config.js`, `web/.prettierrc.json`, `web/.prettierignore`,
`web/vercel.json`, `web/.env.example`, `web/src/vite-env.d.ts`, `web/src/main.tsx`,
`web/src/App.tsx`, `web/src/theme.ts`, `web/src/api/client.ts`,
`web/src/queries/useHealth.ts`, `web/src/components/Layout.tsx`,
`web/src/pages/HomePage.tsx`, `web/src/pages/NotFoundPage.tsx`.

Infra/root: `.env.example`, `.gitignore`, `.github/workflows/ci.yml`.

**Files Modified**

- `PLAN.md` (§ Project Status, § Milestone Status, § Technical Debt, § Known Issues,
  § Next Immediate Goal updated for Milestone 1 completion).

**Database Changes**

- Migration `0001_enable_extensions`: `CREATE EXTENSION IF NOT EXISTS vector`,
  `CREATE EXTENSION IF NOT EXISTS pg_trgm`. No tables. Verified for correct Alembic
  mechanics (`alembic history`, `alembic heads` resolve cleanly); **not yet applied
  to a live Supabase database** — see Problems Encountered / KI-001.

**API Endpoints Added**

- `GET /health` → `{status, service, environment, timestamp}`.

**Frontend Pages Added**

- `/` (Home — backend status widget).
- Catch-all 404 page.
- Nav placeholders (not routed yet, disabled in the drawer): Credit Universe,
  Dashboard, Capital Structure, Watchlists, Search, Research Workspace, Alerts,
  Research Assistant.

**Environment Variables Added**

Full set from `PLAN.md` § Environment Variables, documented in `.env.example` /
`web/.env.example`: `ENVIRONMENT`, `LOG_LEVEL`, `DATABASE_URL`, `DIRECT_DATABASE_URL`,
`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_STORAGE_BUCKET`,
`SEC_USER_AGENT`, `FRED_API_KEY`, `OPENFIGI_API_KEY`, `COURTLISTENER_API_TOKEN`,
`FINRA_CLIENT_ID`, `FINRA_CLIENT_SECRET`, `PACER_USERNAME`, `PACER_PASSWORD`,
`PACER_ENABLED`, `SP_GLOBAL_ENABLED`, `OCTUS_ENABLED`, `BLOOMBERG_ENABLED`,
`LSEG_LPC_ENABLED`, `LLM_PROVIDER`, `LLM_API_KEY`, `AUTH_ENABLED`, `FRONTEND_URL`,
`CORS_ALLOWED_ORIGINS`, `VITE_API_BASE_URL`.

**Tests Added**

- `backend/tests/test_health.py`: `test_health_check_returns_200`,
  `test_health_check_payload_shape` (2 tests).

**Test Results**

```
backend: pytest -v
2 passed in 0.04s
```

No frontend unit tests added in Milestone 1 (no logic beyond routing/a query hook
yet); `npm run build` (which runs `tsc -b`) serves as the frontend correctness gate
for this milestone.

**Commands Executed** (representative, not exhaustive)

```
winget install --id Python.Python.3.12 -e --scope user
python -m venv backend/.venv
pip install -e ".[dev]"
pytest -v
ruff check . / ruff check --fix .
black --check .
mypy app
uvicorn app.main:app --host 127.0.0.1 --port 8000   (manual boot check, then killed)
alembic history / alembic heads                      (mechanics check, no live DB)

npm install
npm audit / npm audit fix
npm run lint
npm run format / npm run format:check
npm run build
npm run dev                                           (manual boot check, then killed)

git init
git add -A
```

**Deployment Validation**

Not exercised — Milestone 1 scope is local scaffolding + CI config, not an actual
Railway/Vercel deploy. `backend/railway.toml` and `web/vercel.json` are in place and
will be validated in Milestone 15 (§18) once there's something worth deploying beyond
`/health`.

**Problems Encountered**

- No Python 3.12 was installed on the machine (only 3.14). Installed 3.12.10 via
  `winget` to match the frozen architecture exactly, rather than deviating to 3.14
  silently.
- `npm audit` found 4 vulnerabilities in the initial dependency set: a moderate
  esbuild/dev-server issue (fixed by a Vite major bump), a moderate→high chain of
  React Router CVEs across the 6.x and early-7.x ranges (open redirect, then an RSC
  CSRF issue in 7.12–8.2), and — most concerning given this machine is Windows — a
  **high-severity** Vite `server.fs.deny` bypass on Windows alternate paths, patched
  only in Vite 8.
- `pyproject.toml`'s initial `[tool.ruff] exclude = [...]` and `[tool.mypy] exclude`
  used plain `exclude`, which replaces Ruff's default exclude list (including
  `.venv`) rather than adding to it — Ruff started linting the entire virtualenv.
- No real Supabase project exists yet for this environment, so `DATABASE_URL`/
  `DIRECT_DATABASE_URL` are unset — `alembic upgrade head` against a live database
  has not been run, and pgvector/pg_trgm extension creation is unverified against a
  real Supabase instance.

**Solutions**

- Installed Python 3.12.10 via `winget install --id Python.Python.3.12` and built the
  backend venv against it explicitly rather than the system's Python 3.14.
- Resolved the dependency vulnerabilities by upgrading rather than pinning around
  them, since none of the upgrades touched frozen architecture (routing library and
  build tool choices are implementation details, not §1–23 decisions): React 18→19,
  `react-router-dom`→`react-router` v8 (the packages were unified upstream as of
  v7), Vite 5→8, `@vitejs/plugin-react` 4→6. Re-ran `npm audit` after each change
  until it reported zero vulnerabilities.
- Changed `[tool.ruff] exclude` to `extend-exclude` (adds to Ruff's defaults instead
  of replacing them) and added an explicit `.venv` exclude to `[tool.mypy]`.
- Logged the missing Supabase credentials as KI-001 in `PLAN.md` § Known Issues
  rather than fabricating a connection or silently skipping the check — Milestone 1's
  "Supabase connects" / "Alembic migration succeeds" criteria are marked pending, not
  falsely marked done.

**Remaining Work**

- KI-001: obtain real Supabase dev-project credentials, run `alembic upgrade head`
  against it, confirm `pgvector`/`pg_trgm` extensions actually create successfully on
  Supabase (not just that the migration is well-formed locally).
- Everything in Milestone 2 onward per `PLAN.md` § Milestone Status.

**Git Commit Hash**

See the commit immediately following this entry in git history (this entry was
written as part of that same commit).

**Approximate Time Spent**

Single focused implementation session.

**Developer Notes**

Deliberately did not stub out DB-touching code paths to "look" connected — `/health`
stays dependency-free by design (per `PLAN.md` §2), and `get_db()` fails loudly with
a clear message if `DATABASE_URL` is missing rather than silently returning `None` or
a fake session. This keeps Milestone 1's "backend starts successfully" claim honest:
it starts successfully *because* nothing in this milestone requires the database yet,
not because a failure was hidden.
