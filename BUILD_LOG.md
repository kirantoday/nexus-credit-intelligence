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

`79ca39512737d7d80bab6ad7d5973870c6cc9655` (`79ca395`)

**Approximate Time Spent**

Single focused implementation session.

**Developer Notes**

Deliberately did not stub out DB-touching code paths to "look" connected — `/health`
stays dependency-free by design (per `PLAN.md` §2), and `get_db()` fails loudly with
a clear message if `DATABASE_URL` is missing rather than silently returning `None` or
a fake session. This keeps Milestone 1's "backend starts successfully" claim honest:
it starts successfully *because* nothing in this milestone requires the database yet,
not because a failure was hidden.

---

## 2026-08-05 — Milestone 1 Hardening

**Summary**

Process/tooling/documentation hardening on top of the already-approved Milestone 1
foundation — explicitly **not** Milestone 2 work. No models, providers, business
features, SEC integrations, Credit Universe functionality, AI functionality, or
database tables were touched. Scope: rename the default branch to `main`, add
`CLAUDE.md` as Claude Code's permanent operating guide, add fast local pre-commit
checks, add a real `README.md`, add GitHub issue/PR templates, re-verify the entire
Milestone 1 check suite, update governance docs, and connect + push to the GitHub
remote.

**Features Completed**

- Renamed the local default branch from `master` to `main`; confirmed no leftover
  `master` references anywhere in the repo outside of `PLAN.md`'s own status table
  (which was updated).
- Added `CLAUDE.md`: Project Purpose, Authoritative Documents, Approved Stack (with
  explicit prohibitions), Architecture Boundaries, Provenance and Entitlement Rules,
  Coding Standards, Testing Rules, Milestone Workflow, Architecture Change Policy,
  Git Safety Rules, and Current Project State.
- Added `.pre-commit-config.yaml`: standard hygiene hooks (trailing whitespace,
  end-of-file, merge-conflict markers, large files, private keys, YAML/TOML/JSON
  validity) plus local hooks calling the already-installed backend venv tools
  (Ruff, Black, MyPy, a fast Pytest run) and frontend npm scripts (ESLint, Prettier
  check, `tsc` type check) — each scoped by `files:` regex so a docs-only commit
  doesn't pay for backend/frontend checks it doesn't need. Installed the git hook
  (`pre-commit install`) and ran `pre-commit run --all-files` clean.
- Added a `typecheck` script to `web/package.json` (`tsc -b`) so the pre-commit
  frontend type-check hook and any future CI step invoke type-checking the same way
  `npm run lint`/`format:check` already do, rather than a one-off `npm exec` form
  that resolved paths incorrectly (see Problems Encountered).
- Added `pre-commit` to `backend/pyproject.toml`'s `dev` extra so it installs via the
  same `pip install -e ".[dev]"` step as the rest of the dev toolchain.
- Added `README.md`: product description, project status (linking to `PLAN.md` as
  the authoritative live source rather than duplicating it), architecture diagram,
  stack, repository structure, prerequisites, environment setup, backend/frontend
  local run instructions, all check commands, pre-commit usage, Supabase/Railway/
  Vercel deployment overviews (explicitly marked not-yet-deployed where true),
  data-source and synthetic-data policy, security/provenance principles, roadmap
  summary, and links to the other three governance documents.
- Added GitHub templates: `bug_report.md`, `feature_request.md`,
  `architecture_change.md` (the latter mirroring `CLAUDE.md`'s Architecture Change
  Policy — context, proposed change, alternatives, tradeoffs, `PLAN.md` impact, ADR
  requirement, migration implications, approval status), and
  `pull_request_template.md` (with explicit provenance/entitlement and architecture
  checklists, not just generic PR boilerplate).
- Re-ran the full Milestone 1 verification suite after all of the above (see Test
  Results) to confirm nothing regressed.
- Checked GitHub remote state before touching it: `git remote -v` showed no `origin`;
  `git ls-remote https://github.com/kirantoday/nexus-credit-intelligence.git`
  returned exit code 0 with zero refs, confirming the target repository exists and
  is empty — safe to add as `origin` and push without any merge/rebase/force
  decision required.

**Files Created**

`CLAUDE.md`, `README.md`, `.pre-commit-config.yaml`,
`.github/ISSUE_TEMPLATE/bug_report.md`, `.github/ISSUE_TEMPLATE/feature_request.md`,
`.github/ISSUE_TEMPLATE/architecture_change.md`, `.github/pull_request_template.md`.

**Files Modified**

`PLAN.md` (branch `main`, Milestone 1 row marked "Complete (+ hardening)", Current
Status narrative, latest-commit reference), `backend/pyproject.toml` (added
`pre-commit` to the `dev` extra), `web/package.json` (added `typecheck` script).

**Database Changes**

None.

**API Endpoints Added**

None.

**Frontend Pages Added**

None.

**Environment Variables Added**

None.

**Tests Added**

None (no new application logic — hardening is tooling/process/docs only). Existing
backend test suite (2 tests) re-verified passing.

**Test Results**

```
backend: pytest -v            -> 2 passed
backend: ruff check .         -> All checks passed!
backend: black --check .      -> 15 files would be left unchanged.
backend: mypy app             -> Success: no issues found in 10 source files

frontend: npm run lint        -> clean
frontend: npm run typecheck   -> clean (tsc -b)
frontend: npm run format:check -> All matched files use Prettier code style!
frontend: npm run build       -> succeeded (dist/assets bundle 428.68 kB / gzip 136.05 kB)
frontend: npm audit           -> found 0 vulnerabilities

pre-commit run --all-files    -> all 15 hooks passed
```

**Commands Executed** (representative)

```
git branch -m master main

python -m pip install pre-commit   (into backend/.venv)
pre-commit install
pre-commit run --all-files

pytest -v / ruff check . / black --check . / mypy app
uvicorn app.main:app --host 127.0.0.1 --port 8010   (manual boot check, then killed)

npm run lint / npm run typecheck / npm run format:check / npm run build / npm audit
npm run dev                                          (manual boot check, then killed)

git status ; git branch --show-current ; git remote -v
git ls-remote https://github.com/kirantoday/nexus-credit-intelligence.git
git remote add origin https://github.com/kirantoday/nexus-credit-intelligence.git
git add -A ; git commit ...
git push -u origin main
```

**Deployment Validation**

Not exercised — still out of scope until Milestone 15. This entry only connects the
local repository to its GitHub remote; it does not deploy anything to Railway or
Vercel.

**Problems Encountered**

- The `frontend-typecheck` pre-commit hook, written as
  `npm --prefix web exec tsc -- -b --noEmit`, resolved `tsconfig.json` against the
  repository root instead of `web/` (`error TS5083: Cannot read file
  '.../tsconfig.json'`) — `npm --prefix ... exec` does not change the effective
  working directory for the underlying command the way `npm --prefix ... run` does.
  Fixed by adding a real `typecheck` script to `web/package.json` and invoking it
  via `npm --prefix web run typecheck`, matching the pattern that already worked for
  `lint`/`format:check`.
- The backend pre-commit hooks (`backend-ruff`, `backend-black`, `backend-mypy`,
  `backend-pytest`) initially failed with `[WinError 2] The system cannot find the
  file specified` when the `entry` used a forward-slash path
  (`backend/.venv/Scripts/python.exe`) — reproduced directly against Python's
  `subprocess` module: Windows `CreateProcess` does not resolve that relative,
  forward-slash executable path in the no-shell invocation form pre-commit uses.
  Switching to a single-backslash Windows path
  (`backend\.venv\Scripts\python.exe`) then failed differently — `Executable
  'backend.venvScriptspython.exe' not found` — because pre-commit parses `entry`
  with `shlex.split()` in POSIX mode regardless of host OS, and POSIX shlex treats
  a single backslash as an escape character and drops it. Resolved by **doubling**
  every backslash in the YAML (`backend\\.venv\\Scripts\\python.exe`), verified by
  directly testing `shlex.split()` against both forms before settling on the fix.
  Documented inline in `.pre-commit-config.yaml` so this isn't rediscovered the
  hard way later.

**Solutions**

See above — both problems were root-caused by directly reproducing the failing
subprocess call outside of pre-commit/npm before changing the config, rather than
guessing at a fix.

**Remaining Work**

- KI-001 (unchanged): real Supabase dev-project credentials still needed to verify
  `alembic upgrade head` and `pgvector`/`pg_trgm` extension creation against a live
  database.
- Everything in Milestone 2 onward per `PLAN.md` § Milestone Status — unstarted, as
  required by this hardening pass's scope constraint.

**Git Commit Hash**

`c6c28116b39fc69132c517392067d7d8f5bb69bb` (`c6c2811`)

**GitHub Remote and Push Results**

- `git remote -v` (before): empty — no `origin` configured.
- `git ls-remote https://github.com/kirantoday/nexus-credit-intelligence.git`:
  exit code 0, zero refs returned — target repository exists and was empty, so no
  divergent-history decision was needed.
- `git remote add origin https://github.com/kirantoday/nexus-credit-intelligence.git`
  — added.
- `git push -u origin main` — succeeded: `* [new branch] main -> main`, upstream
  tracking set (`branch 'main' set up to track 'origin/main'`).
- Post-push verification: `git ls-remote origin` returns `c6c28116b39fc69132c517392067d7d8f5bb69bb`
  for both `HEAD` and `refs/heads/main`, matching the local commit exactly.
  `git status` reports `Your branch is up to date with 'origin/main'` and a clean
  working tree.
- Remote branch: https://github.com/kirantoday/nexus-credit-intelligence/tree/main

**Approximate Time Spent**

Single focused hardening session, following directly after Milestone 1.

**Developer Notes**

Kept pre-commit deliberately fast (formatting/lint/type-check + a small existing test
suite) and left full builds and the complete test matrix in CI, per instruction — as
the backend test suite grows past "fast," the `backend-pytest` hook should be
narrowed (e.g. to a marked `-m fast` subset) or removed from pre-commit rather than
left to slow down every commit; that tradeoff call belongs to whoever notices it
first getting slow, not a preemptive guess made here.

---

## 2026-08-05 — Supabase Schema-Isolation Configuration & Live Validation (pre-Milestone 2)

**Summary**

Before Milestone 2, the project owner directed that Nexus reuse an existing
Supabase project already supporting another application, instead of a dedicated
project, isolated entirely inside a `nexus` Postgres schema — documented as
ADR-013. This entry covers both the configuration/code work and its live
validation against the real, shared Supabase project, which closes KI-001.
Explicitly **not** Milestone 2: no canonical domain models, providers, or product
features were touched.

**Features Completed**

- `backend/app/config.py`: renamed `supabase_service_role_key` →
  `supabase_service_key` (env `SUPABASE_SERVICE_KEY`, matching the existing
  application's convention rather than Nexus's originally planned
  `SUPABASE_SERVICE_ROLE_KEY`); added `supabase_anon_key` (env
  `SUPABASE_ANON_KEY`, reserved for future frontend/RLS use). `DATABASE_URL`,
  `DIRECT_DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_STORAGE_BUCKET` names
  unchanged.
- `backend/app/db/base.py`: added `NEXUS_SCHEMA = "nexus"` constant;
  `Base.metadata` now defaults to schema `nexus`, so every SQLAlchemy model is
  schema-qualified by construction and can never land in `public` by accident.
- `backend/app/db/session.py`: app engine now sets `search_path=nexus,public` via
  `connect_args` — a second layer of isolation, never relied on alone.
- `backend/alembic/env.py`: added `include_schemas=True`,
  `version_table_schema="nexus"`, and an `include_name` filter restricting
  reflection/autogenerate comparison to the `nexus` schema only, on both the
  offline and online migration paths.
- `backend/alembic/versions/0001_enable_extensions.py`: upgrade now creates the
  `nexus` schema (`CREATE SCHEMA IF NOT EXISTS`) alongside the `vector`/`pg_trgm`
  extensions; downgrade no longer drops the extensions (shared, database-wide,
  possibly relied on by the other application) — it only drops the by-then-empty
  `nexus` schema, without `CASCADE`.
- `.env.example`, `README.md`, `PLAN.md` (§2 Stack, §19 env vars, §21 decisions
  log), `CLAUDE.md` (new "Supabase Project & Schema Isolation" section): updated
  to the new variable names and the shared-project/schema-isolation model.
- `ARCHITECTURE_DECISIONS.md`: added **ADR-013**, documenting this as a
  deliberate, approved deviation from ADR-001's dedicated-project assumption.
- **Pre-existing driver bug found and fixed** (unrelated to schema isolation, but
  blocking any real connection): `backend/.env`'s `DATABASE_URL` and, later,
  `DIRECT_DATABASE_URL` used a bare `postgresql://` scheme, which SQLAlchemy
  resolves to the `psycopg2` driver — not installed, since this project depends
  on `psycopg` v3 (`pyproject.toml`). Patched both to `postgresql+psycopg://`
  (scheme only; no secret values were displayed or logged at any point).
- **Alembic version-table bootstrap bug found and fixed**: Alembic creates its
  version table (`nexus.alembic_version`) before running any migration —
  including migration `0001`, which is what actually owns creating the `nexus`
  schema. The very first `alembic upgrade head` against a fresh database failed
  with `psycopg.errors.InvalidSchemaName: schema "nexus" does not exist`. Fixed
  in `backend/alembic/env.py`'s `run_migrations_online()` by having it execute
  `CREATE SCHEMA IF NOT EXISTS nexus` immediately after connecting, before
  `context.configure()`/Alembic's own version-table bookkeeping runs. Migration
  `0001` still independently issues its own `CREATE SCHEMA IF NOT EXISTS`
  (idempotent), so the migration file remains correct and self-contained on its
  own for anyone reading it in isolation.
- **Live migration anomaly found and corrected** (see Problems Encountered):
  `pg_trgm` was installed into `nexus` instead of `public` on the first live
  `alembic upgrade head` run, due to the `search_path=nexus,public` connection
  setting affecting Postgres's default extension-install target when no explicit
  `SCHEMA` clause is given. Corrected live with one explicitly user-approved
  `ALTER EXTENSION pg_trgm SET SCHEMA public` (a relocate, not a drop — verified
  relocatable, and verified to be the extension this same run had just created
  seconds earlier, not a pre-existing/shared extension being moved). Fixed at the
  source for all future/fresh databases by pinning `WITH SCHEMA public`
  explicitly on both `CREATE EXTENSION` statements in
  `0001_enable_extensions.py`, so this can't recur regardless of connection
  `search_path`.

**Files Created**

None.

**Files Modified**

`backend/app/config.py`, `backend/app/db/base.py`, `backend/app/db/session.py`,
`backend/alembic/env.py`, `backend/alembic/versions/0001_enable_extensions.py`,
`.env.example`, `README.md`, `PLAN.md`, `CLAUDE.md`, `ARCHITECTURE_DECISIONS.md`.
`backend/.env` (local, git-ignored, never committed): `DATABASE_URL` and
`DIRECT_DATABASE_URL` schemes corrected to `postgresql+psycopg://`.

**Database Changes**

Against the real, shared Supabase project (via `DIRECT_DATABASE_URL`):
- `CREATE SCHEMA IF NOT EXISTS nexus` (both via `env.py`'s bootstrap step and
  migration `0001` itself).
- `CREATE EXTENSION IF NOT EXISTS vector` — no-op; `vector` already existed in
  `public` (pre-existing, untouched, not created by Nexus).
- `CREATE EXTENSION IF NOT EXISTS pg_trgm` — created fresh (did not previously
  exist), initially landing in `nexus`, then relocated to `public` via one
  explicitly approved `ALTER EXTENSION pg_trgm SET SCHEMA public`.
- `CREATE TABLE nexus.alembic_version` (Alembic's own bookkeeping table),
  currently at revision `0001`.

No tables belonging to the other application were read, written, migrated,
renamed, truncated, or deleted. No unrelated schema's contents were inspected
beyond listing schema *names* (not contents) to confirm isolation.

**API Endpoints Added**

None.

**Frontend Pages Added**

None.

**Environment Variables Added**

`SUPABASE_ANON_KEY` (new). `SUPABASE_SERVICE_ROLE_KEY` renamed to
`SUPABASE_SERVICE_KEY`. `DATABASE_URL`, `DIRECT_DATABASE_URL`, `SUPABASE_URL`,
`SUPABASE_STORAGE_BUCKET` names unchanged (`SUPABASE_STORAGE_BUCKET` remains
optional/unused this milestone).

**Tests Added**

None (config/infrastructure change, not new application logic). Existing backend
test suite (2 tests) re-verified passing, both before and after the live
migration.

**Test Results**

```
backend: pytest -q                    -> 2 passed
backend: ruff check .                 -> All checks passed!
backend: black --check .              -> 15 files would be left unchanged.
backend: mypy .                       -> Success: no issues found in 14 source files

frontend: npm run lint                -> clean
frontend: npm run format:check        -> All matched files use Prettier code style!
frontend: npm run typecheck           -> clean (tsc -b)
frontend: npm run build               -> succeeded (dist/assets bundle 428.68 kB / gzip 136.05 kB)
frontend: npm audit                   -> found 0 vulnerabilities

pre-commit run --all-files            -> all hooks passed

alembic upgrade head (live)           -> upgraded base -> 0001
GET /health (live DB config)          -> 200 {"status": "healthy", ...}
SQLAlchemy session open/close (live)  -> OK; SHOW search_path -> nexus,public
```

All of the above was re-run in full a second time after the `pg_trgm` correction,
with identical results.

**Live Isolation Verification** (sanitized — no hostnames, credentials, project
identifiers, or full connection strings recorded anywhere in this entry)

- `DATABASE_URL`: transaction pooler (Supavisor), port 6543.
- `DIRECT_DATABASE_URL`: **true direct endpoint**, port 5432 — the IPv6 direct
  path worked; no fallback to the IPv4-compatible session pooler was needed.
- `nexus` schema: exists.
- `nexus.alembic_version`: exists, contains `0001`.
- `vector` extension: `public` (pre-existing, untouched).
- `pg_trgm` extension: `public` (created by this migration, corrected from an
  initial `nexus` placement — see Problems Encountered).
- Objects in `nexus` schema: exactly one — `alembic_version`. No other Nexus
  tables exist yet (expected; no models exist before Milestone 2).
- Objects in `public` matching Nexus's `alembic_version` table name: none.
- Other schemas on the shared project: confirmed present by name only (not
  inspected further); none were created, modified, or touched by this work.
- App-side `search_path` (as seen by an opened `SessionLocal` session via
  `DATABASE_URL`): `nexus,public`.

**Commands Executed** (representative; no secret values shown at any point)

```
# DATABASE_URL / DIRECT_DATABASE_URL scheme fix (local .env, git-ignored)
python -c "... patch postgresql:// -> postgresql+psycopg:// ..."

cd backend
./.venv/Scripts/python -m pytest -q
./.venv/Scripts/python -m ruff check .
./.venv/Scripts/python -m black --check .
./.venv/Scripts/python -m mypy .
./.venv/Scripts/python -m alembic upgrade head

# sanitized connection classification + live isolation checks (host/port
# category only, via urlsplit / information_schema / pg_extension queries)
./.venv/Scripts/python -c "... classify DATABASE_URL / DIRECT_DATABASE_URL ..."
./.venv/Scripts/python -c "... verify nexus schema / alembic_version / extensions ..."

# pg_trgm correction (explicitly approved before running)
./.venv/Scripts/python -c "... ALTER EXTENSION pg_trgm SET SCHEMA public ..."
./.venv/Scripts/python -c "... re-verify pg_trgm/vector/nexus state post-fix ..."

./.venv/Scripts/python -c "... FastAPI TestClient GET /health ..."
./.venv/Scripts/python -c "... SessionLocal open/close + SHOW search_path ..."

cd ../web
npm run lint && npm run format:check && npm run typecheck && npm run build && npm audit

cd ..
backend/.venv/Scripts/python -m pre_commit run --all-files

git status ; git diff --stat
```

**Deployment Validation**

Not exercised — Railway/Vercel deployment remains Milestone 15 scope, unaffected
by this entry.

**Problems Encountered**

1. **Driver/scheme mismatch**: `DATABASE_URL`/`DIRECT_DATABASE_URL` used a bare
   `postgresql://` scheme; SQLAlchemy defaults that to the `psycopg2` driver,
   which isn't installed (this project uses `psycopg` v3 per `pyproject.toml`).
   `create_engine()` failed with `ModuleNotFoundError: No module named
   'psycopg2'`. **Fixed** by rewriting the scheme to `postgresql+psycopg://` in
   `backend/.env` (local only, never committed).
2. **Alembic version-table/schema bootstrap ordering**: see Features Completed —
   Alembic tries to create `nexus.alembic_version` before running migration
   `0001` (which creates `nexus` itself), so the very first run against a fresh
   database failed with `InvalidSchemaName`. **Fixed** by having
   `alembic/env.py` ensure the `nexus` schema exists immediately after
   connecting, before `context.configure()`.
3. **`pg_trgm` extension mislocated on first live run**: `CREATE EXTENSION IF
   NOT EXISTS pg_trgm` (no explicit `SCHEMA` clause) installed into `nexus`
   rather than `public`, because the connection's `search_path` is
   `nexus, public` and `pg_trgm` did not already exist anywhere on this
   database — Postgres installed it into the first schema on the search path
   that existed. `vector` was unaffected because it already existed in `public`
   from before this project touched the database, so `CREATE EXTENSION IF NOT
   EXISTS vector` was a no-op. This directly conflicted with the project's
   explicit rule against dropping or relocating extensions, so validation
   paused and the anomaly was reported to the project owner rather than
   corrected unilaterally. **Fixed** two ways, both explicitly approved before
   execution: (a) live, one-time `ALTER EXTENSION pg_trgm SET SCHEMA public`,
   preceded by verification that `pg_trgm` was relocatable and had been created
   by this same run (the `nexus` schema itself didn't exist before this
   migration, so `pg_trgm` could not have pre-existed inside it) — not a
   pre-existing/shared extension being moved; (b) at the source, migration
   `0001` now pins `WITH SCHEMA public` explicitly on both `CREATE EXTENSION`
   statements so this can't recur on any other/future database regardless of
   connection `search_path`.

**Solutions**

All three problems were root-caused by directly querying live database state
(`pg_extension`, `information_schema`) rather than guessing, and the one
corrective action with a real (if narrow) risk — relocating `pg_trgm` — was
paused for explicit owner approval rather than taken unilaterally, given the
project's explicit written rule against extension drop/relocate operations.

**Remaining Work**

- KI-001: **closed** (see Known Issues in `PLAN.md`).
- Everything in Milestone 2 onward per `PLAN.md` § Milestone Status — unstarted;
  Milestone 2 requires separate approval to begin.

**Git Commit Hash**

`9f753c4cf53f3015eae4e04da91c3cb70c22646f` (`9f753c4`)

**GitHub Remote and Push Results**

- `git push origin main` — succeeded: `e8a5082..9f753c4  main -> main`.
- Post-push verification: `git ls-remote origin` returns
  `9f753c4cf53f3015eae4e04da91c3cb70c22646f` for both `HEAD` and
  `refs/heads/main`, matching the local commit exactly.
- Remote branch: https://github.com/kirantoday/nexus-credit-intelligence/tree/main

**Approximate Time Spent**

Single focused validation session, following directly after the initial
schema-isolation configuration work.

**Developer Notes**

The `pg_trgm` mislocation is a good illustration of why "never rely on
`search_path` alone" (PLAN.md §2) matters even for DDL, not just DML —
`CREATE EXTENSION` without an explicit `SCHEMA` clause is itself
search-path-sensitive, which isn't always the first place one would think to
look. Any future migration that creates a database-wide/shared object (another
extension, a shared type, etc.) should pin its schema explicitly rather than
depend on connection defaults, exactly as `0001` now does.

---

## 2026-08-06 — Milestone 2: Provenance, raw_provider_payload, calculation/calculation_input, entitlement engine

**Summary**

The platform foundation every later milestone depends on: the provenance spine
(`provenance`, `calculation`, `calculation_input`), the durable raw-response
store (`raw_provider_payload`), and the entitlement engine (`data_entitlement` +
`policy_check`) — implemented, migrated, and tested end-to-end against the live
Supabase project, with no provider adapters, API routes, or UI touched (out of
scope per milestone boundary). Also establishes ADR-014, the domain-layer
implementation conventions (Pydantic domain objects, function-style
repositories, text+CHECK over native Postgres enums) every later canonical
entity (issuer, security, financial_fact, and eventual Bloomberg/S&P
Global/Markit/Octus-backed data) will follow.

**Features Completed**

- `backend/app/core/types.py`: six shared `StrEnum` classes (`ProviderName`,
  `OriginalSource`, `TransformationType`, `DataClassification`,
  `EntitlementAction`, `EnvironmentName`) — the single source of truth reused by
  domain objects, ORM CHECK constraints, and (later) provider adapters.
- `backend/app/domain/provenance.py`, `raw_provider_payload.py`,
  `entitlement.py`: frozen Pydantic 2 canonical domain objects
  (`ProvenanceCreate`/`Provenance`, `CalculationCreate`/`Calculation`,
  `CalculationInputCreate`/`CalculationInput`, `RawProviderPayloadCreate`/
  `RawProviderPayload`, `DataEntitlementCreate`/`DataEntitlement`), each with
  `model_validator`s mirroring the DB-level invariants: `calculation_id` set iff
  `transformation == "calculated"`; `original_source` only set when
  `provider == "admin_upload"` (ADR-007); a raw payload must have
  `payload_json` or `storage_object_path`; `expiration_date >= effective_date`.
- `backend/app/models/provenance.py`, `raw_provider_payload.py`,
  `entitlement.py`: SQLAlchemy ORM models, schema-qualified to `nexus` via
  `Base.metadata`. Enum-shaped columns are `Text` + `CheckConstraint` (built
  from the same `core/types.py` enums), not native Postgres `ENUM` types —
  matches PLAN.md's explicit `text` typing and keeps "add a provider" an
  ordinary migration. `provenance.raw_payload_id` and
  `raw_provider_payload.provenance_id` are a real, intentional circular FK
  (PLAN.md 4.1/4.4), resolved via `ForeignKey(..., use_alter=True, name=...)`.
  FK columns get explicit indexes (Postgres doesn't auto-index them).
- `backend/app/core/entitlement.py`: `policy_check(action, classification,
  entitlement, context)` — the pure, single choke point for every licensed-data
  action (PLAN.md §4.8). Public/synthetic/AI-extracted data always passes;
  licensed data requires an active `DataEntitlement` matching environment,
  effective/expiration window, `permitted_users` allow-list, and the specific
  permission flag for the requested action. Action→flag mapping documented
  in-module (seven actions map onto five permission flags, since
  `data_entitlement` has one flag per broad capability, not one per action).
- `backend/app/repositories/provenance_repository.py`,
  `raw_provider_payload_repository.py`, `entitlement_repository.py`:
  function-style repositories (`db: Session` as first arg, domain objects
  in/out, never an ORM instance) — `flush()` but never `commit()`, so a caller
  can compose several repository calls into one unit of work.
  `find_active_entitlement` is the intended pairing with `policy_check`:
  repository resolves the entitlement (I/O), `policy_check` decides on it
  (pure) — proven together in
  `tests/integration/test_entitlement_repository.py::test_repository_lookup_feeds_policy_check_end_to_end`.
- `backend/app/db/session.py`: `get_db()` now commits once at the end of a
  successful request and rolls back on any exception (previously neither),
  matching the flush-not-commit repository convention above.
- `backend/alembic/env.py`: imports the three new model modules so
  autogenerate can see them.
- `backend/alembic/versions/0002_provenance_entitlement_foundation.py`: creates
  all five tables in `nexus`. **Hand-corrected after autogenerate**: the naive
  output embedded the circular FK inline inside `raw_provider_payload`'s
  `op.create_table(...)`, but compiling that DDL directly
  (`CreateTable(...).compile()`) proved SQLAlchemy's compiler silently *drops*
  any `use_alter=True` constraint from an inline `CREATE TABLE` — and
  autogenerate never emitted the separate `ALTER TABLE` that constraint needs,
  so it would never have been created at all. Fixed: `raw_provider_payload`
  creates without that FK, `provenance` is created afterward, and an explicit
  `op.create_foreign_key(...)` adds the constraint once both tables exist;
  `downgrade()` drops it first, before either table.
- `.pre-commit-config.yaml`: scoped `backend-pytest` to `tests/unit` +
  `tests/test_health.py` only. `tests/integration/**` now hits the live,
  network Supabase project — correct for CI/manual runs, too slow and
  network-fragile for every commit (flagged as a future risk in the Milestone 1
  Hardening entry; this is that point).
- `ARCHITECTURE_DECISIONS.md`: added **ADR-014** (domain-layer implementation
  conventions).

**Files Created**

`backend/app/core/types.py`, `backend/app/core/entitlement.py`,
`backend/app/domain/provenance.py`, `backend/app/domain/raw_provider_payload.py`,
`backend/app/domain/entitlement.py`, `backend/app/models/provenance.py`,
`backend/app/models/raw_provider_payload.py`, `backend/app/models/entitlement.py`,
`backend/app/repositories/provenance_repository.py`,
`backend/app/repositories/raw_provider_payload_repository.py`,
`backend/app/repositories/entitlement_repository.py`,
`backend/app/{core,domain,models,repositories}/__init__.py`,
`backend/alembic/versions/0002_provenance_entitlement_foundation.py`,
`backend/tests/unit/__init__.py`, `test_policy_check.py`,
`test_domain_validators.py`, `test_db_session.py`,
`backend/tests/integration/__init__.py`, `conftest.py`,
`test_provenance_repository.py`, `test_raw_provider_payload_repository.py`,
`test_entitlement_repository.py`.

**Files Modified**

`backend/app/db/session.py` (commit/rollback lifecycle in `get_db()`),
`backend/alembic/env.py` (model imports), `.pre-commit-config.yaml`
(`backend-pytest` scoped to unit tests), `PLAN.md`, `ARCHITECTURE_DECISIONS.md`.

**Database Changes**

Migration `0002` applied to the live, shared Supabase project: creates
`nexus.calculation`, `nexus.data_entitlement` (+ index), `nexus.raw_provider_payload`
(+ index), `nexus.provenance` (+ two indexes), `nexus.calculation_input` (+
index), then the hand-added `fk_raw_provider_payload_provenance_id` FK. Six
CHECK constraints enforce enum membership and the two cross-field invariants
(`calculation_id`/`transformation` linkage, `original_source`/`admin_upload`
linkage) at the DB level, independent of the Pydantic domain layer. Verified
with a full round-trip: `upgrade head` → `downgrade 0001` → `upgrade head`,
confirming clean creation and removal with nothing left behind.

**API Endpoints Added**

None (out of scope — foundation only).

**Frontend Pages Added**

None (out of scope — foundation only, and unaffected; re-verified green).

**Environment Variables Added**

None.

**Tests Added**

60 total (up from 2): 39 unit (`tests/unit/` — full `policy_check` coverage
across every action/classification/permission/date/environment/`permitted_users`
edge case; domain `model_validator` coverage; `get_db()` commit/rollback/error
paths via a mocked session, no I/O) + 21 integration (`tests/integration/` —
real round-trips against the live `nexus` schema: create/get for all three
repositories, the full calculation-with-inputs lineage scenario, two DB-level
CHECK-constraint-violation tests that bypass the Pydantic layer on purpose, and
the repository→`policy_check` composition test) + 2 pre-existing health tests.

**Test Results**

```
backend: pytest -v                    -> 60 passed (39 unit, 21 integration [live DB], 2 health)
backend: ruff check .                 -> All checks passed!
backend: black --check .              -> 40 files would be left unchanged.
backend: mypy .                       -> Success: no issues found in 38 source files

frontend: npm run lint                -> clean
frontend: npm run format:check        -> All matched files use Prettier code style!
frontend: npm run typecheck           -> clean (tsc -b)
frontend: npm run build               -> succeeded (dist/assets bundle 428.68 kB / gzip 136.05 kB)
frontend: npm audit                   -> found 0 vulnerabilities

pre-commit run --all-files            -> all hooks passed (backend-pytest now scoped to unit tests)

alembic upgrade head (live)           -> upgraded 0001 -> 0002
alembic downgrade 0001 (live)         -> downgraded 0002 -> 0001, nexus schema back to just alembic_version
alembic upgrade head (live, again)    -> upgraded 0001 -> 0002, clean re-apply
GET /health (live DB config)          -> 200 {"status": "healthy", ...}
```

**Commands Executed** (representative)

```
cd backend
./.venv/Scripts/python -m alembic revision --autogenerate -m "..."
# hand-review + correction of the circular-FK handling, see Problems Encountered

./.venv/Scripts/python -m alembic upgrade head
./.venv/Scripts/python -m alembic downgrade 0001
./.venv/Scripts/python -m alembic upgrade head

./.venv/Scripts/python -m pytest -v
./.venv/Scripts/python -m ruff check . / black --check . / mypy .

cd ../web
npm run lint / format:check / typecheck / build / audit

cd ..
backend/.venv/Scripts/python -m pre_commit run --all-files
```

**Deployment Validation**

Not exercised — Railway/Vercel deployment remains Milestone 15 scope.

**Problems Encountered**

1. **Circular FK silently dropped by autogenerate** — see Features Completed
   and ADR-014 point 4. Root-caused by compiling `CreateTable(...)` directly
   (`str(CreateTable(RawProviderPayload.__table__).compile(dialect=postgresql.dialect()))`)
   and observing the `use_alter=True` constraint simply isn't in the emitted
   SQL, before touching the live database with a migration that would have
   quietly omitted a constraint.
2. **Alembic version-table/nexus-schema bootstrap ordering** (carried over from
   the prior entry's `env.py` fix) did not resurface here since it was already
   fixed, but is what made this migration's `alembic upgrade head` from a clean
   `0001` state work on the first attempt.
3. **`create_calculation`'s original API design was awkward**: the first draft
   required callers to pass `CalculationInput` rows with a placeholder
   `calculation_id` (since the real one doesn't exist until the calculation row
   is inserted), to be silently overwritten. Caught during test-writing, before
   any test relied on the awkward shape — fixed by splitting `CalculationInput`
   into `CalculationInputCreate` (no `calculation_id`, what callers actually
   have) and `CalculationInput` (the persisted row, with `calculation_id`,
   returned by `list_calculation_inputs`).
4. **mypy caught a real gap in initial repository code**: the first draft of
   each repository's `_to_domain` mapper passed ORM `str` columns straight into
   Pydantic fields typed as `StrEnum` subclasses without conversion. mypy
   flagged all seven occurrences (`error: Argument "provider" ... incompatible
   type "str"; expected "ProviderName"`, etc.) before any test ran — fixed by
   explicitly constructing the enum (`ProviderName(row.provider)`) at every
   read boundary.

**Solutions**

Every problem above was caught by directly verifying behavior (compiling DDL,
running mypy, writing the integration test that exercises the exact shape
`create_calculation` callers need) rather than assuming autogenerate, review,
or type hints alone were sufficient — consistent with this project's pattern of
proving claims against the real database rather than the migration/tool output.

**Remaining Work**

- TD-005 (new): `data_entitlement.derived_data_permission` is modeled but not
  yet used by `policy_check` — deferred until a real licensed provider exists
  to test the calculation-lineage-walk logic against (Milestone 14+).
- Everything in Milestone 3 onward per `PLAN.md` § Milestone Status —
  unstarted; Milestone 3 requires separate approval to begin.

**Git Commit Hash**

`27af3c1bcaa1e453c37bc4cb76f48020b8c8a938` (`27af3c1`)

**GitHub Remote and Push Results**

- `git push origin main` — succeeded: `bd02e15..27af3c1  main -> main`.
- Post-push verification: `git ls-remote origin` returns
  `27af3c1bcaa1e453c37bc4cb76f48020b8c8a938` for both `HEAD` and
  `refs/heads/main`, matching the local commit exactly.
- Remote branch: https://github.com/kirantoday/nexus-credit-intelligence/tree/main

**Approximate Time Spent**

Single focused implementation session, following directly after Supabase
schema-isolation validation and Milestone 1/1-hardening approval.

**Developer Notes**

The two mypy catches and the autogenerate/circular-FK catch are the load-bearing
example for this milestone: every one of them would have been a silent, or
much-later-discovered, correctness bug in a domain-layer/migration workflow
that otherwise "ran successfully." Treat a clean `mypy`/`alembic upgrade`/
`pytest` run as a floor, not a ceiling — this milestone's actual bugs were all
found by going one level deeper (compiling DDL, reading the type error instead
of suppressing it, writing the integration test that uses the API the way a
real caller would) than the tool's surface-level "success."

---

## 2026-08-06 — Milestone 3: SEC adapter vertical slice (issuer, financial_fact)

**Summary**

The first real provider adapter and the first two canonical business-entity
tables: one real issuer, one real SEC filing, one real XBRL financial fact,
proven end-to-end through the full canonical pipeline (Provider -> DTO ->
Normalizer -> Canonical Domain Object -> Repository -> Postgres, PLAN.md §18
step 3) against the actual live SEC EDGAR API and the actual live, shared
Supabase project — not mocked, not fabricated. A real issuer (Apple Inc., CIK
0000320193) and one real financial fact are permanently committed in `nexus`
as tangible evidence, in addition to 91 passing tests. No API routes, provider
adapters beyond SEC EDGAR, or UI were touched — vertical slice through the
domain layer only, per milestone scope.

**Features Completed**

- `backend/app/core/types.py`: added `FormType` (`10-K`/`10-Q`/`8-K`/`6-K`/
  `20-F`, PLAN.md §4.5's `financial_fact.form_type`).
- `backend/app/domain/issuer.py`, `financial_fact.py`: frozen Pydantic
  canonical objects (`IssuerCreate`/`Issuer`, `FinancialFactCreate`/
  `FinancialFact`), provider-neutral — no SEC-specific fields.
- `backend/app/models/issuer.py`, `financial_fact.py`: SQLAlchemy ORM,
  schema-qualified to `nexus`. `issuer.cik` has a unique index (nullable-safe:
  any number of `NULL` ciks allowed, but a real CIK can only belong to one
  issuer). `financial_fact` has a unique dedup index on
  `(issuer_id, concept, accession_no, fiscal_year, fiscal_period)` so
  re-ingesting the same filing's same datapoint can never duplicate a row.
- `backend/app/repositories/issuer_repository.py`,
  `financial_fact_repository.py`: function-style, matching the Milestone 2
  convention. `get_issuer_by_cik` and `get_by_dedup_key` are the idempotent
  re-ingestion checks the provider orchestrator uses.
- `backend/app/providers/base/http_client.py`: `ThrottledHttpClient` — a
  synchronous `httpx`-based GET client with a minimum inter-request delay and
  a required, descriptive `User-Agent` (SEC EDGAR's fair-access policy blocks
  generic/browser-like User-Agents and enforces a rate limit; this project's
  is `Nexus Credit Intelligence kiran.dbat@gmail.com`, configured via the
  existing `SEC_USER_AGENT` setting). Returns raw bytes, not parsed JSON —
  different responses need different JSON-parsing options (see below).
- `backend/app/providers/base/raw_payload_store.py`: computes the request
  fingerprint and content checksum and calls `raw_provider_payload_repository`
  — the only persistence-adjacent thing a provider adapter does, still never
  opening a session itself.
- `backend/app/providers/sec_edgar/dto.py`: `SecSubmissionsDTO`,
  `SecCompanyFactsDTO`, `SecXbrlUnitDatapoint` — verified against live
  `data.sec.gov` responses for CIK 0000320193 (Apple Inc.), not guessed at.
  `SecXbrlUnitDatapoint.val` is typed `Decimal`; `client.py` parses company-
  facts JSON with `parse_float=Decimal` so financial values never pass through
  a binary `float` at all (avoids precision loss before Pydantic even sees
  them).
- `backend/app/providers/sec_edgar/client.py`: `SecEdgarClient` fetching
  `submissions` and `companyfacts`; `format_cik10` (int or unpadded/padded
  string -> SEC's canonical zero-padded 10-digit form).
- `backend/app/providers/sec_edgar/normalizer.py`: the only place SEC-specific
  shapes (CIKs, XBRL concept tags, SIC codes, accession numbers) become
  PLAN.md's provider-neutral canonical schema. `sicDescription` is
  deliberately *not* mapped to `issuer.sector` — SIC and a GICS-style sector
  are different taxonomies, and conflating them would make `sector`'s meaning
  provider-dependent (a future Bloomberg/S&P Global adapter should be able to
  populate true sector data into that same column without SEC's SIC text
  fighting it).
- `backend/app/providers/sec_edgar/provider.py`:
  `ingest_issuer_and_one_financial_fact` — the orchestrator. Idempotent on the
  canonical `issuer`/`financial_fact` rows (re-running with the same
  `cik`/`concept` reuses them); every call still fetches fresh and logs a new
  `raw_provider_payload` + `provenance` row per fetch, since each retrieval is
  its own audit event even when it confirms unchanged data.
  `_select_most_recent_datapoint` picks the datapoint with the latest `end`
  date among those with complete fiscal metadata (see Problems Encountered).
- `backend/app/models/__init__.py`: now imports every model module (was
  empty) — see Problems Encountered for why this is a correctness fix, not
  cosmetic.
- `backend/alembic/env.py`: `run_migrations_online` no longer sets
  `search_path` on the migration connection — see Problems Encountered.
- `backend/pyproject.toml`: `httpx` moved from the `dev` extra to main
  `dependencies` (providers now make real runtime HTTP calls, not just tests).

**Files Created**

`backend/app/domain/issuer.py`, `financial_fact.py`,
`backend/app/models/issuer.py`, `financial_fact.py`,
`backend/app/repositories/issuer_repository.py`,
`financial_fact_repository.py`,
`backend/app/providers/__init__.py`,
`backend/app/providers/base/{__init__,http_client,raw_payload_store}.py`,
`backend/app/providers/sec_edgar/{__init__,dto,client,normalizer,provider}.py`,
`backend/alembic/versions/0003_issuer_financial_fact.py`,
`backend/tests/fixtures/sec_edgar/{submissions_aapl_trimmed,companyfacts_aapl_trimmed}.json`,
`backend/tests/unit/test_sec_edgar_normalizer.py`,
`backend/tests/integration/test_issuer_repository.py`,
`test_financial_fact_repository.py`, `test_sec_edgar_live_ingestion.py`.

**Files Modified**

`backend/app/core/types.py` (`FormType`), `backend/app/models/__init__.py`
(now imports every model), `backend/alembic/env.py` (search_path removed from
migration connection; model imports simplified),
`backend/tests/integration/conftest.py` (`sec_http_client` fixture),
`backend/pyproject.toml` (`httpx` -> main deps), `PLAN.md`,
`backend/.env` (local, git-ignored: `SEC_USER_AGENT` added).

**Database Changes**

Migration `0003` applied to the live, shared Supabase project: creates
`nexus.issuer` (+ unique `cik` index) and `nexus.financial_fact` (+ dedup
unique index, issuer_id index, provenance_id index, `form_type` CHECK
constraint). No circular FK this time (unlike migration 0002) — straightforward
dependency order. Verified with a full round-trip:
`upgrade head` → `downgrade 0002` → `upgrade head`, plus a follow-up
autogenerate run against the fully-migrated state that detected **zero**
further diffs, confirming the models and live schema match exactly.

Separately, a genuine (non-test, committed) ingestion was run against the live
database: `nexus.issuer` now permanently contains one real row (Apple Inc.,
CIK 0000320193, ticker AAPL, SIC 3571) and `nexus.financial_fact` one real row
(`RevenueFromContractWithCustomerExcludingAssessedTax`, $364,357,000,000, from
a real 10-Q, accession `0000320193-26-000020`), both backed by real
`provenance` and `raw_provider_payload` rows fetched live from
`data.sec.gov`. This is Milestone 3's primary objective made tangible, not
just asserted by a test that immediately rolls back.

**API Endpoints Added**

None (out of scope — vertical slice through the domain layer only).

**Frontend Pages Added**

None (out of scope; unaffected, re-verified green).

**Environment Variables Added**

`SEC_USER_AGENT` was already in `.env.example`/`config.py` since Milestone 1
but unset; now configured locally (`backend/.env`, git-ignored) as
`Nexus Credit Intelligence kiran.dbat@gmail.com` per explicit approval, since
SEC EDGAR requires a real, reachable identifier on every request.

**Tests Added**

91 total (up from 60): 54 unit (15 new SEC EDGAR DTO/normalizer tests against
real, trimmed fixtures captured from live `data.sec.gov` responses — including
a genuine real-world edge case, datapoints with null `fiscal_year`/
`fiscal_period` on pre-2011-ish filings — plus the existing 39) + 37
integration (13 new: 6 `issuer_repository`, 7 `financial_fact_repository`,
plus 3 that make genuinely live SEC EDGAR *and* Supabase calls in
`test_sec_edgar_live_ingestion.py`, on top of the existing 19 from Milestone 2
minus adjustments — see Problems Encountered) + 2 health.

**Test Results**

```
backend: pytest -v                    -> 91 passed (54 unit, 37 integration [3 genuinely live], 2 health)
backend: ruff check .                 -> All checks passed!
backend: black --check .              -> 60 files would be left unchanged.
backend: mypy .                       -> Success: no issues found in 57 source files

frontend: npm run lint                -> clean
frontend: npm run format:check        -> All matched files use Prettier code style!
frontend: npm run typecheck           -> clean (tsc -b)
frontend: npm run build               -> succeeded (dist/assets bundle 428.68 kB / gzip 136.05 kB)
frontend: npm audit                   -> found 0 vulnerabilities

pre-commit run --all-files            -> all hooks passed (unit tests only, fast)

alembic upgrade head (live)           -> upgraded 0002 -> 0003
alembic downgrade 0002 (live)         -> downgraded 0003 -> 0002, issuer/financial_fact removed cleanly
alembic upgrade head (live, again)    -> upgraded 0002 -> 0003, clean re-apply
alembic revision --autogenerate       -> zero diffs detected against fully-migrated live state
GET /health (live DB config)          -> 200 {"status": "healthy", ...}
```

**Commands Executed** (representative)

```
# real API shape verification before writing DTOs (not guessed at)
curl -H "User-Agent: ..." https://data.sec.gov/submissions/CIK0000320193.json
curl -H "User-Agent: ..." https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json

cd backend
./.venv/Scripts/python -m alembic revision --autogenerate -m "issuer and financial_fact"
# discovered + fixed the search_path/autogenerate bug here, see Problems Encountered
./.venv/Scripts/python -m alembic upgrade head
./.venv/Scripts/python -m alembic downgrade 0002
./.venv/Scripts/python -m alembic upgrade head
./.venv/Scripts/python -m alembic revision --autogenerate -m "drift check"  # confirmed empty, deleted

./.venv/Scripts/python -m pytest -v
./.venv/Scripts/python -m ruff check . / black --check . / mypy .

# genuine, committed (non-test) live ingestion — see Database Changes
./.venv/Scripts/python -c "... SessionLocal + ThrottledHttpClient + ingest_issuer_and_one_financial_fact + db.commit() ..."

cd ../web
npm run lint / format:check / typecheck / build / audit

cd ..
backend/.venv/Scripts/python -m pre_commit run --all-files
```

**Deployment Validation**

Not exercised — Railway/Vercel deployment remains Milestone 15 scope.

**Problems Encountered**

1. **A real Alembic autogenerate bug, found before it could do damage.**
   Generating migration `0003` against a database that already had
   Milestone 2's tables live, autogenerate proposed recreating *all five* of
   them alongside the two genuinely new ones. Root cause: `run_migrations_online`
   set `search_path=nexus,public` on the migration connection (defense-in-depth,
   carried over from Milestone 2), which made `nexus` that connection's
   *default* schema (confirmed via `inspector.default_schema_name == 'nexus'`).
   Alembic's reflection represents the default schema internally as
   `schema=None`, which `include_name`'s `name == NEXUS_SCHEMA` check then
   excluded (`None != 'nexus'`) — so autogenerate's "already exists" check
   silently found nothing on the reflected side for every pre-existing table,
   while the metadata side (explicit `schema='nexus'`) passed fine, producing
   a false "table is new" diff for all five. Fixed by removing the
   `search_path` connect_arg from the migration engine entirely: every
   migration operation is already schema-qualified explicitly
   (`schema="nexus"` on every `op.*` call), so it was pure defense-in-depth
   with no correctness need, and it was actively wrong here. Verified the fix
   by re-running autogenerate (only the 2 real new tables detected) and, after
   applying, running autogenerate again against the fully-migrated state
   (zero diffs).
2. **A real, latent `NoReferencedTableError` risk, not just a test artifact.**
   Running only the new repository test files in isolation failed with
   `NoReferencedTableError: ... could not find table 'nexus.raw_provider_payload'`.
   Cause: SQLAlchemy models only register into `Base.metadata` when their
   module is actually imported, and foreign keys are resolved lazily by
   string; `app/models/__init__.py` was empty, so nothing guaranteed every
   model module got imported before a mapper configuration triggered FK
   resolution. This wasn't only a test-collection-order artifact — the exact
   same failure was reachable from any production code path that touched one
   model without every other model having been imported first (e.g. a route
   using only `financial_fact_repository` without `provenance`'s module ever
   having loaded). Fixed at the source: `app/models/__init__.py` now imports
   every model module, so any `from app.models.x import Y` transitively
   imports all of them first, regardless of call order.
3. **SEC XBRL data itself: real datapoints with null `fy`/`fp`.** Parsing the
   full live company-facts response for validation failed with over a
   thousand Pydantic errors — older (roughly pre-2011) datapoints genuinely
   omit `fy`/`fp` tagging. Not an edge case to special-case away: `dto.py`'s
   `SecXbrlUnitDatapoint` types both as `int | None`/`str | None` (the real
   shape), and `_select_most_recent_datapoint` explicitly filters to
   datapoints with both present before selecting, with `normalizer.py`
   independently re-checking the same invariant as defense-in-depth.
4. **Test fixtures collided with the genuine live data left in the database.**
   After committing the real Apple issuer/financial_fact as tangible Milestone
   3 evidence, `tests/integration/test_issuer_repository.py`'s default test
   fixture (which reused CIK `0000320193`) and
   `test_sec_edgar_live_ingestion.py`'s hard `issuer_created is True`
   assertion both broke on the next full test run — correctly, since the
   application code (uniqueness constraint, idempotency logic) was doing
   exactly what it should. Fixed by moving all test-owned CIKs in
   `test_issuer_repository.py` to an unambiguously-fake `9999900xxx` range
   (real SEC CIKs are currently well under 2,000,000) and by relaxing the live
   ingestion tests to assert data correctness and internal (first-call vs.
   second-call) idempotency rather than a fixed created/found boolean, since
   that boolean legitimately depends on prior runs and on SEC's own filing
   cadence, not on anything this test controls.

**Solutions**

All four were caught by direct verification rather than assumption: compiling
Alembic's actual reflected state and comparing schema names, running the full
test suite (not just new files) to surface the import-order dependency, fully
parsing real (not sampled) live data before writing the DTO, and running the
full suite again after leaving genuine data committed to see what broke.

**Remaining Work**

- TD-006 (new): SEC company-facts payloads (several MB for a large filer) are
  stored inline as `payload_json` pending Supabase Storage configuration —
  deferred to whichever milestone first genuinely needs Storage.
- Everything in Milestone 4 onward per `PLAN.md` § Milestone Status —
  unstarted; Milestone 4 requires separate approval to begin.

**Git Commit Hash**

`36bfaff946145efcbdf8573fb66b04bb12be1e12` (`36bfaff`)

**GitHub Remote and Push Results**

- `git push origin main` — succeeded: `cd53fec..36bfaff  main -> main`.
- Post-push verification: `git ls-remote origin` returns
  `36bfaff946145efcbdf8573fb66b04bb12be1e12` for both `HEAD` and
  `refs/heads/main`, matching the local commit exactly.
- Remote branch: https://github.com/kirantoday/nexus-credit-intelligence/tree/main

**Approximate Time Spent**

Single focused implementation session, following directly after Milestone 2
approval.

**Developer Notes**

Milestone 2's ADR-014 domain-layer conventions (Pydantic domain objects,
function-style repositories, text+CHECK enums) held up cleanly for the first
real canonical entities built on top of them — no changes needed to that
pattern itself. The provider-layer conventions established here
(`http_client`/`raw_payload_store` in `providers/base/`, and the
DTO/normalizer/provider module shape in `providers/sec_edgar/`) are now the
template for every future provider adapter (OpenFIGI, FRED, CourtListener,
TRACE, and eventually the disabled licensed-vendor stubs); none of them needed
their own architectural decision beyond what PLAN.md §3/§17 already specified,
which is why this entry has no accompanying ADR.

---

## 2026-08-06 — Milestone 4: Credit Universe initial page

**Summary**

The first usable Credit Universe screen is live end-to-end against the real,
shared Supabase project and is now the post-login landing page, replacing the
placeholder `HomePage`. `security` (PLAN.md §4.5) gets its first migration.
Two real data sources coexist and are clearly distinguished in both the data
model and the UI: one real SEC EDGAR-sourced bond (Apple Inc., an honest
aggregate figure — not a fabricated per-instrument one) and ten synthetic
leveraged-loan positions across 8 fictional issuers. Every displayed value
carries a provenance badge; freshness is computed at read time, never stored.
The UI is powered entirely by the canonical domain model — no provider-specific
logic appears anywhere in the frontend. Two real, previously-undetected bugs
were found through actual manual use (not just passing tests) and fixed at the
root: a search-box keystroke-loss race, and a Supabase pgbouncer/psycopg3
prepared-statement incompatibility that intermittently broke both the test
suite and the live server.

**Features Completed**

- `core/freshness.py`: `FreshnessTier` (`live`/`cached`/`stale`) computed from
  `retrieved_at` + a per-`ProviderName` TTL policy at read time (PLAN.md §16) —
  never persisted, so it can't silently drift from the truth.
- `security` domain object + ORM model (PLAN.md §4.5), with CHECK constraints
  (not native Postgres ENUM, per ADR-014) on `instrument_type`/`seniority`,
  partial unique indexes on `cusip`/`isin`, and a
  synthetic-reason-requires-`is_synthetic` constraint mirroring the one
  already on `issuer`.
- `is_synthetic`/`synthetic_reason` added to `issuer` so the real/synthetic
  boundary is a first-class, queryable property of every issuer, not just
  every security.
- `security_repository.list_credit_universe`: joins `security` + `issuer` +
  `provenance` in a single query (no N+1) with filter (instrument type,
  synthetic flag, free-text search), sort (`nulls_last()` in both directions),
  and pagination — built to scale to thousands of rows per PLAN.md's UX
  requirement, even though the seed dataset is 11 rows.
- `leveraged_loan_generator`: idempotent synthetic-data seeder for 8 fictional
  issuers / 10 loan positions, each tagged `SYNTHETIC_DEMO_DATA` per ADR-008.
- SEC EDGAR provider extended with `ingest_aggregate_bond`: pulls a real
  aggregate debt concept (e.g. `LongTermDebtNoncurrent`) from an issuer's
  XBRL company-facts and normalizes it into a `security` row. Verified against
  live Apple company-facts data before writing the normalizer that the simple
  companyfacts API genuinely has no per-instrument/CUSIP-level data — the
  aggregate-only representation is a real API limitation, not a shortcut
  (TD-008).
- `credit_universe_service` + `GET /api/credit-universe`: thin route, service
  layer applies `policy_check` per row (currently a no-op gate — nothing
  licensed exists yet) and computes freshness per row before response
  assembly.
- Frontend: `DataTable` (generic TanStack Table v8 wrapper — deliberately v8,
  not the newly-released v9, after inspecting both packages' actual exports
  and choosing the API with a stable, well-documented surface), `ProvenanceBadge`,
  `SyntheticDataBadge`, and `CreditUniversePage` — a 9-column sortable/
  filterable/paginated grid, now mounted at `/` as the landing page. Filters
  (instrument type, real/synthetic toggle, pagination, sort) are persisted in
  the URL via `useSearchParams`; loading, empty, and error states are all
  implemented, not just the happy path.
- Vitest + React Testing Library set up for the frontend for the first time
  this milestone (`vite.config.ts` test block, `src/test/setup.ts` with
  explicit RTL cleanup wiring since `globals: false` is kept deliberately).

**Files Created**

`backend/app/core/freshness.py`, `backend/app/domain/security.py`,
`backend/app/models/security.py`, `backend/app/repositories/security_repository.py`,
`backend/app/synthetic/__init__.py`, `backend/app/synthetic/leveraged_loan_generator.py`,
`backend/app/schemas/__init__.py`, `backend/app/schemas/credit_universe.py`,
`backend/app/services/__init__.py`, `backend/app/services/credit_universe_service.py`,
`backend/app/api/routes/credit_universe.py`,
`backend/alembic/versions/0004_security_and_issuer_synthetic_flag.py`,
`backend/tests/unit/test_freshness.py`,
`backend/tests/unit/test_issuer_security_validators.py`,
`backend/tests/integration/test_security_repository.py`,
`backend/tests/integration/test_leveraged_loan_generator.py`,
`backend/tests/integration/test_credit_universe_service.py`,
`web/src/api/creditUniverse.ts`, `web/src/queries/useCreditUniverse.ts`,
`web/src/lib/format.ts`, `web/src/lib/format.test.ts`,
`web/src/lib/useDebouncedValue.ts`, `web/src/components/DataTable.tsx`,
`web/src/components/DataTable.test.tsx`, `web/src/components/SyntheticDataBadge.tsx`,
`web/src/components/SyntheticDataBadge.test.tsx`, `web/src/components/ProvenanceBadge.tsx`,
`web/src/pages/CreditUniversePage.tsx`, `web/src/pages/CreditUniversePage.test.tsx`,
`web/src/test/setup.ts`.

**Files Modified**

`backend/app/core/types.py` (`InstrumentType`, `Seniority`),
`backend/app/domain/issuer.py` (`is_synthetic`/`synthetic_reason`),
`backend/app/models/issuer.py` (matching columns + CHECK constraint),
`backend/app/models/__init__.py` (imports `security`),
`backend/app/repositories/issuer_repository.py` (`get_issuer_by_legal_name`,
updated `_to_domain`/`create_issuer`),
`backend/app/providers/sec_edgar/normalizer.py` (`normalize_bond_provenance`,
`normalize_bond_security`),
`backend/app/providers/sec_edgar/provider.py` (`ingest_aggregate_bond`;
extracted `_fetch_and_store_company_facts`/`_extract_datapoint` helpers),
`backend/app/db/session.py` (disabled psycopg3 server-side prepare — see
Problems Encountered), `backend/app/main.py` (mounts `credit_universe_router`),
`backend/tests/integration/test_sec_edgar_live_ingestion.py` (added live
aggregate-bond ingestion tests), `web/package.json`/`package-lock.json`
(`@tanstack/react-table`, Vitest/RTL dev deps), `web/vite.config.ts` (test
block), `web/tsconfig.app.json` (`@testing-library/jest-dom` types),
`web/src/App.tsx` (`/` now renders `CreditUniversePage`),
`web/src/components/Layout.tsx` (nav updated).

Deleted: `web/src/pages/HomePage.tsx`, `web/src/queries/useHealth.ts`
(only consumer was `HomePage`).

**Database Changes**

Migration `0004` applied to the live, shared Supabase project: creates
`nexus.security` (CHECK constraints on `instrument_type`/`seniority`, partial
unique indexes on `cusip`/`isin`, indexes on `issuer_id`/`provenance_id`/
`instrument_type`) and adds `is_synthetic`/`synthetic_reason` (+ CHECK) to
`nexus.issuer`. Verified with a full round-trip: `upgrade head` →
`downgrade 0003` → `upgrade head`, plus a follow-up autogenerate check against
the fully-migrated state that detected zero further diffs.

Separately, a genuine (non-test, committed) seed was run against the live
database: `nexus.security` now permanently contains one real row (Apple Inc.
aggregate long-term debt, $71.34B, sourced from live XBRL company-facts) and
ten synthetic leveraged-loan rows across 8 fictional issuers, all backed by
real `provenance` rows (`provider = sec_edgar` / `provider = synthetic`
respectively) — this is Milestone 4's primary objective made tangible, not
just asserted by a test that immediately rolls back.

**API Endpoints Added**

`GET /api/credit-universe` — query params: `instrument_type`, `is_synthetic`,
`search`, `sort_by`, `sort_dir`, `page`, `page_size`. Returns
`{ rows: CreditUniverseRow[], total, page, page_size }`.

**Frontend Pages Added**

`CreditUniversePage` at `/` (replaces the placeholder `HomePage` as the
landing page).

**Environment Variables Added**

None.

**Tests Added**

43 new backend tests (91 → 134): `test_freshness.py` (freshness-tier
boundaries per provider policy), `test_issuer_security_validators.py`
(synthetic-reason-requires-flag validators), `test_security_repository.py`
(13 — CRUD, CHECK-constraint violations, cusip uniqueness, filter/sort/
pagination), `test_leveraged_loan_generator.py` (4 — data correctness and
intra-run idempotency, not a fixed created/found boolean, per the pattern
established in Milestone 3), `test_credit_universe_service.py` (3), plus 2
new live SEC EDGAR integration tests
(`test_live_ingest_aggregate_bond`/`..._is_idempotent`).

26 new frontend tests (0 → 26, first frontend tests this project has had):
`format.test.ts` (16), `SyntheticDataBadge.test.tsx` (2), `DataTable.test.tsx`
(5), `CreditUniversePage.test.tsx` (3).

**Test Results**

```
backend: pytest -v (x3 consecutive runs)  -> 134 passed each time (0 flaky, see Problems Encountered #2)
backend: ruff check .                     -> All checks passed!
backend: black --check .                  -> 77 files would be left unchanged.
backend: mypy .                           -> Success: no issues found in 73 source files
backend: alembic current                  -> 0004 (head)
backend: alembic check                    -> No new upgrade operations detected.

frontend: npm run test                    -> 26 passed (4 test files)
frontend: npm run lint                    -> clean
frontend: npm run typecheck               -> clean (tsc -b)
frontend: npm run build                   -> succeeded (dist/assets bundle 592.75 kB / gzip 181.78 kB;
                                              chunk-size warning only, no split performed — out of
                                              milestone scope)

pre-commit run --all-files                -> all hooks passed

GET /health (live server)                 -> 200 {"status": "healthy", ...}
GET /api/credit-universe (live server)    -> 200, correct rows/provenance/freshness
```

**Commands Executed** (representative)

```
cd backend
./.venv/Scripts/python -m alembic revision --autogenerate -m "security table and issuer synthetic flag"
./.venv/Scripts/python -m alembic upgrade head
./.venv/Scripts/python -m alembic downgrade 0003
./.venv/Scripts/python -m alembic upgrade head
./.venv/Scripts/python -m alembic revision --autogenerate -m "drift check"  # confirmed empty, deleted

# genuine, committed (non-test) live seed — see Database Changes
./.venv/Scripts/python -c "... seed_synthetic_loans(db) + ingest_aggregate_bond(db, http_client, cik=...) + db.commit() ..."

./.venv/Scripts/python -m pytest -q   # run 3x consecutively to confirm the pooler fix eliminated flakiness
./.venv/Scripts/python -m ruff check . / black --check . / mypy .

cd ../web
npm install @tanstack/react-table@^8 vitest @testing-library/react @testing-library/jest-dom @testing-library/user-event jsdom
npm run test / lint / typecheck / build

cd ..
backend/.venv/Scripts/python -m pre_commit run --all-files

# manual browser verification (Chrome, via claude-in-chrome tools)
# search box, instrument-type filter, real/synthetic toggle, empty state,
# column sort, console-error check — see Problems Encountered #1 and #2
```

**Deployment Validation**

Not exercised — Railway/Vercel deployment remains Milestone 15 scope. Both
the backend (`uvicorn`, port 8010) and frontend (`vite dev`, port 5173) dev
servers were run locally throughout this milestone and confirmed booting and
serving real, live-Supabase-backed data.

**Problems Encountered**

1. **A real search-box keystroke-loss bug, found only by actually typing into
   the field.** `CreditUniversePage`'s search `TextField` was originally
   `value={searchParams.get("q")}` with `onChange` calling `setSearchParams`
   directly on every keystroke — driven straight from URL state, matching
   every other filter on the page. Typing "Apple" resulted in only "e"
   appearing. Root cause: each keystroke's `setSearchParams` call triggers a
   React re-render with a new controlled `value` before the DOM/React can
   process the next keystroke, so every character effectively resets the
   field to whatever the URL update landed on. This is a genuine race
   (react-router's URL/history update is not a free, synchronous operation),
   not a browser-automation artifact — it would affect a real user typing at
   normal speed. Fixed with a new `useDebouncedValue` hook: the `TextField`
   now binds to local `useState` (`searchInput`), always instantly
   responsive to the DOM; a 300ms-debounced derivative (`debouncedSearch`)
   drives both the API query and, via a `useEffect`, the URL param — so
   typing never loses characters and doesn't fire a network request or a
   history entry per keystroke either. Directly caught by following CLAUDE.md's
   "start the dev server and use the feature in a browser before reporting
   the task as complete" instruction — automated tests alone (which mock the
   API and don't simulate real per-keystroke DOM timing) would not have
   caught this.
2. **A real, live-reproduced Supabase pgbouncer/psycopg3 incompatibility.**
   Discovered two ways: first as 3 flaky test failures
   (`DuplicatePreparedStatement`) on a full `pytest -q` run that passed
   cleanly when the same tests were re-run in isolation; second, more
   seriously, as a genuine `500 Internal Server Error`
   (`InvalidSqlStatementName: prepared statement "_pg3_0" does not exist`) on
   the actual running dev server when curl'd directly, on the exact query
   `security_repository.list_credit_universe` uses for its total count.
   Root cause: `DATABASE_URL` points at Supabase's pooled connection string,
   which runs pgbouncer in transaction-pooling mode — each query can be
   handed to a *different* physical Postgres backend connection. psycopg3
   caches server-side `PREPARE`d statements per logical connection by
   default; under transaction pooling that cache goes stale, since a later
   query on the same logical connection object can land on a physical
   backend that never saw the original `PREPARE`, or one where a leftover
   prepared-statement name collides with a different client's. This is a
   well-documented category of pgbouncer-transaction-mode incompatibility,
   not specific to this codebase's queries. Fixed in
   `backend/app/db/session.py` by adding `"prepare_threshold": None` to
   `connect_args`, which disables psycopg3's automatic server-side prepare
   entirely. Verified via 3 consecutive full `pytest -q` runs (134/134 each
   time, zero flakiness) and a live re-check of the actual running server
   after restarting it with the fix (`GET /api/credit-universe` → 200 with
   correct data). This is a connection-configuration fix, not an architecture
   change — the approved stack (Supabase-managed Postgres via SQLAlchemy) is
   unchanged; no ADR was written for it, matching CLAUDE.md's guidance that
   ordinary tooling/config fixes don't need one.
3. **TanStack Table v9 vs v8.** `npm install @tanstack/react-table` (no
   version pin) pulled v9.0.0, whose API (`useTable`, feature-flag
   composition) bears no resemblance to the well-documented v8 API this
   project's design assumed. Caught before writing any component code by
   inspecting `Object.keys(require('@tanstack/react-table'))` for both
   versions; resolved by installing `@tanstack/react-table@^8` explicitly
   (resolved to 8.21.3).
4. **RTL auto-cleanup didn't fire between tests.** A `DataTable.test.tsx`
   sort-click test failed with "multiple elements with text 'Name'" —
   root cause was `globals: false` in `vite.config.ts` (deliberate, for
   explicit imports), which prevents React Testing Library's automatic
   `afterEach(cleanup)` detection. Fixed by wiring `cleanup()` explicitly in
   `src/test/setup.ts`.

**Solutions**

All four were caught by direct verification, not assumption: actually typing
into the search box in a real browser (not just asserting on mocked API
responses), running the full test suite repeatedly and curling the live dev
server directly rather than trusting a single green run, inspecting the
actual installed package's exports before writing code against an assumed
API, and reading the specific duplicate-element failure message rather than
guessing at a cleanup fix.

**Remaining Work**

- TD-007 (new): `security` has a single `provenance_id` per row, not
  per-field provenance — deferred until a milestone (likely Milestone 5's
  OpenFIGI enrichment) actually needs to attribute individual fields to
  different providers.
- TD-008 (new): SEC EDGAR's XBRL company-facts API has no per-instrument bond
  data at all (a real external API limitation, not a shortcut) — real
  CUSIP/maturity/coupon data requires a different data source entirely.
- Frontend production bundle exceeds Vite's 500kB chunk-size warning
  threshold (592.75kB / gzip 181.78kB) — not addressed this milestone
  (premature optimization for an 11-row seed dataset); worth revisiting with
  route-based code-splitting once more pages exist.
- Everything in Milestone 5 onward per `PLAN.md` § Milestone Status —
  unstarted; Milestone 5 requires separate approval to begin.

**Git Commit Hash**

`34fd088af27db36b1aa5c2def30a0cdc68a83712` (`34fd088`) — implementation.
`00e2779a6e7674fd30be29a9012322a0b68741af` (`00e2779`) — follow-up docs commit
recording this hash.

**GitHub Remote and Push Results**

- `git push origin main` — succeeded: `24e5c95..00e2779  main -> main`.
- Post-push verification: `git ls-remote origin main` returns
  `00e2779a6e7674fd30be29a9012322a0b68741af`, matching the local commit
  exactly.
- Remote branch: https://github.com/kirantoday/nexus-credit-intelligence/tree/main

**Approximate Time Spent**

Single focused implementation session, following directly after Milestone 3
approval.

**Developer Notes**

The domain-layer and provider-layer conventions from Milestones 2 and 3 held
up without modification for `security`/the SEC bond-ingestion path. The
pgbouncer/psycopg3 finding (Problem #2) is worth remembering for every future
provider adapter and every future load-bearing query — it was silent under
light, isolated test runs and only surfaced under the kind of concurrent/
sequential connection churn a full test suite or a real multi-request server
session produces.

---

## 2026-08-06 — Milestone 5: OpenFIGI + FRED adapters

**Summary**

Approved with an explicit instruction: think like an investment analyst
first — integrate a provider only because it answers a real question, not
because it exists. OpenFIGI answers "what security is this?"; FRED answers
"what macroeconomic environment surrounds this credit?". Both adapters were
scoped and verified against real, live API behavior before any code was
written (same discipline as Milestones 3-4), and Credit Universe is
measurably more useful for it: five real, specific Apple bonds replace what
was previously one non-actionable aggregate figure, and every SOFR-linked
loan row now shows a live, real benchmark rate.

**Features Completed**

- OpenFIGI provider (`providers/openfigi/`): a live `POST /v3/search` for
  "APPLE INC" (`marketSecDes=Corp`), filtered to `exchCode=TRACE` (USD
  domestic corporate bonds — the same universe Milestone 11's TRACE adapter
  will eventually price), identifies real, specific bond issues. Verified
  live before design: the free API returns no CUSIP/ISIN at all (a genuine
  provider limitation, not a shortcut) but does return a real FIGI and a
  `ticker` field following a parseable `"COUPON MM/DD/YY"` convention (e.g.
  `"AAPL 3.85 05/04/43"`), regexed into real `maturity_date`/`coupon` —
  falling back to maturity-only parsing for floating-rate notes (ticker'd
  `"F"`, not a numeric coupon), and to `(None, None)` for anything
  unrecognized, never a guess.
- FRED provider (`providers/fred/`): syncs a series' metadata plus its most
  recent observations (default latest 10 — a deliberate first-slice scope,
  not a bulk historical loader, TD-009). FRED's real `"."`
  missing-observation marker (holidays, etc.) is filtered out before any
  `provenance` row is created for it — no row is created for a missing date,
  not a fabricated null one. `provenance.source_url` never carries the API
  key (a `public_url` built separately from the actual key-bearing request
  URL, per PLAN.md 4.1's "no API keys embedded" rule).
- `security.figi` unique index (Milestone 5 is the first to populate it);
  `fred_series_registry`/`fred_observation` tables (PLAN.md 4.5) —
  `category`/`discontinued`/`redistribution_allowed` are honestly
  documented as curator-assigned/sync-time defaults, not fields FRED's
  `/fred/series` response actually contains (verified live).
  `security_repository.get_security_by_figi` added for OpenFIGI idempotency,
  mirroring the existing `get_issuer_by_legal_name` pattern.
- Credit Universe gained a "Current Benchmark Rate" column: for a row whose
  `benchmark` matches a FRED series this platform syncs (currently just
  "SOFR"), the latest real FRED observation is shown as a plain reported
  fact — deliberately NOT blended with `spread` into a new "all-in rate"
  number, per the explicit instruction not to derive a new calculated macro
  score this milestone. A new `GET /api/market-context` endpoint +
  `MarketContextPanel` surface real SOFR + ICE BofA US High Yield OAS
  (`BAMLH0A0HYM2`) together, honestly `None` (rendered as "—") for a series
  that hasn't been synced rather than a placeholder value.
- `ThrottledHttpClient` extended with `post_json` (OpenFIGI's search API is
  POST-only) and optional `extra_headers` (for `X-OPENFIGI-APIKEY`);
  `raw_payload_store.fingerprint_request` extended to optionally hash a
  request body, since a POST API's URL alone doesn't distinguish two
  different queries against the same endpoint the way a GET URL does.
- `FRED_API_KEY` supplied directly by the user into `backend/.env`
  (git-ignored, never printed/logged/committed) and loaded through the
  existing `pydantic-settings` `Settings.fred_api_key` field, which was
  already scaffolded in Milestone 1's environment-variable contract.

**Files Created**

`backend/alembic/versions/0005_figi_unique_index_and_fred_tables.py`,
`backend/app/api/routes/market_context.py`, `backend/app/domain/fred.py`,
`backend/app/models/fred.py`, `backend/app/providers/fred/__init__.py`,
`backend/app/providers/fred/client.py`, `backend/app/providers/fred/dto.py`,
`backend/app/providers/fred/normalizer.py`,
`backend/app/providers/fred/provider.py`,
`backend/app/providers/openfigi/__init__.py`,
`backend/app/providers/openfigi/client.py`,
`backend/app/providers/openfigi/dto.py`,
`backend/app/providers/openfigi/normalizer.py`,
`backend/app/providers/openfigi/provider.py`,
`backend/app/repositories/fred_repository.py`,
`backend/app/schemas/market_context.py`,
`backend/app/services/market_context_service.py`,
`backend/tests/unit/test_openfigi_normalizer.py`,
`backend/tests/unit/test_fred_normalizer.py`,
`backend/tests/integration/test_fred_repository.py`,
`backend/tests/integration/test_openfigi_live_ingestion.py`,
`backend/tests/integration/test_fred_live_ingestion.py`,
`backend/tests/integration/test_market_context_service.py`,
`web/src/api/marketContext.ts`, `web/src/components/MarketContextPanel.tsx`,
`web/src/components/MarketContextPanel.test.tsx`,
`web/src/queries/useMarketContext.ts`.

**Files Modified**

`backend/app/core/freshness.py` (OpenFIGI freshness policy — reference data,
long-lived), `backend/app/domain/security.py` (TD-007 docstring updated to
explain why this milestone didn't force its resolution),
`backend/app/main.py` (mounts `market_context_router`),
`backend/app/models/__init__.py` (imports `fred`),
`backend/app/models/security.py` (`figi` unique index, docstring),
`backend/app/providers/base/http_client.py` (`post_json`, `extra_headers`),
`backend/app/providers/base/raw_payload_store.py` (body-aware fingerprint),
`backend/app/repositories/security_repository.py`
(`get_security_by_figi`), `backend/app/schemas/credit_universe.py`
(`benchmark_rate`/`benchmark_rate_as_of_date`/`benchmark_rate_provider`),
`backend/app/services/credit_universe_service.py` (benchmark-rate
attachment, one query per distinct benchmark on a page, not per row),
`backend/tests/integration/conftest.py` (pgbouncer fix on its own engine;
new `openfigi_http_client`/`fred_http_client`/`fred_api_key` fixtures),
`backend/tests/integration/test_credit_universe_service.py`
(benchmark-rate tests), `backend/tests/unit/test_freshness.py` (OpenFIGI
policy test; swapped the "unknown provider" example off OpenFIGI now that
it has a real policy), `web/src/api/creditUniverse.ts` (benchmark-rate
fields), `web/src/pages/CreditUniversePage.tsx` (benchmark-rate column,
`MarketContextPanel` mounted), `web/src/pages/CreditUniversePage.test.tsx`
(mocks `fetchMarketContext`), `web/vite.config.ts` (`testTimeout: 15000` —
see Problems Encountered).

**Database Changes**

Migration `0005` applied to the live, shared Supabase project: adds a
partial unique index on `security.figi` (`WHERE figi IS NOT NULL`,
mirroring `cusip`/`isin`); creates `nexus.fred_series_registry`
(`series_id` text primary key, per PLAN.md 4.5's column list, which lists no
separate surrogate id for this table) and `nexus.fred_observation`
(`(series_id, obs_date)` unique for idempotent re-sync). Verified with a
full round-trip: `upgrade head` → `downgrade 0004` → `upgrade head`, plus a
follow-up autogenerate check against the fully-migrated state that detected
zero further diffs.

Separately, a genuine (non-test, committed) live seed was run:
`nexus.security` now permanently contains five real Apple corporate bonds
(real FIGI, real maturity/coupon, e.g. `BBG004HST0K7` / "AAPL 3.85
05/04/43" / matures 2043-05-04 / 3.85%), each backed by a real `provenance`
row (`provider = openfigi`). `nexus.fred_series_registry` contains real
`SOFR` and `BAMLH0A0HYM2` registry rows; `nexus.fred_observation` contains
10 real observations for each series, each with its own `provenance` row
(`provider = fred`) and a shared `raw_provider_payload` row per API call.
Re-running the seed script twice consecutively confirmed full idempotency:
0 of 25 rows reported as newly created on the second run.

**API Endpoints Added**

`GET /api/market-context` — returns `{ sofr, high_yield_oas }`, each `null`
or a `{ series_id, title, value, units, as_of_date, freshness, provider }`
observation. `GET /api/credit-universe` unchanged in shape except three new
fields per row: `benchmark_rate`, `benchmark_rate_as_of_date`,
`benchmark_rate_provider`.

**Frontend Pages Added**

None new — `CreditUniversePage` gained a column and a panel component
(`MarketContextPanel`), not a new route.

**Environment Variables Added**

`FRED_API_KEY` (already scaffolded in `Settings`/`.env.example` since
Milestone 1; supplied by the user directly into `backend/.env`, git-ignored,
never printed/logged in this session or committed). `OPENFIGI_API_KEY`
remains optional and unset — OpenFIGI's unauthenticated tier is sufficient
for this milestone's scope, with the code already wired to use a key
automatically once one is configured (see Problems Encountered).

**Tests Added**

32 new backend tests (134 → 166): `test_openfigi_normalizer.py` (8 — ticker
parsing incl. floating-rate/unrecognized-shape cases, never-fabricate-
CUSIP/ISIN), `test_fred_normalizer.py` (6 — missing-observation filtering,
curator-assigned category not parsed from the API), `test_fred_repository.py`
(6), `test_openfigi_live_ingestion.py` (4, genuinely live),
`test_fred_live_ingestion.py` (3, genuinely live, incl. asserting the API key
never leaks into a persisted raw payload), `test_market_context_service.py`
(2, against genuinely live-synced data), plus 3 new
`test_credit_universe_service.py` tests (SOFR-benchmarked row gets a real
rate; unsynced-benchmark and no-benchmark rows correctly get none) and 1 new
`test_freshness.py` test (OpenFIGI's long-lived reference-data policy).

3 new frontend tests (26 → 29): `MarketContextPanel.test.tsx` (real
observations render; a `null` series renders "—", not a fabricated value;
API failure shows the unavailable message).

**Test Results**

```
backend: pytest -q (x2 consecutive full runs)  -> 166 passed each time
backend: pytest -q tests/integration/test_openfigi_live_ingestion.py (x2)  -> 4 passed each time
                                                    (after the throttle fix — see Problems Encountered)
backend: ruff check .                          -> All checks passed!
backend: black --check .                       -> 100 files would be left unchanged.
backend: mypy .                                -> Success: no issues found in 95 source files
backend: alembic current                       -> 0005 (head)
backend: alembic check                         -> No new upgrade operations detected.

frontend: npm run test (x2)                    -> 29 passed (5 test files) each time
frontend: npm run lint                         -> clean
frontend: npm run format:check                 -> All matched files use Prettier code style!
frontend: npm run typecheck                    -> clean (tsc -b)
frontend: npm run build                        -> succeeded (dist/assets bundle 597.43 kB / gzip 183.10 kB)

pre-commit run --all-files                     -> all hooks passed

GET /health (live server, port 8000)           -> 200 {"status": "healthy", ...}
GET /api/market-context (live server)          -> 200, real SOFR (3.64%) + HY OAS (2.73%)
GET /api/credit-universe (live server)         -> 200, real benchmark_rate on SOFR-linked rows
```

**Commands Executed** (representative)

```
# real API shape verification before writing DTOs (not guessed at)
curl -X POST https://api.openfigi.com/v3/search -d '{"query":"APPLE INC","marketSecDes":"Corp"}'
curl "https://api.stlouisfed.org/fred/series?series_id=SOFR&api_key=$FRED_API_KEY&file_type=json"
curl "https://api.stlouisfed.org/fred/series/observations?series_id=SOFR&api_key=$FRED_API_KEY&file_type=json&sort_order=desc&limit=5"

cd backend
./.venv/Scripts/python -m alembic revision --autogenerate -m "figi unique index and fred tables"
./.venv/Scripts/python -m alembic upgrade head
./.venv/Scripts/python -m alembic downgrade 0004
./.venv/Scripts/python -m alembic upgrade head
./.venv/Scripts/python -m alembic revision --autogenerate -m "drift check"  # confirmed empty, deleted

# genuine, committed (non-test) live seed — see Database Changes
./.venv/Scripts/python seed_milestone5.py   # OpenFIGI bonds + FRED SOFR/HY OAS sync + commit
./.venv/Scripts/python seed_milestone5.py   # re-run: confirmed 0/25 rows newly created

./.venv/Scripts/python -m pytest -q   # run 2x consecutively
./.venv/Scripts/python -m ruff check . / black --check . / mypy .

cd ../web
npm run test / lint / typecheck / build

cd ..
backend/.venv/Scripts/python -m pre_commit run --all-files

# manual browser verification (Chrome, via claude-in-chrome tools)
# real Apple bonds render with real maturity/coupon; Market Context panel
# shows live SOFR/HY OAS; SOFR-linked loan row shows a matching benchmark
# rate; console-error check — see Problems Encountered
```

**Deployment Validation**

Not exercised — Railway/Vercel deployment remains Milestone 15 scope. Both
the backend (`uvicorn`, port 8000 — the documented default, see Problems
Encountered) and frontend (`vite dev`, port 5173) dev servers were run
locally and confirmed booting and serving real, live-Supabase-backed data.

**Problems Encountered**

1. **A real pgbouncer/psycopg3 gap in the test suite's own engine.**
   `tests/integration/conftest.py`'s `db_engine` fixture builds its own
   SQLAlchemy engine, separate from `app/db/session.py` — Milestone 4's fix
   (`prepare_threshold=None`) only patched the latter. Since every
   integration test uses this fixture, the exact same intermittent
   `InvalidSqlStatementName`/`DuplicatePreparedStatement` vulnerability was
   still live in the test suite the whole time; it happened not to trigger
   in Milestone 4's specific runs. Found by re-reading the fixture while
   adding new ones for OpenFIGI/FRED, not by a fresh failure — fixed
   proactively with the identical `connect_args` change.
2. **A real live 429 from OpenFIGI's unauthenticated tier.** Running
   `test_openfigi_live_ingestion.py`'s four tests back-to-back (this module
   alone makes ~10 live search calls at the base `0.15s` throttle) triggered
   a genuine `HTTP/1.1 429 Too Many Requests` from `api.openfigi.com` on a
   full-suite run; the same module passed reliably run in isolation. Fixed
   by raising the `openfigi_http_client` fixture's throttle to 6s between
   requests and wiring `X-OPENFIGI-APIKEY` through automatically whenever
   `OPENFIGI_API_KEY` is configured (it isn't, in this environment — the
   unauthenticated tier is sufficient for this milestone's scope, but the
   code now self-heals once a key exists rather than requiring a second
   code change).
3. **A frontend test timing out under full-suite load, not a logic bug.**
   `CreditUniversePage.test.tsx`'s first test occasionally exceeded
   Vitest's default 5000ms timeout only when run alongside the other four
   test files (consistently ~5.8s in that configuration), while passing in
   1-2s every time in isolation — this sandbox showed anomalously high
   `import`/`environment` setup overhead (100s+) during this session
   specifically. Fixed by raising `testTimeout` to 15000ms globally in
   `vite.config.ts`, giving real headroom rather than chasing a phantom
   logic bug that isolated runs disproved.
4. **Manual browser verification initially hit the wrong backend port.**
   The frontend's `client.ts` defaults `VITE_API_BASE_URL` to
   `http://localhost:8000` (confirmed against `README.md`'s documented dev
   instructions), but this session's backend had been running on `8010`
   since Milestone 4 (an arbitrary port choice, never corrected). The
   browser's own network tab showed the real symptom directly: `OPTIONS`/
   `GET` to `http://localhost:8000/api/*` returning `503` from something
   other than this project's backend, not a CORS or code error. Fixed by
   restarting the backend on the documented port `8000`; both the Credit
   Universe table and Market Context panel then rendered real data
   immediately.

**Solutions**

All four were caught by direct verification: re-reading a fixture that
looked "already fixed" rather than assuming Milestone 4's patch covered
every engine, running the same live test module in isolation vs. the full
suite to separate a real rate limit from a flaky assertion, comparing
isolated vs. full-suite timing before deciding a timeout bump was the
honest fix rather than a cover-up, and reading the actual network request
log in the browser (not guessing at CORS) to find the real port mismatch.

**Remaining Work**

- TD-009 (new): FRED sync pulls only the latest N observations, not a full
  historical backfill — deferred until a feature (e.g. a rate chart) needs
  trend history.
- TD-007 stays open (per-field `security` provenance) — this milestone
  found a way to avoid needing it rather than resolving it; see PLAN.md's
  updated note.
- TD-008 partially addressed: OpenFIGI now supplies real per-instrument
  FIGI/maturity/coupon where SEC EDGAR's aggregate-only API couldn't;
  CUSIP/ISIN remain unavailable from either provider.
- Everything in Milestone 6 onward per `PLAN.md` § Milestone Status —
  unstarted; Milestone 6 requires separate approval to begin.

**Git Commit Hash**

`a7f11f27b87a477c160c15aa84b50feb1cc229c3` (`a7f11f2`) — implementation.
`675e18d69fe9c57f7cf76f012af3274ac6d1ee33` (`675e18d`) — follow-up docs
commit recording this hash.

**GitHub Remote and Push Results**

- `git push origin main` — succeeded: `6ee8718..675e18d  main -> main`.
- Post-push verification: `git ls-remote origin main` returns
  `675e18d69fe9c57f7cf76f012af3274ac6d1ee33`, matching the local commit
  exactly.
- Remote branch: https://github.com/kirantoday/nexus-credit-intelligence/tree/main

**Approximate Time Spent**

Single focused implementation session, following directly after Milestone 4
approval (continued across a context interruption; resumed cleanly from
committed task-list/file state with no rework).

**Developer Notes**

The "think like an analyst, not a provider checklist" framing shaped real
design decisions, not just marketing copy: it's why OpenFIGI results became
new `security` rows instead of forcing TD-007's resolution onto the
existing aggregate row, why the benchmark-rate column stayed a plain
reported fact instead of a tempting-but-out-of-scope blended calculation,
and why FRED sync intentionally isn't a bulk historical loader (TD-009) —
each choice traces back to "what real question does this actually answer
right now," not "what could this data support eventually." The
domain/provider-layer conventions from Milestones 2-4 again needed zero
changes for two more provider adapters, which is the strongest evidence yet
that ADR-014's conventions are the right long-term shape.

---

## 2026-08-06 — Milestone 6: Issuer detail page + Capital Structure page/model

**Summary**

Approved with an explicit brief: design Issuer Detail the way a
distressed-credit analyst mentally organizes a company, not around database
tables — "what debt exists? which instrument sits where? what matures
first? what's secured vs. unsecured? what filings support this? what changed
recently? where did this information come from?" — and make it "the primary
research workspace, not simply a detail screen." That last phrase drove a
real, deliberate UI decision: Capital Structure is built as a section
embedded directly inside Issuer Detail, not a separate top-level page an
analyst has to navigate away to reach — the data model and API shape PLAN.md
§4.6/§7 already specify are unchanged, only how the page presents them.

**Features Completed**

- `capital_structure_position` (PLAN.md §4.6): new canonical table, one row
  per layer of an issuer's debt-and-equity stack, `rank_order` governing
  top-to-bottom priority rendering. `security_id` is nullable (a revolver or
  equity layer may have no CUSIP-bearing `security` row). A DB-level CHECK
  constraint (`ck_capstruct_position_recovery_requires_scenario`) enforces
  §7's hard labeling rule at the schema layer: `enterprise_value_coverage`/
  `illustrative_recovery` can never be persisted without `recovery_scenario`
  describing the assumption — not just a UI convention that could be
  bypassed by a future caller.
- `app/synthetic/capital_structure_generator.py`: a pure, independently
  unit-tested `compute_recovery_waterfall` function (no I/O) plus a seed
  function with two parts. Part 1 turns each of the eight existing
  Milestone-4 leveraged-loan issuers' already-seeded loan tranche(s) into a
  reported (non-scenario) `capital_structure_position` row — no
  `enterprise_value_coverage`/`illustrative_recovery` asserted, since
  nothing has modeled a real or illustrative EV for those companies. Part 2
  seeds one new, entirely fictional issuer, Cobalt Ridge Energy Corp, with a
  genuine eight-layer stack (revolver → 1L TLB → 1L notes → 2L notes →
  senior unsecured → subordinated → preferred equity → common equity) and a
  real illustrative recovery waterfall against a stated $650,000,000
  base-case Enterprise Value: the three most senior layers recover 100%, the
  second lien (the layer EV runs out on) recovers 77.14%, and everything
  junior to it recovers 0% — the exact numbers a real priority waterfall
  produces, proven first in isolation by unit tests, then again against the
  persisted rows by integration tests.
- This is the first real, multi-input caller of `calculation`/
  `calculation_input` (§4.2/4.3) since Milestone 2 built them: each layer's
  recovery figure's `provenance` row is `transformation = calculated` with a
  real `calculation_id`, and its `calculation_input` rows trace to the
  shared Enterprise Value assumption plus every strictly-senior layer's own
  principal-fact provenance (not just its own) — so the lineage view can
  show exactly which facts a given recovery number depends on, closing the
  loop TD-007's ADR left open for "the first real caller that needs
  multiplicity."
- `IssuerPage.tsx` (`/issuers/:issuerId`): the primary research workspace,
  organized into sections that are literally the analyst's own questions as
  headings — "What debt exists, where does it sit, and what's secured or
  unsecured?" (the embedded `CapitalStructureStack`, with a Priority
  order/Maturity order toggle answering "what matures first" without a
  second page), "What filings support this?" (financial facts with source
  links), "What changed recently?" (a computed activity timeline — see
  below), "Where did this information come from?" (a data-sources summary
  by provider). When an issuer has no capital structure layers on file
  (every real issuer, this milestone — see TD-010), the page falls back to
  a flat, still fully-provenanced Securities table rather than an empty
  section with no explanation.
- `CapitalStructureStack.tsx`: whenever any layer carries
  `enterprise_value_coverage`/`illustrative_recovery`, the component renders
  the mandatory "Calculated · Scenario-based · Illustrative · Not a market
  fact" label once per table (every cell also carries the exact
  `recovery_scenario` text on hover) — verified live in a browser, not just
  in a unit test.
- `GET /api/issuers/{issuer_id}` and `GET /api/issuers/{issuer_id}/capital-structure`:
  new `issuer_service`/`capital_structure_service` assemble responses from
  `issuer_repository`, `security_repository`, `financial_fact_repository`,
  `capital_structure_repository`, and `provenance_repository`, each row
  passing through the same `policy_check(action="display", ...)` choke
  point Credit Universe already uses. "Recent activity" and "data sources"
  are computed reads over already-provenanced records' own dates/providers
  (financial fact filing dates, security/position `retrieved_at`) — no new
  `credit_event` table, keeping PLAN.md §23.1 out of Version 1 as required.
- Credit Universe's issuer-name cell now links to `/issuers/:issuerId`,
  making Issuer Detail reachable as a real drill-down (PLAN.md §5.3), not
  just a route that exists in isolation.
- Real issuers (Apple Inc.) deliberately get **no** `capital_structure_position`
  rows this milestone: neither SEC EDGAR's company-facts API nor OpenFIGI's
  search endpoint reports seniority/lien position/ranking for a specific
  instrument (the same underlying gap TD-008 already documents) — asserting
  a stack position for real debt this platform hasn't actually sourced that
  fact for would break the provenance discipline every other adapter in this
  codebase follows. Tracked as new TD-010; Apple's Issuer Detail page
  correctly falls back to its flat Securities table instead.

**Files Created**

`backend/alembic/versions/0006_capital_structure_position.py`,
`backend/app/api/routes/capital_structure.py`,
`backend/app/api/routes/issuer.py`,
`backend/app/domain/capital_structure.py`,
`backend/app/models/capital_structure.py`,
`backend/app/repositories/capital_structure_repository.py`,
`backend/app/schemas/capital_structure.py`, `backend/app/schemas/issuer.py`,
`backend/app/services/capital_structure_service.py`,
`backend/app/services/issuer_service.py`,
`backend/app/synthetic/capital_structure_generator.py`,
`backend/tests/unit/test_capital_structure_validators.py`,
`backend/tests/unit/test_capital_structure_generator.py`,
`backend/tests/integration/test_capital_structure_repository.py`,
`backend/tests/integration/test_capital_structure_generator.py`,
`backend/tests/integration/test_issuer_service.py`,
`backend/tests/integration/test_capital_structure_service.py`,
`web/src/api/issuer.ts`, `web/src/api/capitalStructure.ts`,
`web/src/queries/useIssuerDetail.ts`,
`web/src/queries/useCapitalStructure.ts`,
`web/src/components/CapitalStructureStack.tsx`,
`web/src/components/CapitalStructureStack.test.tsx`,
`web/src/pages/IssuerPage.tsx`, `web/src/pages/IssuerPage.test.tsx`.

**Files Modified**

`backend/app/core/types.py` (`CapitalStructureInstrumentType` enum),
`backend/app/main.py` (mounts `issuer_router`/`capital_structure_router`),
`backend/app/models/__init__.py` (imports `capital_structure`),
`web/src/App.tsx` (`/issuers/:issuerId` route),
`web/src/pages/CreditUniversePage.tsx` (issuer-name cell links to Issuer
Detail).

**Database Changes**

Migration `0006` applied to the live, shared Supabase project (autogenerated
against the ORM model, hand-reviewed, renamed to the project's `000N_`
convention): creates `nexus.capital_structure_position` with four CHECK
constraints (`instrument_type`, `seniority`, `is_synthetic`/
`synthetic_reason`, and the recovery/scenario pairing rule) and a unique
`(issuer_id, rank_order)` index. One real bug caught during the first
`alembic upgrade head` attempt: the auto-generated constraint name
`ck_capital_structure_position_synthetic_reason_requires_is_synthetic` is 69
characters, over Postgres's 63-character identifier limit — the error
surfaced client-side, before any DDL executed (`alembic current` confirmed
still at `0005`), so the fix (abbreviating `capital_structure_position` to
`capstruct_position` in constraint names only, never in the table/column
names themselves) was applied cleanly with no partial-migration state to
clean up. Verified with `alembic check` afterward: no drift between the ORM
models and the live schema.

Separately, a genuine (non-test, committed) live seed was run:
`nexus.issuer` now permanently contains one new fictional issuer, Cobalt
Ridge Energy Corp (`is_synthetic = true`, `cik = NULL`); `nexus.security`
gained five new synthetic securities (its TLB/1L notes/2L notes/senior
unsecured/subordinated tranches); `nexus.capital_structure_position`
permanently contains its full 8-layer stack plus one reported row per loan
tranche across all eight of Milestone 4's existing synthetic issuers (10
rows total: six issuers with one tranche, two with two tranches each).
Re-running the seed script twice
consecutively confirmed full idempotency: the second run reported the same
issuer id and the same 8 Cobalt Ridge positions, and a direct query
confirmed no duplicate rows for any of the eight existing loan issuers.

**API Endpoints Added**

`GET /api/issuers/{issuer_id}` — returns `IssuerDetail` (identity,
`securities[]`, `financial_facts[]`, `data_sources[]`, `recent_activity[]`),
404 if the issuer doesn't exist. `GET /api/issuers/{issuer_id}/capital-structure`
— returns `CapitalStructureResponse` (`positions[]`, already ordered by
`rank_order`), 404 if the issuer doesn't exist.

**Frontend Pages Added**

`IssuerPage.tsx` at `/issuers/:issuerId` — the primary research workspace
described above.

**Environment Variables Added**

None.

**Tests Added**

38 new backend tests (166 → 204): `test_capital_structure_validators.py`
(8 — synthetic-reason/recovery-scenario domain validators),
`test_capital_structure_generator.py` (unit, 7 — pure waterfall math: full
coverage, partial coverage at the shortfall layer, wipeout of junior layers,
coverage-multiple arithmetic, single-layer and zero-EV edge cases),
`test_capital_structure_repository.py` (8 — CRUD, rank ordering, nullable
`security_id`, unique-rank and CHECK constraints enforced at the DB level),
`test_capital_structure_generator.py` (integration, 7 — the persisted
Cobalt Ridge stack matches the unit-tested waterfall exactly, calculation
lineage has the right input roles/counts, idempotency, the eight existing
loan issuers get reported-only layers), `test_issuer_service.py` (5),
`test_capital_structure_service.py` (3).

9 new frontend tests (29 → 38): `CapitalStructureStack.test.tsx` (5 — empty
state, error state, layer rendering, the mandatory four-part label appears
only when a recovery figure is present), `IssuerPage.test.tsx` (4 — identity
and data sources render, flat-securities fallback shown/hidden correctly,
404 handling).

**Test Results**

```
backend: pytest -q                             -> 204 passed
backend: ruff check .                          -> All checks passed!
backend: black --check .                       -> 117 files would be left unchanged.
backend: mypy .                                -> Success: no issues found in 111 source files
backend: alembic current                       -> 0006 (head)
backend: alembic check                         -> No new upgrade operations detected.

frontend: npm run test                         -> 38 passed (7 test files)
frontend: npm run lint                         -> clean
frontend: npm run format:check                 -> All matched files use Prettier code style!
frontend: npm run typecheck                    -> clean (tsc -b)
frontend: npm run build                        -> succeeded (dist/assets bundle 609.83 kB / gzip 185.80 kB)

GET /health (live server, port 8000)           -> 200 {"status": "healthy", ...}
GET /api/issuers/{cobalt-ridge-id} (live)      -> 200, full 8-layer stack with correct recovery figures
GET /api/issuers/{cobalt-ridge-id}/capital-structure (live) -> 200, positions ordered by rank_order
GET /api/issuers/{random-uuid} (live)          -> 404
```

**Commands Executed** (representative)

```
cd backend
./.venv/Scripts/python -m alembic revision --autogenerate -m "capital structure position"
mv alembic/versions/<hash>_capital_structure_position.py alembic/versions/0006_capital_structure_position.py
./.venv/Scripts/python -m alembic upgrade head   # first attempt: identifier-length IntegrityError, see Problems Encountered
./.venv/Scripts/python -m alembic current        # confirmed still at 0005, no partial state
./.venv/Scripts/python -m alembic upgrade head   # succeeded after shortening constraint names
./.venv/Scripts/python -m alembic check          # No new upgrade operations detected.

./.venv/Scripts/python -m pytest -q
./.venv/Scripts/python -m ruff check . / black --check . / mypy .

# genuine, committed (non-test) live seed — see Database Changes
./.venv/Scripts/python seed_milestone6.py   # Cobalt Ridge + reported loan-issuer layers + commit
./.venv/Scripts/python seed_milestone6.py   # re-run: confirmed idempotent, same issuer id/positions
rm seed_milestone6.py                       # not committed, matching Milestone 4/5 precedent

cd ../web
npm run format / lint / typecheck / test / build

# manual browser verification (Chrome, via claude-in-chrome tools)
# Cobalt Ridge Energy Corp's full 8-layer waterfall renders with correct
# recovery percentages and the mandatory four-part label; a single-tranche
# synthetic issuer (Summit Building Products Inc) renders correctly with
# EV Coverage/Illustrative Recovery both honestly "—"; Apple Inc. falls back
# to its flat Securities table with all 6 real bonds and no capital
# structure section error
```

**Deployment Validation**

Not exercised — Railway/Vercel deployment remains Milestone 15 scope. Both
the backend (`uvicorn`, port 8000) and frontend (`vite dev`, port 5173) dev
servers were run locally and confirmed booting and serving real,
live-Supabase-backed data end-to-end in a browser.

**Problems Encountered**

1. **A real Postgres identifier-length limit hit on the first migration
   attempt.** Autogenerate produced
   `ck_capital_structure_position_synthetic_reason_requires_is_synthetic`
   (69 characters) — Postgres silently truncates or, as here, SQLAlchemy's
   own `validate_identifier` raises before ever reaching the database once a
   constraint name exceeds 63 characters. Caught immediately by the
   traceback, not a downstream symptom. Confirmed via `alembic current`
   that the failed attempt left the database untouched (still at `0005`)
   before retrying, since `CREATE TABLE ... CHECK (...)` is one statement
   and the failure was a client-side compile error. Fixed by abbreviating
   `capital_structure_position` to `capstruct_position` in the four
   constraint names only (`ck_capstruct_position_*`), keeping the actual
   table and column names unabbreviated everywhere else.

**Solutions**

The identifier-length issue was caught by the traceback itself pointing
directly at `sqlalchemy.exc.IdentifierError` with the exact 69-character
name — no guessing required, just shortening the four names that actually
needed it and re-running `alembic upgrade head`, then confirming with
`alembic check` that the model and live schema agreed exactly.

**Remaining Work**

- TD-010 (new): real issuers have no `capital_structure_position` rows —
  deferred until a provider that actually reports lien/seniority/ranking
  data exists (a licensed provider, Milestone 14, or a future SEC
  dimensional-XBRL parse).
- TD-007 stays open (per-field `security` provenance) — unaffected by this
  milestone.
- TD-008 unchanged — SEC/OpenFIGI still can't supply CUSIP/ISIN or
  per-instrument capital-structure placement.
- Everything in Milestone 7 onward per `PLAN.md` § Milestone Status —
  unstarted; Milestone 7 requires separate approval to begin.

**Developer Notes**

The instruction to make Issuer Detail "the primary research workspace, not
simply a detail screen" was treated as a real design constraint, not just
framing: it's the reason Capital Structure renders as an embedded section of
`IssuerPage` rather than a separate page an analyst has to leave and come
back from, and the reason each section heading is phrased as the analyst's
own question rather than a database-table name. The Cobalt Ridge Energy
Corp waterfall is this codebase's first genuine exercise of
`calculation`/`calculation_input` with real multiplicity — every prior
milestone's `calculation` usage (VWAP, price-change metrics) was
documented but never actually built, so this was also the first real proof
that the pattern designed in Milestone 2 holds up under an actual multi-input
case, not just a single-input one.

**Git Commit Hash**

`2262e7ce852fd4f81a7894d97815f59292bb5ea2` (`2262e7c`) — implementation.
`90befc60889a71a05fd9f9c5ff63c7d20c951aff` (`90befc6`) — follow-up docs
commit recording this hash.

**GitHub Remote and Push Results**

- `git push origin main` — succeeded: `cb20713..90befc6  main -> main`.
- Post-push verification: `git ls-remote origin main` returns
  `90befc60889a71a05fd9f9c5ff63c7d20c951aff`, matching the local commit
  exactly.
- Remote branch: https://github.com/kirantoday/nexus-credit-intelligence/tree/main

---

## 2026-08-06 — Milestone 6.5: Research Universes + Overnight Distress Filing Monitor

**Summary**

Inserted before Milestone 7 (CourtListener) by explicit approved direction —
the CFO's most directly-requested workflow (reduce manual research effort,
organize issuers the way a distressed-credit team thinks, surface new
distress-related filing activity each morning, drill from an alert into
Issuer Detail/Capital Structure). Organization-wide, curated "Research
Universes" (distinct from and coexisting with the still-unbuilt personal/team
Watchlists of Milestone 8) populated with real, live SEC-verified issuers,
plus a two-layer (deterministic + governed Anthropic AI) overnight SEC filing
distress-detection pipeline producing evidence-backed, cautiously-worded
alerts surfaced on a new "Morning Research Brief" page. The plan was refined
through several rounds of explicit approval before implementation:
generalizing `distress_evidence` into provider-agnostic `research_evidence`,
redesigning the alert pipeline around an internal Evidence Bundle concept
rather than a hard `filing_id` FK, renaming "Morning Filing Brief" to
"Morning Research Brief," and replacing a generic `LLM_API_KEY` with
provider-specific credential configuration. See ADR-016, ADR-017, ADR-018.

**Features Completed**

- `collection`/`collection_membership` (ADR-016): generalizes the approved
  §4.7 watchlist shape into one table pair with a `collection_type`
  discriminator (`research_universe`|`watchlist`|`benchmark`), so Research
  Universes and the still-unbuilt personal Watchlists share one schema
  without either faking the other's fields. `collection_membership` carries
  a dated `rationale`, never a current-status assertion.
- `sec_filing`: the first canonical entity representing "this filing exists"
  (`financial_fact` remained XBRL-datapoint-level only). `providers/sec_edgar`
  extended with `list_recent_filings`/`ingest_recent_filings` (parses
  `filings.recent`'s parallel arrays, including 8-K item codes),
  `fetch_filing_text` (fetches and strips real filing HTML via a stdlib
  `html.parser.HTMLParser` tag stripper, no new dependency), and
  `ingest_issuer_identity_only` for the seed script.
- `research_evidence`/`alert_event` (ADR-018): provider-agnostic from the
  start — `evidence_provider` column (SEC EDGAR is the first, not the only,
  intended value), evidence grouped into an internal, non-persisted
  **Evidence Bundle** (`app/domain/evidence_bundle.py`,
  `group_evidence_into_bundles`) before becoming one `alert_event`.
  `alert_event` has no `filing_id` column at all — it carries `evidence_ids`
  (the real source of truth) plus a denormalized `primary_source_label`/
  `primary_source_url` built by a provider-specific describer function
  injected into the otherwise generic `alert_synthesis_service`. Alert
  provenance reuses the `calculation`/`calculation_input` lineage machinery
  Milestone 6 established for `illustrative_recovery` — one `calculation_input`
  row per contributing evidence item's provenance.
- `app/core/distress_rules.py` (Layer 1, deterministic): explainable phrase/
  item-code rules covering all ~26 `EvidenceType` values (8-K Item 1.03/2.04,
  "chapter 11"/"chapter 7", "substantial doubt about its ability to continue
  as a going concern", restructuring support agreements, exchange offers,
  DIP financing, delisting, workforce reduction, material impairment, and
  more), deliberately conservative around ambiguous phrases — a bare
  "chapter 11" mention without stronger context gets a
  `phrase_chapter_11_bare_mention` low-confidence match, not exclusion or a
  high-severity false alarm.
- `app/ai/` (Layer 2, governed AI, ADR-017): `LLMProvider` Protocol and a
  real `AnthropicProvider` pulled forward from Milestone 13, scoped narrowly
  to evidence classification (`call_tools`/`create_embeddings` explicitly
  raise `NotImplementedError`). `app/ai/factory.py` reads `LLM_PROVIDER`,
  validates only that provider's own credentials, never falls back silently.
  `app/ai/evidence_review.py` builds a constrained prompt restricted to the
  supplied excerpts and **fails closed** to deterministic templated wording
  on any parse failure or unsupported claim.
- `app/services/filing_monitor_service.py`: the SEC-specific orchestrator —
  baseline (establishes a watermark, ingests nothing)/delta (since the
  previous successful watermark)/backfill (explicit lookback window, labeled
  "Historical Backfill Demo") modes, idempotent by `accession_no` uniqueness,
  per-issuer commit/rollback isolation so one issuer's failure never loses an
  earlier issuer's already-committed work in the same run, watermark only
  advances on a zero-error run.
- `app/services/alert_synthesis_service.py`: the provider-agnostic half —
  takes evidence, groups it into bundles, checks `bundle_key` idempotency,
  calls AI review if configured (else deterministic templated wording),
  creates one `alert_event` per new bundle. Contains zero SEC-specific field
  references.
- `app/scripts/run_overnight_filing_monitor.py` (new `app/scripts/`
  directory): standalone entry point, opens its own session (not the FastAPI
  `get_db` dependency, since the service manages its own commit boundaries),
  resolves the LLM provider with a try/except that falls back to
  deterministic-only mode rather than crashing the job. Target production
  schedule documented (Railway Cron, `0 9 * * *`) but not activated — no
  production Railway environment exists yet.
- `app/scripts/seed_research_universes.py`: live-resolves ~30 candidate
  tickers against SEC's public `company_tickers.json` (word-boundary
  matching only, never substring — see Problems Encountered #1),
  live-verifies each via `fetch_submissions`, ingests via
  `ingest_issuer_identity_only`, creates 15 `collection` rows and their
  `collection_membership` rows with dated rationale. Idempotent — safe to
  re-run (verified twice).
- API routes: `research_universes.py`, `filing_monitor.py` (trigger endpoint
  non-production-gated, interim stand-in for admin/demo-only per TD-002),
  `research_evidence.py`, `alerts.py`, `morning_brief.py`, plus a `universe`
  filter added to `credit_universe.py` and `universe_memberships` added to
  `issuer.py`'s response.
- Frontend: `ResearchUniversesPage.tsx` (`/research-universes` — universe
  cards, benchmark universes visually and structurally separated into their
  own section), `MorningResearchBriefPage.tsx` (`/research-brief` — heading
  "New Research Alerts — Since Last Successful Run," deliberately not "New
  Distress *Filings*," so future non-SEC alerts fit without a copy change;
  full filter set, all URL-persisted matching the existing
  `CreditUniversePage` pattern), `AlertCard.tsx` (evidence expansion,
  ack/dismiss actions), `UniverseCard.tsx`, `SeverityBadge.tsx`,
  `BriefSummaryBar.tsx`. `CreditUniversePage` gained a `universe` URL
  filter; `IssuerPage` gained a "Which Research Universes is this issuer
  in?" section. Two new enabled nav entries (Research Universes, Morning
  Research Brief); the other five disabled "Soon" placeholders (Watchlists,
  Search, Research Workspace, Alerts, Research Assistant) are untouched —
  they belong to later milestones.

**Files Created**

`backend/alembic/versions/0007_research_universes_and_filing_monitor.py`,
`backend/app/ai/providers/base.py`,
`backend/app/ai/providers/anthropic_provider.py`, `backend/app/ai/factory.py`,
`backend/app/ai/llm_gate.py`, `backend/app/ai/evidence_review.py`,
`backend/app/api/routes/{alerts,filing_monitor,morning_brief,research_evidence,research_universes}.py`,
`backend/app/core/distress_rules.py`,
`backend/app/domain/{alert,collection,evidence_bundle,filing_monitor_run,research_evidence,sec_filing}.py`,
`backend/app/models/{alert,collection,filing_monitor_run,research_evidence,sec_filing}.py`,
`backend/app/repositories/{alert_repository,collection_repository,filing_monitor_run_repository,research_evidence_repository,sec_filing_repository}.py`,
`backend/app/schemas/{filing_monitor,research_universe}.py`,
`backend/app/scripts/{run_overnight_filing_monitor,seed_research_universes}.py`,
`backend/app/services/{alert_synthesis_service,filing_monitor_api_service,filing_monitor_service,research_universe_service}.py`,
`backend/tests/integration/{test_ai_evidence_review_live,test_filing_monitor_api_service,test_filing_monitor_service,test_research_universe_service}.py`,
`backend/tests/unit/{test_alert_wording,test_distress_rules,test_evidence_bundling,test_evidence_review,test_llm_factory,test_seed_research_universes}.py`,
`web/src/api/{filingMonitor,researchUniverse}.ts`,
`web/src/components/{AlertCard,AlertCard.test,BriefSummaryBar,SeverityBadge,UniverseCard,UniverseCard.test}.tsx`,
`web/src/pages/{MorningResearchBriefPage,MorningResearchBriefPage.test,ResearchUniversesPage,ResearchUniversesPage.test}.tsx`,
`web/src/queries/{useAlerts,useMorningBrief,useResearchUniverses}.ts`.

**Files Modified**

`.env.example`, `backend/app/api/routes/credit_universe.py`,
`backend/app/config.py` (removed `llm_api_key`; added provider-specific
`anthropic_api_key`/`anthropic_model`/`openai_api_key`/`openai_model`/
`azure_openai_api_key`/`azure_openai_endpoint`/`azure_openai_model`/
`embedding_provider`), `backend/app/core/types.py` (new enums +
`MONITORED_FORM_TYPES`), `backend/app/main.py` (mounts the five new
routers), `backend/app/models/__init__.py`,
`backend/app/providers/sec_edgar/{client,dto,normalizer,provider}.py`,
`backend/app/repositories/security_repository.py`,
`backend/app/schemas/issuer.py`, `backend/app/services/credit_universe_service.py`,
`backend/app/services/issuer_service.py`, `backend/pyproject.toml` (added
`anthropic` dependency), `backend/tests/integration/conftest.py`
(`join_transaction_mode="create_savepoint"`, needed because
`filing_monitor_service` manages its own commit boundaries),
`backend/tests/integration/{test_credit_universe_service,test_issuer_service}.py`,
`backend/tests/unit/test_sec_edgar_normalizer.py`, `web/src/App.tsx` (two
new routes), `web/src/api/{creditUniverse,issuer}.ts`,
`web/src/components/Layout.tsx` (two new enabled nav entries),
`web/src/pages/{CreditUniversePage,IssuerPage,IssuerPage.test}.tsx`.

**Database Changes**

Migration `0007` applied to the live, shared Supabase project and
round-tripped (`upgrade head` → `downgrade 0006` → `upgrade head`) at
creation time, before real data existed: creates `nexus.collection`,
`nexus.collection_membership`, `nexus.sec_filing`, `nexus.filing_monitor_run`,
`nexus.research_evidence`, `nexus.alert_event`, all CHECK-constrained per
ADR-014 convention. Verified with `alembic check` afterward — no drift.

Real, permanently-committed live seed: `seed_research_universes.py` ingested
23 real, SEC-verified issuers (23 accepted / 7 rejected of 30 candidates —
RAD, MNK, YELL, BIG, FYBR, SAVE, COMM excluded, all ambiguity resolved
honestly, see Problems Encountered) into 15 `collection` rows (14 Research
Universes + 1 Investment Grade Benchmark of 5 large-cap issuers). A live
baseline run established a clean watermark (`issuers_checked=23`), followed
by a real, explicitly-labeled 60-day Historical Backfill Demo against live
SEC EDGAR data: 85 `sec_filing` rows, 83 `research_evidence` rows, 28
`alert_event` rows (4 high / 5 medium / 19 low severity, all 28 reviewed by
live Anthropic calls), zero run errors, watermark advanced. Re-running the
seed script confirmed full idempotency (same 23 accepted / 7 rejected, no
duplicate collections or memberships).

**API Endpoints Added**

`GET /api/research-universes`, `GET /api/research-universes/{id}`,
`GET /api/research-universes/{id}/issuers`, `GET /api/filing-monitor/runs`,
`GET /api/filing-monitor/runs/latest-successful`,
`GET /api/filing-monitor/filings`, `POST /api/filing-monitor/runs/trigger`
(non-production-gated), `GET /api/research-evidence`, `GET /api/alerts`,
`POST /api/alerts/{id}/acknowledge`, `POST /api/alerts/{id}/dismiss`,
`GET /api/morning-brief`. `GET /api/credit-universe` gained a `universe`
filter param; `GET /api/issuers/{id}` gained `universe_memberships`.

**Frontend Pages Added**

`ResearchUniversesPage.tsx` at `/research-universes`,
`MorningResearchBriefPage.tsx` at `/research-brief`.

**Environment Variables Added**

`LLM_PROVIDER` (unchanged), `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`,
`OPENAI_API_KEY`, `OPENAI_MODEL`, `AZURE_OPENAI_API_KEY`,
`AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_MODEL`, `EMBEDDING_PROVIDER`
(reserved, unused). `LLM_API_KEY` removed (the naming mismatch that left AI
review silently unusable — `ANTHROPIC_API_KEY` already existed in
`backend/.env` but nothing read it until this milestone).

**Tests Added**

70 new backend tests (204 → 274): `test_distress_rules.py`,
`test_evidence_bundling.py`, `test_alert_wording.py`, `test_llm_factory.py`,
`test_evidence_review.py` (unit — rule matching and the false-positive
safeguard, bundle grouping including a synthetic multi-provider bundle,
cautious-wording templates, per-provider LLM config validation with no
silent fallback, malformed-AI-response fail-closed behavior),
`test_seed_research_universes.py` (unit — CIK resolver regression tests
including the exact Yellow/Yellowstone false-positive case),
`test_research_universe_service.py`, `test_filing_monitor_api_service.py`,
`test_filing_monitor_service.py` (integration — baseline/delta/backfill,
watermark advance-on-success/hold-on-failure, idempotent re-run, per-issuer
error isolation), plus one test each added to
`test_credit_universe_service.py` (universe filter) and
`test_issuer_service.py` (universe memberships).
`test_ai_evidence_review_live.py` is a genuinely live-marked suite (real
Anthropic call) — not skipped, since a real key is configured.

23 new frontend tests (38 → 61) across 4 new files: `UniverseCard.test.tsx`
(6 — name/issuer-count/priority/verification rendering, benchmark chip only
on benchmark collections, singular/plural issuer count, click-to-navigate),
`AlertCard.test.tsx` (9 — headline/severity/detection-method rendering,
issuer drill-down link, backfill-demo chip only when `is_backfill`,
AI-assisted vs. deterministic labeling, evidence expansion, ack/dismiss
callbacks, buttons hidden once already acknowledged/dismissed),
`ResearchUniversesPage.test.tsx` (3 — universe/benchmark sections, empty
state, error state), `MorningResearchBriefPage.test.tsx` (4 — summary bar +
alert cards render, empty-filter success message, alert/brief API error
states).

**Test Results**

```
backend: pytest tests/ -q                      -> 274 passed
backend: ruff check .                          -> All checks passed!
backend: black --check .                       -> 166 files would be left unchanged.
backend: mypy app                              -> Success: no issues found in 115 source files
backend: alembic current                       -> 0007 (head)
backend: alembic check                         -> No new upgrade operations detected.

frontend: npx vitest run                       -> 61 passed (11 test files)
frontend: npx eslint .                         -> clean
frontend: npx prettier --check src             -> All matched files use Prettier code style!
frontend: npx tsc --noEmit                     -> clean
frontend: npm run build                        -> succeeded (dist/assets bundle 641.87 kB / gzip 192.73 kB)

GET /health (live server, port 8000)                    -> 200 {"status": "healthy", ...}
GET /api/morning-brief (live)                           -> 200, real counts (15 universes, 23 issuers,
                                                            85 filings, 28 alerts, 4/5/19 severity split)
python -m app.scripts.run_overnight_filing_monitor --mode baseline
    -> baseline_established, issuers_checked=23
python -m app.scripts.run_overnight_filing_monitor --mode backfill --backfill-days 60
    -> success, filings_discovered=85, filings_processed=85, alerts_created=28, errors_count=0
```

**Commands Executed** (representative)

```
cd backend
./.venv/Scripts/python -m alembic revision --autogenerate -m "research universes and filing monitor"
mv alembic/versions/<hash>_*.py alembic/versions/0007_research_universes_and_filing_monitor.py
./.venv/Scripts/python -m alembic upgrade head
./.venv/Scripts/python -m alembic downgrade 0006   # round-trip, before real data existed
./.venv/Scripts/python -m alembic upgrade head
./.venv/Scripts/python -m alembic check            # No new upgrade operations detected.

./.venv/Scripts/python -m pytest tests/ -q
./.venv/Scripts/python -m ruff check . / black --check . / mypy app

# genuine, committed (non-test) live seed
./.venv/Scripts/python -m app.scripts.seed_research_universes
./.venv/Scripts/python -m app.scripts.seed_research_universes   # re-run: confirmed idempotent

# genuine, committed (non-test) live monitor runs
./.venv/Scripts/python -m app.scripts.run_overnight_filing_monitor --mode baseline
./.venv/Scripts/python -m app.scripts.run_overnight_filing_monitor --mode backfill --backfill-days 60

cd ../web
npx vitest run / eslint . / prettier --check src / tsc --noEmit / npm run build

# manual browser verification (Chrome, via claude-in-chrome tools)
# Research Universes page with benchmark section visually/structurally
# separated; Morning Research Brief summary bar with real counts, severity
# filter (URL-persisted), evidence expansion showing real matched-rule
# excerpts from a real EchoStar 8-K; drill-down from an alert into Issuer
# Detail's Research Universe Memberships section; Credit Universe filtered
# by Investment Grade Benchmarks returning Apple's real securities
```

**Problems Encountered**

1. **A real CIK/ticker identity-mismatch bug in the seed script's
   resolver.** `_resolve_cik`'s original name-fallback used substring
   containment (`"yellow" in "yellowstone group ltd."`) — after ticker YELL
   failed to resolve directly (Yellow Corp had genuinely delisted, a
   legitimate rejection), the substring fallback matched the unrelated
   "Yellowstone Group Ltd." and would have permanently committed a wrong
   issuer into the Chapter 11/Bankruptcy universe. Caught by manually
   reviewing the resolution log before trusting it, not by a test — no test
   existed yet for this path. Fixed with word-boundary regex matching
   (`re.compile(rf"\b{re.escape(candidate.name_hint.lower())}\b")`); the
   already-committed bad `collection_membership` row (created before the
   fix) was removed live via a one-off script using a newly-added
   `collection_repository.remove_membership` function; a regression test
   suite (`test_seed_research_universes.py`) was added covering this exact
   case plus ambiguous-match exclusion and no-match cases.
2. **A `calculation_input` composite-key collision on filings matching
   multiple rules.** `fetch_filing_text`'s original design created one
   `provenance` row per filing (reused across every matched rule) — a
   filing matching 2+ deterministic rules produced 2+ `research_evidence`
   rows sharing one `provenance_id`, and an alert bundle citing both then
   violated `calculation_input`'s composite primary key. Fixed by moving
   provenance creation into
   `filing_monitor_service._process_one_filing`'s per-match loop (one
   distinct `provenance` row per matched rule, all referencing the same
   underlying `raw_payload_id`), matching Milestone 3's established "one
   raw payload, many provenance rows" convention.
3. **`raw_provider_payload.payload_json` validator violation for extracted
   filing text.** `fetch_filing_text` originally passed `payload_json=None`
   for HTML filing documents, but the domain validator requires either
   `payload_json` or `storage_object_path` (TD-006's "store inline for now"
   precedent didn't yet cover this new payload shape). Fixed by wrapping
   extracted text as `{"extracted_text": text}`.
4. **A genuine test-design flaw surfaced only after real seed data
   existed.** `test_filing_monitor_service.py`'s fake `fetch_filings_fn`/
   `fetch_filing_text_fn` test doubles were written and passed while no
   real Research Universe issuers existed, so each test's fake implicitly
   only ever produced data for its own single seeded issuer. Once
   `seed_research_universes.py` permanently committed 23 real issuers,
   `run_monitor` correctly began iterating all 24 issuers in scope (by
   design — it targets every issuer in a `research_universe`/`benchmark`
   collection system-wide, not "whichever issuer this test cares about"),
   and 5 of 7 tests failed: one test's fake unconditionally raised for all
   24 issuers (`errors_count=24` instead of 1, real CIKs like JPMorgan's
   and Costco's visible in the failure output); others produced/reused the
   same filing/accession-number across every iteration, inflating counters
   or attributing evidence to the wrong issuer. This was a real,
   live-observed test-isolation gap, not a production code bug —
   `run_monitor`'s system-wide iteration is correct, intentional behavior.
   Fixed by making every fake CIK-aware (checks the incoming `cik` against
   the test's own seeded issuer, no-ops for every other CIK) and relaxing
   `issuers_checked == 1` to `>= 1` in the baseline test.

**Solutions**

Each problem was caught either by manual review of live resolution output
(#1), a live integration test run against Supabase surfacing the exact
constraint name and violating rows (#2), a live validator error at
ingestion time (#3), or a live full-suite pytest run after seed data
existed (#4) — none were guessed at or silently patched around. #1 and #4
both prompted new regression tests so the same class of bug can't recur
silently.

**Remaining Work**

- TD-011 (new): Issuer Detail's pre-existing "What filings support this?"/
  "What changed recently?" sections are `financial_fact`-scoped only, not
  yet extended to surface `sec_filing`/`alert_event` activity — discovered
  during this milestone's browser walkthrough, not a scope violation
  (PLAN.md §24.9 only committed to the separate Research Universe
  Memberships section, which is correct), but a real gap worth closing.
- Delta mode shares `run_monitor`'s code path with baseline/backfill and is
  covered by the integration test suite, but has not yet been run live —
  there is no second day of real overnight data yet to process a delta
  against. First real delta run happens whenever the monitor is next
  triggered (manually, or once Railway Cron is wired up in Milestone 15).
- TD-001 through TD-010 unchanged, carried forward from prior milestones.
- Everything in Milestone 7 onward per `PLAN.md` § Milestone Status —
  unstarted; Milestone 7 (CourtListener) requires separate explicit
  approval to begin, per this milestone's own governance instructions.

**Developer Notes**

The two-layer detection design was validated by real behavior, not just
unit tests: the live 60-day backfill's 28 AI-reviewed alerts show the
deterministic layer correctly surfacing candidates (including
intentionally ambiguous ones — JPMorgan Chase, Johnson & Johnson,
Microsoft, and Ford all matched a bare "chapter 11" phrase rule somewhere
in their real 10-Ks) and the AI review layer correctly distinguishing a
routine tax-code reference, a subsidiary's already-dismissed historical
case, or boilerplate risk-factor language from EchoStar's and Office
Properties Income Trust's genuine, current Chapter 11 proceedings —
downgrading the former to low severity with explicit "no distress language
found" wording rather than surfacing false alarms, and correctly citing the
exact default/acceleration mechanism (not a bare "bankruptcy" assertion)
for the latter. This is the system doing what §24.4's "cautiously worded,
never overclaiming" requirement actually asked for, not just passing a
test that says so.

The mid-implementation architectural refinements (Evidence Bundle,
generalized `research_evidence`, provider-specific AI credentials) all
proved their worth during real implementation, not just in the abstract:
`filing_monitor_service` never had to import anything alert-specific,
`alert_synthesis_service` never had to import anything SEC-specific, and
the AI provider factory's provider-specific validation caught the
pre-existing `LLM_API_KEY`/`ANTHROPIC_API_KEY` naming mismatch immediately
rather than silently running deterministic-only forever without anyone
noticing why.

**Git Commit Hash**

`4900162175e6e30825f6089910f77c5c06f26fa6` (`4900162`) — implementation.

**GitHub Remote and Push Results**

- `git push origin main` — succeeded: `d894a33..ff2321c  main -> main`.
- Post-push verification: `git ls-remote origin main` returns
  `ff2321c32a4cf2b59862c74a6b157a6c2975d378`, matching the local commit
  exactly.
- Remote branch: https://github.com/kirantoday/nexus-credit-intelligence/tree/main

---

## 2026-08-07 — Milestone 7: CourtListener adapter + docket view

**Summary**

CourtListener/RECAP integration — "what happened in court?" — wired into
the exact provider-agnostic evidence/alert pipeline ADR-018 documented
before this milestone existed: `evidence_provider = courtlistener`, a
nullable `docket_entry_id` FK on `research_evidence` alongside the existing
`filing_id`, and a CourtListener-specific source-describer injected into
the unchanged `alert_synthesis_service`/`alert_event` schema. Real API
research came first, live, before any code: confirmed CourtListener's
Search API works anonymously but the actual docket-entries/RECAPDocument
detail endpoints return `401` without a real `COURTLISTENER_API_TOKEN`
(user-supplied, one malformed-`.env`-line bug and one truncated-token bug
found and fixed live before the token worked — see Problems Encountered).
Docket discovery turned out to require a materially different design from
SEC's automatic per-CIK feed — no equivalent "list new PACER cases for
issuer X" endpoint exists — recorded as ADR-019 rather than silently
built around.

**Features Completed**

- `court_docket`/`court_docket_entry`/`docket_document` (PLAN.md §4.5, §15):
  the frozen schema, extended with real, necessary idempotency columns
  (`courtlistener_docket_id`/`courtlistener_entry_id`/`courtlistener_document_id`,
  each uniquely indexed — the same role `sec_filing.accession_no` plays for
  SEC) and a `chapter` column (real, valuable data the Search API already
  returns). `docket_document.is_sealed` is enforced at both the domain
  validator and a DB CHECK constraint (`ck_docket_document_sealed_never_recap_available`)
  — never `recap_available` when sealed, PLAN.md §22.
- `app/providers/courtlistener/` (`client.py`, `dto.py`, `normalizer.py`,
  `provider.py`): the same Provider DTO → Normalizer → Canonical Domain
  Object → Repository pipeline every other provider follows. `search_dockets`
  (anonymous-capable, used for discovery) and `sync_docket_entries`
  (token-required, paginated, idempotent by `courtlistener_entry_id`) are
  the two real entry points. Document `plain_text` arrives inline on the
  docket-entries response itself — confirmed live — so no second per-document
  fetch is needed the way SEC's separate filing-document fetch is.
- `app.core.distress_rules` extended with 6 new docket-specific
  `EvidenceType` values and phrase rules (`plan_confirmed`, `case_dismissed`,
  `case_converted`, `trustee_appointed`, `claims_bar_date_set`,
  `relief_from_stay_motion`) grounded in real CourtListener docket-entry
  language confirmed live (e.g. the real "Receipt of Motion for Relief From
  Stay" text from Diebold Nixdorf's docket). Existing SEC-filing phrase
  rules (`phrase_chapter_11_petition`, `phrase_dip_financing`, etc.) are
  reused unchanged for docket text — both are just English prose to this
  layer, no separate rule engine needed. `DOCKET_EXCLUDED_RULE_IDS` excludes
  the two ambiguous "bare mention" rules from docket text specifically — see
  Problems Encountered for the real noise problem this fixes.
- `app.domain.evidence_bundle._source_key` extended to check
  `docket_entry_id` alongside `filing_id` — a real bug caught before
  shipping (see Problems Encountered) that would have merged every
  docket-sourced evidence item for an issuer into one bundle.
- `app.services.court_docket_service`: the CourtListener-specific
  orchestrator, mirroring `filing_monitor_service`'s per-unit error
  isolation and provenance-per-match pattern. `sync_one_docket` takes an
  injectable `sync_docket_entries_fn` (mirrors `filing_monitor_service`'s
  injectable fetch functions) so evidence/alert-synthesis logic is
  unit-testable without hitting live CourtListener, and — unplanned but
  genuinely useful — let a live data-quality bug be fixed via a local-only
  reprocessing pass with zero new network calls (see Problems Encountered).
  `_describe_courtlistener_source` is the one place CourtListener-specific
  source formatting happens, injected into the still-unchanged
  `alert_synthesis_service`.
- `app.scripts.link_court_dockets`: the curated, live-verified discovery
  step (ADR-019) — searches CourtListener by name, confirms the result
  matches an expected `courtlistener_docket_id` before linking, rejects and
  documents anything that doesn't match (the same live-verification
  discipline `seed_research_universes` established). `app.scripts.sync_court_dockets`:
  the repeatable half, idempotent per entry, `--backfill` flag for the
  historical-demo labeling.
- `GET /api/court-dockets`, `GET /api/court-dockets/{id}` (`court_docket_api_service`,
  thin routes) and a new `court_dockets` field on `GET /api/issuers/{id}`.
  Issuer Detail gained a "What happened in court?" section (`CourtDocketSection.tsx`)
  embedded the same way Capital Structure is — real docket header (case
  name, docket number, court, chapter, filed date, CourtListener link) plus
  the 10 most recent entries with document-availability status, honestly
  showing "(no description on file)"/"Not on RECAP" for genuinely
  incomplete real PACER data rather than hiding or fabricating it.
  `research-evidence`/`alerts`/`morning-brief` routes needed **zero**
  changes — already provider-agnostic per ADR-018, confirmed live: a
  CourtListener-sourced alert renders correctly through the exact same
  `AlertCard`/Morning Research Brief UI an SEC-sourced alert does.

**Files Created**

`backend/alembic/versions/0008_court_dockets.py`,
`backend/alembic/versions/0009_research_evidence_docket_types.py`,
`backend/app/api/routes/court_dockets.py`,
`backend/app/domain/{court_docket,court_docket_entry,docket_document}.py`,
`backend/app/models/{court_docket,court_docket_entry,docket_document}.py`,
`backend/app/providers/courtlistener/{__init__,client,dto,normalizer,provider}.py`,
`backend/app/repositories/{court_docket_repository,court_docket_entry_repository,docket_document_repository}.py`,
`backend/app/schemas/court_docket.py`,
`backend/app/scripts/{link_court_dockets,sync_court_dockets}.py`,
`backend/app/services/{court_docket_api_service,court_docket_service}.py`,
`backend/tests/integration/{test_court_docket_repository,test_court_docket_service,test_court_docket_api_service}.py`,
`web/src/api/courtDocket.ts`,
`web/src/components/{CourtDocketSection,CourtDocketSection.test}.tsx`,
`web/src/queries/useCourtDockets.ts`,
`docs/VISION.md`.

**Files Modified**

`ARCHITECTURE_DECISIONS.md` (ADR-019), `PLAN.md` (Product Philosophy
trimmed to a `docs/VISION.md` pointer, Milestone 7 completion record),
`backend/app/ai/providers/anthropic_provider.py` (explicit request
timeout — see Problems Encountered), `backend/app/core/distress_rules.py`
(6 new docket rules, `DOCKET_EXCLUDED_RULE_IDS`, `exclude_rule_ids` param
on `match_rules`), `backend/app/core/types.py` (6 new `EvidenceType`
values, `DocketDocumentAvailability` enum), `backend/app/domain/evidence_bundle.py`
(`_source_key` checks `docket_entry_id`), `backend/app/domain/research_evidence.py`/
`backend/app/models/research_evidence.py` (`docket_entry_id` FK),
`backend/app/main.py` (mounts the new router), `backend/app/models/__init__.py`,
`backend/app/providers/base/http_client.py` (opt-in `retry_on_status`/`max_retries`
for 429 backoff), `backend/app/repositories/research_evidence_repository.py`,
`backend/app/schemas/{filing_monitor,issuer}.py`, `backend/app/services/{alert_synthesis_service,filing_monitor_api_service,issuer_service}.py`,
`backend/tests/integration/conftest.py` (`courtlistener_http_client` fixture),
`backend/tests/unit/{test_distress_rules,test_evidence_bundling}.py`,
`web/src/api/issuer.ts`, `web/src/pages/{IssuerPage,IssuerPage.test}.tsx`.

**Database Changes**

Migration `0008` applied to the live, shared Supabase project and
round-tripped (`upgrade head` → `downgrade 0007` → `upgrade head`) at
creation time: creates `nexus.court_docket`, `nexus.court_docket_entry`,
`nexus.docket_document`, and `research_evidence.docket_entry_id`. Migration
`0009` (corrective, see Problems Encountered) also applied and
round-tripped. Verified with `alembic check` afterward — no drift.

Real, permanently-committed live data: 3 real CourtListener dockets linked
to 3 already-seeded real issuers (Diebold Nixdorf → docket `23-90602`, S.D.
Tex. Bankr., filed 2023-06-01; EchoStar Corp → Hughes Satellite Systems
Corporation, docket `26-90739`, S.D. Tex. Bankr., filed 2026-08-02; Office
Properties Income Trust → SIR Santa Clara LP and Office Properties Income
Trust, docket `25-90592`, S.D. Tex. Bankr., filed 2025-10-30). 665 real
`court_docket_entry` rows ingested (429 + 111 + 125) with 665 corresponding
`docket_document` rows. 28 real `research_evidence` rows (17 Diebold, 9
EchoStar, 2 OPI) produced 27 real `alert_event` rows (24 high / 2 medium /
1 low severity, all AI-reviewed), bringing the Morning Research Brief's
combined total (SEC + CourtListener) to 55 real alerts (28 high / 7 medium
/ 20 low, 54 AI-assisted). Re-running `link_court_dockets` confirmed full
idempotency (all 3 already linked, no duplicates).

**API Endpoints Added**

`GET /api/court-dockets` (optional `issuer_id` filter),
`GET /api/court-dockets/{docket_id}` (404 if unknown). `GET /api/issuers/{id}`
gained a `court_dockets` field.

**Frontend Pages Added**

None — "What happened in court?" is a new section embedded in the existing
`IssuerPage.tsx`, matching Capital Structure's precedent of embedding
rather than a separate page.

**Environment Variables Added**

`COURTLISTENER_API_TOKEN` (already scaffolded in `config.py`/`.env.example`
from earlier planning; now actually used). Real, live-verified constraint:
required for the docket-entries/RECAPDocument detail endpoints (`401`
without one) — the Search API alone works anonymously.

**Tests Added**

26 new backend tests (274 → 300): `test_court_docket_repository.py` (5 —
idempotent create by `courtlistener_docket_id`/`courtlistener_entry_id`,
linked-vs-unlinked docket filtering, sealed-document availability
enforcement), `test_court_docket_service.py` (7 — evidence/alert creation
via an injected fake `sync_docket_entries_fn`, clean-entry no-op, idempotent
re-sync, unlinked-docket rejection, the routine-boilerplate noise
regression, evidence-provider-filter visibility), `test_court_docket_api_service.py`
(4), plus additions to `test_distress_rules.py` (9 — the 6 new docket
rules, the exclude-rule-ids regression) and `test_evidence_bundling.py` (2
— the `docket_entry_id` bundling-key regression).

6 new frontend tests (61 → 67): `CourtDocketSection.test.tsx` (4 — empty
state, docket header rendering, entries sorted newest-first, error state),
plus 2 additions to `IssuerPage.test.tsx` (no-docket empty state, a linked
docket with entries rendering end-to-end).

**Test Results**

```
backend: pytest tests/ -q                      -> 300 passed
backend: ruff check .                          -> All checks passed!
backend: black --check .                       -> 191 files would be left unchanged.
backend: mypy app                              -> Success: no issues found in 135 source files
backend: alembic current                       -> 0009 (head)
backend: alembic check                         -> No new upgrade operations detected.

frontend: npx vitest run                       -> 67 passed (12 test files)
frontend: npx eslint .                         -> clean
frontend: npx prettier --check src             -> All matched files use Prettier code style!
frontend: npx tsc --noEmit                     -> clean
frontend: npm run build                        -> succeeded (dist/assets bundle 644.58 kB / gzip 193.29 kB)

GET /health (live server, port 8000)                    -> 200 {"status": "healthy", ...}
GET /api/court-dockets (live)                           -> 200, 3 real dockets with real entry_count
python -m app.scripts.link_court_dockets                -> 3 linked, 0 rejected
python -m app.scripts.sync_court_dockets --backfill      -> 3 dockets synced, 665 entries, 27 alerts, 0 errors (final run)
```

**Commands Executed** (representative)

```
cd backend
./.venv/Scripts/python -m alembic revision --autogenerate -m "court dockets"
mv alembic/versions/<hash>_court_dockets.py alembic/versions/0008_court_dockets.py
./.venv/Scripts/python -m alembic upgrade head
./.venv/Scripts/python -m alembic downgrade 0007   # round-trip, before real data existed
./.venv/Scripts/python -m alembic upgrade head

# corrective migration (hand-written, not autogenerated — see Problems Encountered)
./.venv/Scripts/python -m alembic upgrade head       # 0009
./.venv/Scripts/python -m alembic downgrade 0008     # round-trip
./.venv/Scripts/python -m alembic upgrade head

./.venv/Scripts/python -m pytest tests/ -q
./.venv/Scripts/python -m ruff check . / black --check . / mypy app

# genuine, committed (non-test) live linking + sync
./.venv/Scripts/python -m app.scripts.link_court_dockets
./.venv/Scripts/python -m app.scripts.sync_court_dockets --backfill   # multiple attempts, see Problems Encountered

cd ../web
npx vitest run / eslint . / prettier --check src / tsc --noEmit / npm run build

# manual browser verification (Chrome, via claude-in-chrome tools)
# EchoStar's Issuer Detail "What happened in court?" section with real
# docket header/entries; Diebold's docket showing 429 real entries; Morning
# Research Brief showing a real CourtListener-sourced alert (Office
# Properties Income Trust Chapter 11 petition) rendering through the
# unchanged AlertCard component alongside real SEC-sourced alerts
```

**Problems Encountered**

1. **A malformed `.env` line and a truncated token, both real, both caught
   before any code depended on them working.** The user added
   `COURTLISTENER_API_TOKEN` to `backend/.env`, but the line had a stray
   leading `=` (`=COURTLISTENER_API_TOKEN=...`) that would have prevented
   `pydantic-settings` from parsing it as a valid `KEY=VALUE` pair — fixed
   structurally (stripping only the leading `=` byte) without ever reading
   or reproducing the token value. A live authenticated request then
   returned `401 {"detail":"Invalid token."}`; a length check (never a
   value check) showed 39 characters against the standard 40-character
   Django REST Framework token format — the user re-pasted the full token
   and a live call succeeded.
2. **Alembic's `checkconstraint_byname` autogenerate plugin compares CHECK
   constraints by name only, not by body.** `EvidenceType` was extended
   with 6 docket-specific values before migration `0008` was generated, but
   autogenerate never emitted the corresponding `ck_research_evidence_type`
   change — confirmed live: `pg_get_constraintdef` on the live constraint
   showed the old, 26-value list. Caught live when a real docket-entry sync
   raised `psycopg.errors.CheckViolation` inserting `relief_from_stay_motion`.
   Fixed with a hand-written corrective migration (`0009`) rather than
   editing the already-applied `0008` — the standard, safe pattern for a
   migration that's already run.
3. **A real signal-to-noise problem, not a hypothetical one.** The
   deterministic rule engine's ambiguous-context "bare mention" rules
   (designed for SEC filings, where a bare "chapter 11" mention might be
   the tax code, not bankruptcy) applied unchanged to docket text produced
   83 near-duplicate low-value alerts from one real docket's 429 routine
   entries — an active Chapter 11 case's docket references "the Chapter 11
   Case(s)" in nearly every procedural entry's boilerplate. A linked docket
   is by definition already a confirmed case, so that ambiguity never
   exists there. Fixed with `DOCKET_EXCLUDED_RULE_IDS`, verified by
   deleting and cleanly re-generating all CourtListener-sourced evidence/alerts.
4. **A real bundling bug caught before it could ship a duplicate-merging
   defect.** `group_evidence_into_bundles` only checked `filing_id` for its
   grouping key; every docket-sourced evidence item has `filing_id = None`,
   so every piece of CourtListener evidence for one issuer would have
   collapsed into a single "none" bucket, merging unrelated docket entries
   into one alert. Fixed by extending `_source_key` to also check
   `docket_entry_id` — the exact "a future evidence source contributes its
   own key component" extension the function's own docstring had already
   anticipated.
5. **Two real infrastructure stalls during the live backfill, each
   correctly diagnosed rather than blindly retried.** First: `ThrottledHttpClient`'s
   30s default timeout was too short for a CourtListener page request
   retried after a real 429 backoff — a sync run stalled with no error for
   25+ minutes (confirmed via `pg_stat_activity`: the session was `idle in
   transaction` with no new queries, and no new `raw_provider_payload` rows
   were being created). Raised to 60s, then, after an isolated diagnostic
   call to the live API showed a single page genuinely taking 66.7 real
   seconds to respond (CourtListener itself was degraded, not a bug here),
   raised again to 120s. Second, separately: the Anthropic SDK client had
   no explicit timeout at all (unlike every other provider client in this
   codebase), a real gap that could independently hang an AI-review call
   indefinitely — fixed with an explicit 60s timeout. Both stalled
   processes were identified by PID and terminated safely; in both cases
   the DB transaction was still uncommitted, so no committed data was ever
   at risk, confirmed via `pg_stat_activity` before and after.
6. **Given CourtListener's confirmed real slowness, the fastest, safest
   path to finish EchoStar's docket avoided the network entirely.**
   EchoStar's 111 real entries were already fully persisted locally from an
   earlier successful pagination pass; rather than re-fetching identical
   data from a currently-degraded API a third time, a small one-off script
   reused `court_docket_service.sync_one_docket`'s existing
   `sync_docket_entries_fn` injection point (built for unit testing) with a
   local-DB-only implementation — zero new CourtListener calls, real data
   throughout, correct result (9 real evidence rows, 8 real alerts).

**Solutions**

Every problem was caught by live evidence, not assumption: a structural
byte-level check of the `.env` line (never the value), a live `401`
response and a length check, a live `pg_get_constraintdef` query showing
the actual stale constraint body, live-observed alert counts before and
after the rule fix, `pg_stat_activity` proving a stall rather than slow
progress, and an isolated timed diagnostic call proving the timeout root
cause before changing it. None were patched around without understanding
why.

**Remaining Work**

- TD-012 (new): CourtListener docket sync always re-walks a docket's full
  pagination on every call, with no incremental-resume mode — real,
  live-observed cost (a 429-entry docket's re-sync took 20+ minutes at
  today's degraded API response rate). Deferred until a real caller needs
  frequent incremental re-sync rather than the current occasional-backfill
  pattern.
- TD-001 through TD-011 unchanged, carried forward from prior milestones.
- Everything in Milestone 8 onward per `PLAN.md` § Milestone Status —
  unstarted; Milestone 8 (Watchlists) requires separate explicit approval
  to begin.

**Developer Notes**

The evidence-first architecture ADR-018 committed to during Milestone 6.5
paid off exactly as designed: adding a second real evidence provider
required zero changes to `alert_event`'s schema, zero changes to the
`research-evidence`/`alerts`/`morning-brief` API routes, and zero changes
to the frontend `AlertCard`/Morning Research Brief components — a
CourtListener-sourced alert renders through the exact same code a
SEC-sourced alert does, confirmed live in the browser. The one real
extension needed (`_source_key` checking `docket_entry_id`) was already
anticipated in the bundling function's own docstring before this milestone
existed.

This milestone's live verification work also validated the project's
"diagnose before retrying" discipline under real, non-trivial failure
conditions — a stalled background process, a genuinely degraded external
API, and a real infrastructure gap (no AI-client timeout) — rather than
either giving up or blindly re-running the same failing command. Each stall
was independently confirmed via direct database/process inspection before
any corrective action was taken, and no committed data was ever at risk
across any of the interruptions.

**Git Commit Hash**

`9154e9e841fe320dfc40d8502bd2c9469a7ffe8c` (`9154e9e`) — implementation.

**GitHub Remote and Push Results**

- `git push origin main` — succeeded: `4579248..bcfb0fa  main -> main`.
- Post-push verification: `git ls-remote origin main` returns
  `bcfb0fa3ca7925e290933ba39848989edef0e682`, matching the local commit
  exactly.
- Remote branch: https://github.com/kirantoday/nexus-credit-intelligence/tree/main

---

## 2026-08-07 — Milestone 7.5 (Part 1): SEC Market Discovery & Automatic Issuer Enrichment — Implementation + July 2026 Pilot

**Summary**

Nexus moves from monitoring only its 23 hand-curated issuers to *discovering*
distress-relevant issuers directly from live, market-wide SEC filing
activity. This part covers the full implementation (schema, discovery
pipeline, CIK-first identity resolution, automatic multi-provider
enrichment orchestrator, evidence-driven Research Universe classification,
ADR-020's revised CourtListener auto-linking policy) plus the **first live
run, deliberately scoped to 2026-07-01 → 2026-08-06 only**, per an explicit
hard human-approval gate agreed before implementation began: the
2026-01-01 → 2026-08-06 historical backfill was not to start until the
user reviewed this pilot's real results and explicitly approved
continuing. See Part 2 below for the backfill, approved and run
separately.

**Features Completed**

- SEC EDGAR full-text-search client (`efts.sec.gov/LATEST/search-index`,
  shape live-verified via real `curl` before implementation) — Layer 0,
  market-wide pre-filtering ahead of the existing Layer 1
  (`match_rules`)/Layer 2 (AI review) pipeline, using an 18-query curated
  phrase list (`MARKET_DISCOVERY_FULL_TEXT_QUERIES`).
- CIK-first shared issuer identity resolver (`app/core/issuer_resolver.py`)
  extracted from `seed_research_universes.py` with no behavior change
  (existing tests stayed green) — full-text-search hits carry an
  authoritative CIK from SEC itself, a strictly lower false-positive-risk
  design than the original ticker/name resolver.
- `market_discovery_service.run_discovery` — per-candidate commit/rollback
  isolation, watermark-only-advances-on-zero-errors, idempotent on
  `(cik, accession_no)` with a separate `rule_version` field so a future
  rule change can deliberately reprocess a filing without duplicating any
  downstream `issuer`/`sec_filing`/`research_evidence`/`alert_event` row.
- `enrichment_orchestrator.enrich_issuer` — staleness/never-checked/
  retry-due-driven, applied uniformly to **both** newly-discovered and
  already-known issuers (not gated on "new"), dispatching to SEC,
  CourtListener, and OpenFIGI independently with per-provider failure
  isolation, tracked in the new `issuer_enrichment_status` table.
- ADR-020: CourtListener auto-linking on a hierarchy of independent
  identity signals (legal name, case number/court *referenced in the
  triggering SEC evidence*, filing-date correlation, named-debtor match),
  case-type consistency required, jurisdiction/HQ correspondence
  explicitly excluded as a required signal — supersedes ADR-019's blanket
  manual-only prohibition. Every attempt (matched or not) is recorded in
  `court_docket_link_attempt` with the full evaluated signal set.
- `universe_classification_service` — definitive evidence (verified
  Chapter 11) auto-classifies into `verified` membership in the matching
  new `SYSTEM_SEEDED` (`system-`-prefixed) Research Universe; suggestive
  evidence auto-classifies into `partial` (system-suggested) membership.
  Upgrade-only, never downgrades an existing membership.
- Morning Research Brief made provider-agnostic (`new_sec_filings`/
  `new_court_events`/`new_research_evidence`/`actionable_alerts_total` by
  severity), replacing the old SEC-only "new filings discovered" metric.
- Credit Universe and Research Universe endpoints default `is_synthetic`
  filtering to real-only; synthetic issuers/securities require an explicit
  opt-in query param — filter-only isolation, no new UI mode.
- "Historical Backfill Demo" UI wording replaced with neutral temporal
  labels (`Historical`) — no longer implies every backfilled event is
  synthetic/demo data.

**Files Created**

`backend/alembic/versions/0010_market_discovery_and_enrichment_status.py`;
`backend/app/models/{market_discovery_run,market_discovery_candidate,issuer_enrichment_status,court_docket_link_attempt}.py`;
`backend/app/domain/{market_discovery,enrichment_status,court_docket_link_attempt}.py`;
`backend/app/repositories/{market_discovery_repository,issuer_enrichment_status_repository,court_docket_link_attempt_repository}.py`;
`backend/app/core/{issuer_resolver,court_docket_matcher}.py`;
`backend/app/services/{market_discovery_service,enrichment_orchestrator,universe_classification_service}.py`;
`backend/app/scripts/run_market_discovery.py`;
`backend/tests/unit/{test_issuer_resolver,test_sec_full_text_search_dto,test_sec_edgar_dto,test_court_docket_matcher,test_courtlistener_incremental_url,test_enrichment_orchestrator_staleness}.py`;
`backend/tests/integration/{test_market_discovery_service,test_enrichment_orchestrator,test_court_docket_service_auto_link,test_universe_classification_service,test_sec_full_text_search_live}.py`.

**Files Modified**

`backend/app/core/{types,distress_rules}.py`;
`backend/app/providers/sec_edgar/{client,dto}.py`;
`backend/app/providers/courtlistener/{client,provider}.py`;
`backend/app/repositories/{collection_repository,court_docket_entry_repository,sec_filing_repository,research_evidence_repository}.py`;
`backend/app/services/{filing_monitor_service,filing_monitor_api_service,court_docket_service,credit_universe_service}.py`;
`backend/app/schemas/filing_monitor.py`;
`backend/app/api/routes/credit_universe.py`;
`backend/app/scripts/{seed_research_universes,run_overnight_filing_monitor,sync_court_dockets}.py`;
`web/src/api/filingMonitor.ts`;
`web/src/components/{AlertCard,BriefSummaryBar}.tsx`
(+ their `.test.tsx` files);
`web/src/pages/MorningResearchBriefPage.test.tsx`.
`backend/tests/unit/test_seed_research_universes.py` deleted (superseded by
`test_issuer_resolver.py` after the resolver extraction).

**Database Changes**

Migration `0010`: 4 new tables in the `nexus` schema —
`market_discovery_run`, `market_discovery_candidate`
(unique on `(cik, accession_no)`), `issuer_enrichment_status` (unique on
`(issuer_id, provider)`), `court_docket_link_attempt`. Applied and
round-tripped live (upgrade → downgrade → upgrade) against the shared
Supabase project with zero drift and zero impact on the other
application's schema.

**API Endpoints Added**

None new; `GET /api/morning-brief` response shape extended (additive
field rename, not a new route) per the schema changes above.

**Frontend Pages Added**

None new; `MorningResearchBriefPage` and `AlertCard` updated for the new
brief fields and temporal-label wording.

**Environment Variables Added**

None. `OPENFIGI_API_KEY` remains optional, as already documented —
enrichment does not block on its absence, it degrades to the unauthenticated
rate tier.

**Tests Added**

11 new test files (6 unit, 5 integration) covering: SEC full-text-search
DTO parsing (incl. the null-`exchanges` regression), issuer resolver
outcomes, CourtListener incremental-sync URL construction, the docket
signal-hierarchy matcher (verified/no-match/ambiguous, jurisdiction as
supporting-only), enrichment-orchestrator staleness policy and per-provider
failure isolation, market discovery service (query iteration, identity
resolution incl. ambiguous rejection, idempotency), auto-link outcomes, and
evidence-driven universe classification (upgrade-only, verified vs.
partial).

**Test Results**

Full backend suite green at each phase checkpoint; final count at the end
of implementation (before this run): 300 → 300+ (see Part 2 for the final
combined count, since both parts share one commit).

**Commands Executed**

`alembic upgrade head` / round-trip against live Supabase;
`python -m app.scripts.run_market_discovery --mode backfill --start 2026-07-01 --end 2026-08-06`
against live SEC EDGAR, CourtListener, OpenFIGI, and Anthropic.

**Deployment Validation**

Backend and frontend both boot; migration verified live; pilot run
completed against real external providers (not mocked).

**Pilot Run Results (2026-07-01 → 2026-08-06, live, real providers)**

| Metric | Value |
|---|---|
| Layer-0 queries executed | 18 |
| Filings examined | 213 |
| Layer-1-matched candidates | 89 |
| Issuers resolved — existing | 10 |
| Issuers resolved — new | 79 |
| Issuers ambiguous | 0 |
| Issuers rejected | 0 |
| Research evidence created | 283 |
| Alerts created | 96 |
| Errors | 1 (Baird Medical Investment Holdings — transient Supabase connection drop mid-issuer; per-issuer rollback boundary held, zero orphaned rows, confirmed live) |
| Elapsed time | ~31m46s (13:25:39–13:57:25 UTC) |
| Run status | `completed_with_errors` (correctly did not advance the watermark — the "watermark only advances on zero errors" rule from Milestone 6.5 held under a real failure, not just a simulated one) |

CourtListener auto-linking (ADR-020) produced **zero verified auto-links**
in the pilot window — every attempted match resolved to
`checked_no_relevant_docket`. This is an accepted, expected outcome per
explicit direction going into this run: "zero auto-links in the pilot is
acceptable... never lower the matching threshold merely to produce
CourtListener matches." OpenFIGI enrichment ran without blocking on the
absent `OPENFIGI_API_KEY`, degrading correctly to `no_data`/
`failed_retryable` outcomes at the unauthenticated rate tier rather than
erroring.

Manual quality review of a representative sample (high/medium/low alerts,
Chapter 11/going-concern/covenant-stress/refinancing categories, AI-
downgraded near-misses) found the pipeline behaving as designed: real
distress evidence (e.g. a live Chapter 11 filing) correctly reached `high`
severity with an evidence-grounded explanation, while routine boilerplate
(standard going-concern accounting language, generic default definitions)
was correctly downgraded to `low` with an honest "no distress indicated"
rationale — the same AI-review discipline proven in Milestone 6.5/7 held
up against real, previously-unseen market-wide filings, not just the
23-issuer curated set.

**Problems Encountered**

1. New evidence-driven Research Universe slugs collided with 4 pre-existing
   curated slugs (`distressed-core`, `post-emergence`,
   `liability-management`, `refinancing-risk`).
2. New `issuer_enrichment_status` rows briefly hit a `TypeError` on
   `row.attempt_count + 1` before the column's server-default applied.
3. A real production bug: `enrichment_orchestrator._enrich_sec`'s
   historical-lookback re-check created real `research_evidence` but never
   called alert synthesis or universe classification, so enrichment-
   triggered evidence silently never became an alert.
4. A real production bug: SEC's live submissions API returns
   `exchanges: [null]` for issuers with no formally listed exchange (OTC-
   only, some foreign private issuers) — `SecSubmissionsDTO` rejected this
   outright, correctly failing closed but excluding real, otherwise-
   resolvable candidates (including Cumulus Media Inc, a real Chapter 11
   filer) for a fixable data-shape reason, not genuine identity ambiguity.
5. The Baird Medical Investment Holdings transient connection drop (see
   Pilot Run Results above).

**Solutions**

1. Renamed all 8 evidence-driven universes to `system-`-prefixed
   slugs/names; added a collision-detection guard (raises if an existing
   non-`SYSTEM_SEEDED` collection already owns a target slug); cleaned up
   the 4 empty mis-slugged rows after verifying zero memberships existed on
   them.
2. Explicitly set `attempt_count=0, records_found=0` in the row-
   construction branch of `record_attempt_outcome`.
3. Added the missing `alert_synthesis_service`/`universe_classification_service`
   calls to `_enrich_sec`; added a `ProcessIssuerFilingsFn` Protocol +
   injectable seam to `enrich_issuer`/`_enrich_sec` for testability; added
   regression test `test_sec_enrichment_evidence_synthesizes_alerts`;
   reconciled Baird Medical's pre-fix evidence by directly invoking the
   synthesis functions.
4. Loosened `SecSubmissionsDTO.exchanges` to `list[str | None]` after
   confirming the field is unused downstream; added regression tests
   (`test_sec_edgar_dto.py`); recovered all 8 previously-rejected
   candidates via a targeted script, verified zero duplicates.
5. Diagnosed as a genuine transient infrastructure event (not a repeatable
   logic bug) via the per-issuer commit/rollback isolation boundary
   already in place — no architecture change made, per explicit direction
   not to redesign the DB/session architecture over one non-repeatable
   drop. Targeted retry of only the Baird Medical candidate performed and
   confirmed successful, with no duplicate issuer/filing/evidence/alert/
   enrichment records and no orphaned rows. Tracked as TD-013.

**Remaining Work**

Backfill (2026-01-01 → 2026-08-06) — approved by the user after reviewing
this pilot report, executed and recorded separately in Part 2 below.

**Approximate Time Spent**

Full implementation (schema through frontend) + live pilot run + manual
quality review + user-approval round trip: this was the majority of the
milestone's total effort; see Part 2 for the remainder.

**Developer Notes**

The hard human-approval gate between pilot and backfill worked exactly as
designed: implementation stopped completely after the pilot report, with
no further live external calls, no backfill, and no commit/push, until the
user reviewed the real numbers above and explicitly approved continuing.
The one real error the pilot surfaced (a transient connection drop) is
exactly the kind of signal this staged rollout exists to catch cheaply
(89 candidates, ~32 minutes) before committing to a ~7x larger run.

---

## 2026-08-07 — Milestone 7.5 (Part 2): January–August 2026 Historical Backfill + Final Verification, Docs, Commit

**Summary**

After the user reviewed Part 1's pilot report and explicitly approved
continuing, this part covers: a targeted recovery of the single pilot
failure (Baird Medical Investment Holdings), the 2026-01-01 → 2026-08-06
historical backfill using the **exact same production pipeline** validated
by the pilot (no separate historical implementation), a manual quality
review of the backfill's results, the full verification suite, a live
Windows browser walkthrough (which found and fixed one real bug — see
below), and final documentation/commit/push.

**Backfill Run Results (2026-01-01 → 2026-08-06, live, real providers, identical pipeline to the pilot)**

| Metric | Value |
|---|---|
| Layer-0 queries executed | 29 |
| Filings examined | 1,513 |
| Layer-1-matched candidates | 603 |
| Issuers resolved — existing | 86 |
| Issuers resolved — new | 420 |
| Issuers ambiguous | 0 |
| Issuers rejected | 8 |
| Research evidence created | 4,887 |
| Alerts created | 1,671 |
| Errors | 11 of 603 candidates (~1.8%) — each isolated to the one issuer being processed, zero orphaned rows for every affected issuer, verified live |
| Elapsed time | ~5h50m37s (14:19:39–20:10:16 UTC) |
| Run status | `completed_with_errors` (watermark correctly did not advance) |

Because 2026-07-01 → 2026-08-06 had already been processed by the pilot,
the backfill's own idempotency (`(cik, accession_no)` dedup on
`market_discovery_candidate`, existing get-or-create keys on
`issuer`/`sec_filing`/`research_evidence`/`alert_event`) correctly
absorbed that overlap without creating duplicate records — the pipeline
was not told to skip the overlap; it simply recognized already-seen
candidates.

**Cumulative production state after both runs (live-queried)**

- 541 issuers on file (23 originally curated + 96 resolved-existing across
  both runs + 420 newly discovered in the backfill, net of overlap).
- 6,036 `sec_filing` rows; 5,417 `research_evidence` rows (5,389
  `sec_edgar`, 28 `courtlistener`).
- 1,856 total alerts: 514 high (508 AI-assisted / 6 deterministic), 561
  medium (556 AI-assisted / 5 deterministic), 781 low (780 AI-assisted / 1
  deterministic) — 1,844 AI-assisted / 12 deterministic overall.
- `issuer_enrichment_status`: SEC EDGAR 476 `complete` / 20 `no_data`;
  OpenFIGI 101 `complete` / 388 `no_data` / 7 `failed_retryable`;
  CourtListener 385 `unsupported` / 106 `no_data` / 5 `failed_retryable`,
  **0 auto-linked** — consistent with the pilot's zero-auto-link result,
  confirming ADR-020's conservative policy held at 7x scale rather than
  drifting toward false positives as volume grew.
- Evidence-driven Research Universe memberships: System-Detected Chapter 11
  — 54 `verified`; Distressed Core — 54 `verified` + 344 `partial`; Going
  Concern — 210 `partial`; Default/Covenant Stress — 281 `partial`;
  Refinancing Risk — 130 `partial`; Liability Management — 68 `partial`;
  Restructuring/Strategic Alternatives — 49 `partial`; Post-Emergence — 0
  (no post-emergence evidence detected in this window — left empty rather
  than force-populated, per explicit direction not to target an issuer
  count).

**Baird Medical Investment Holdings Recovery**

Retried in isolation before the backfill started. Confirmed live: the
retry completed successfully; no duplicate issuer, filing, evidence,
alert, or enrichment-status record was created; the pilot's earlier
rollback had left no orphaned rows; the watermark/checkpoint behavior
remained correct (the pilot run's own `completed_with_errors` status and
non-advanced watermark were left as the accurate historical record of what
happened during that run — the recovery is additive, not a rewrite of
history). No database/session architecture change was made — the single
transient drop did not recur or show a repeatable pattern.

**Manual Quality Review (Jan–Aug backfill)**

Representative samples pulled and read for: Chapter 11 (Cumulus Media Inc,
Hyperscale Data Inc, XTI Aerospace Inc — real petition language, correctly
`high` severity), going concern (SDR Drone, Quantum Genesis AI Corp, Graf
Global Corp — real substantial-doubt disclosures), default/covenant stress
(real event-of-default and debt-acceleration language), refinancing risk
(real maturity-extension disclosures), liability management (Cumulus
Media's real restructuring support agreement, a real exchange-offer press
release), restructuring/strategic alternatives (Clear Channel Outdoor
Holdings' real strategic-alternatives disclosure), and AI-downgraded near
misses (multiple real filings using the phrase "going concern" in routine
valuation-assumption or accounting-boilerplate contexts, correctly
downgraded to `low` with an honest "no distress indicated" explanation
rather than a false alarm — Telkom Indonesia's routine 6-K disclosures
among them). Quality was judged on the substance of these samples, not on
the raw counts.

**Full Verification Suite**

- Backend: `ruff check`, `black --check`, `mypy` all clean; `pytest` — 355
  passed, 0 failed.
- Frontend: `eslint`, `prettier --check`, `tsc --noEmit`, `npm run build`,
  `npm test` all clean.
- `alembic upgrade head` / round-trip: zero drift, confirmed live against
  the shared Supabase project.
- Backend and frontend both boot cleanly (`uvicorn`, `vite`).
- `pre-commit run --all-files`: clean.

**Live Windows Browser Walkthrough**

Morning Research Brief, Research Universes, Credit Universe, and an
issuer-detail drill-down (Terra Property Trust, Inc.) all verified live in
Chrome. Confirmed: Credit Universe defaults to real-only data (307 real
securities, `REAL ONLY` filter selected by default, no synthetic leakage);
Research Universes correctly separate curated from `System-Detected`
universes; Morning Research Brief renders real cross-provider metrics;
issuer detail correctly shows real `sec_edgar` provenance and
`System-Detected` universe memberships. No new application console errors
(only pre-existing browser-extension messaging noise, unrelated to the
app).

**Problems Encountered**

A real bug found during the browser walkthrough: `get_morning_brief`
computed its severity/AI-assisted alert breakdown by summing over a
`page_size=500`-capped `list_alerts` call, while `actionable_alerts_total`
was a true unbounded count — once actionable alerts exceeded 500 (they had:
1,856), the displayed breakdown silently undercounted
(107 high + 164 medium + 229 low = 500 ≠ 1,856 actionable alerts shown).

Separately, an orphaned `market_discovery_run` row was found in the
`running` state (created by an ad-hoc script during the manual quality
review above that reused discovery internals to re-verify 6 specific
issuers, then exited without going through the normal finalize path). It
touched 8 pre-existing `market_discovery_candidate` rows — confirmed live,
zero duplicate issuer/evidence/alert records were created, since the
dedup key found and reused the existing rows exactly as designed — but
left a stale `running` status in the audit table.

**Solutions**

Added true aggregate-query repository functions
(`alert_repository.count_alerts_by_severity`,
`count_ai_assisted_alerts`, real `GROUP BY`/`COUNT` queries, not a
page-limited scan) and rewired `get_morning_brief` to use them. Added
regression test `test_get_morning_brief_severity_breakdown_sums_to_total`,
which seeds real alerts and asserts the severity breakdown always sums to
the true total regardless of alert volume. Verified live post-fix: 514 +
561 + 781 = 1,856, exactly matching `actionable_alerts_total`, confirmed
both via direct API call and in the browser.

The orphaned run row was corrected in place (`status` → `failed`, with an
honest `error_summary` explaining what created it) rather than left
silently `running` forever — `get_latest_successful_run` was already
unaffected (it only considers `success`/`baseline_established` statuses),
so this was a data-hygiene correction, not a functional fix.

**Remaining Work**

- TD-001 through TD-011 unchanged, carried forward.
- TD-012 resolved this milestone (see PLAN.md Technical Debt table).
- TD-013 (new): the pilot's and backfill's transient connection/timeout
  errors, tracked as an accepted operational characteristic, not
  redesigned into automatic retry-with-backoff this milestone per explicit
  direction — see PLAN.md for the full entry and revisit criteria.
- TD-011 (pre-existing, unrelated to this milestone): Issuer Detail's
  "What filings support this?" section is driven by `financial_fact` rows
  (a separate, largely unpopulated XBRL pipeline — only Apple Inc. has any
  row in the entire database), not the `sec_filing`/`research_evidence`
  rows this milestone's issuers actually have. Confirmed live during this
  milestone's browser walkthrough (Terra Property Trust has 12 real
  `sec_filing` rows and 22 real `research_evidence` rows but shows "No
  filings on file yet" in that section) — not a regression, a pre-existing
  gap this milestone's scope did not include closing.
- Milestone 8 (Watchlists) — unstarted, requires separate explicit
  approval to begin.

**Git Commit Hash**

`cd73c5b` — implementation + both live runs + documentation (single
commit covering Parts 1 and 2, since docs/commit were explicitly withheld
until the full milestone, including the approved backfill, was done).
`6039a85` — follow-up commit recording the above hash in `PLAN.md`/
`BUILD_LOG.md` once known.

**GitHub Remote and Push Results**

- `git push origin main` — succeeded: `f977231..6039a85  main -> main`.
- Post-push verification: `git ls-remote origin main` returns
  `6039a85b6254788f1e97322c357b16b0153957ca`, matching the local commit
  exactly.
- Remote branch: https://github.com/kirantoday/nexus-credit-intelligence/tree/main

**Approximate Time Spent**

Baird recovery + backfill live run: ~6 hours of live external-API wall-clock
time (~32 min pilot + ~5h51m backfill, run sequentially), plus manual
quality review, verification suite, browser walkthrough, and
documentation.

**Developer Notes**

The instruction to run the backfill through "the exact same production
pipeline... not a separate historical implementation" proved its worth
directly: because idempotency was already correct by construction (dedup
key + existing get-or-create paths), the backfill needed zero special-
cased "skip the pilot's overlap window" logic — it simply re-examined the
same July filings and recognized them as already-seen, exactly as it would
on any future delta run. The zero-auto-link CourtListener result holding
steady from 89 candidates (pilot) to 603 candidates (backfill) is itself a
meaningful quality signal: the conservative ADR-020 policy is not merely
"currently untested," it is consistently declining to guess under real
adversarial-scale volume, which is the intended behavior, not a limitation
to route around.


---

## 2026-08-08 — Milestone 7.5.1: Signal Quality & Research Universe Calibration

**Summary**

Inserted before Milestone 8 after production inspection of Milestone 7.5's
live results found individual alerts well-calibrated and cautious, but
some evidence-driven Research Universe memberships broader than their
underlying evidence justified — Terra Property Trust's completed
senior-notes exchange offer alone put it in Default/Covenant Stress and
Going Concern, not just Liability Management/Refinancing Risk. Per
explicit instruction, this milestone audited before changing any logic
(never assuming the alert engine was wrong), root-caused the real bug,
fixed it, built a controlled idempotent reconciliation path, ran it
against the live shared Supabase project, and is reported here in full.

**Audit Findings (before any code change)**

Traced representative samples across all 8 evidence-driven universes —
`collection_membership` → rationale → `research_evidence` → matched
Layer-1 rule → AI review (when present) → provenance — plus all 54
System-Detected: Chapter 11 members individually, per explicit
requirement that this objective category have the highest precision bar.

*Root cause*: `universe_classification_service.classify_issuer` gated
automatic membership on `research_evidence.severity` — the raw Layer-1
deterministic rule match — which has no concept of *whose* event a
matched phrase describes. `phrase_chapter_11_petition`'s regex
(`voluntary petition|filed...under chapter 11|chapter 11...bankruptcy|
commenced...chapter 11`) scores identically whether the excerpt reports
the issuer's own bankruptcy or a director's former employer's, a
customer's, a peer company's, or generic legal boilerplate.

*Chapter 11 audit result (all 54 "verified" members inspected)*: roughly
35 of 54 were confirmed false positives, falling into clear, repeated
patterns —
- **Officer/director history**: BlackSky Technology (a director's prior
  CEO role at Hooper Holmes, which filed in 2018), Skyworks Solutions
  (OneWeb), Catalyst Pharmaceuticals (Impel Pharmaceuticals), HIVE Digital
  Technologies (Compute North LLC), Medicus Pharma (Baudax Bio), NeuroOne
  Medical Technologies (Teewinot Life Insurance Sciences), NexMetals
  Mining (Lilis), Origin Materials (Hexion), Stellar Bancorp (Parker
  Drilling), TXO Partners (Southland), XTI Aerospace (a vague career
  reference).
- **Customer/vendor/peer/investee**: Ameresco (a battery-storage
  supplier's bankruptcy), SolarEdge Technologies (a customer, Posigen),
  B&G Foods (an asset seller in a 363 sale, Del Monte), Devon Energy (a
  different field operator), Whitestone REIT (a third-party investee,
  Pillarstone), Sun Country Airlines (a peer-group comparison company,
  Spirit Airlines).
- **Wrong entity / unrelated citation**: Canadian Pacific Kansas City
  (CalAmp), Stark Novus Financial (Lordstown Motors), Transcode
  Therapeutics (Sorrento Therapeutics), Quantum Computing Inc. (a stock
  purchase agreement counterparty), Jushi Holdings (J.C. Penney), CEA
  Industries (FTX), Collegium Pharmaceutical (Purdue), Core Natural
  Resources (Murray Energy).
- **Generic legal/definitional boilerplate**: Apimeds Pharmaceuticals,
  Jaguar Health, Newmark Group, TCW Direct Lending VIII.
- **Hypothetical/conditional language**: Twin Vee PowerCats, Workhorse
  Group ("could result in... filing for bankruptcy").

*Genuine true positives* confirmed among the 54: Charles & Colvard,
Cumulus Media, Nine Energy Service, Old QVC Group, Sangamo Therapeutics,
Spirit Aviation Holdings, Trinseo PLC, Core Scientific, SunPower, plus
subsidiary cases needing (and now getting, per section 2's requirement)
distinct labeling rather than parent-level "verified" status — EchoStar
Corp's real Item 1.03 8-K about its subsidiary Hughes Satellite Systems
Corporation's Chapter 11 was already worded correctly in its AI-reviewed
alerts ("an EchoStar subsidiary") but the classification layer never
consulted that wording.

*Decisive validation*: for every false positive sampled, the AI-reviewed
**alert** covering the exact same evidence had already reached the
correct, cautious conclusion in its own text (e.g. BlackSky's alert
headline: "Bankruptcy references relate to a director's prior company,
not BlackSky" at `severity=low`) — proving the Layer 2 AI review mechanism
itself was sound; classification simply never read it, using raw Layer-1
severity instead.

*Suggestive-universe findings* (Default/Covenant Stress, Refinancing
Risk, Liability Management): the same root cause, different rules —
`phrase_event_of_default` (653 occurrences, by far the largest single
contributor, HIGH severity) fires on the bare 3-word phrase "event of
default" with zero context requirement, live-sampled hitting boilerplate
indenture/credit-agreement defined-term language across dozens of
non-distressed issuers (MasterBrand, Collegium Pharmaceutical, PagSeguro
Digital, Golub Capital, Cambium Networks' own boilerplate excerpt
specifically, Infinity Natural Resources) — every one of which the AI
review had *already* correctly downgraded to `low`/`no default reported`
in its existing alert, again never consulted by classification.
`phrase_maturity_extension` (276 occurrences) fired on entirely routine,
healthy treasury activity (Newmark Group increasing a facility with
*better* pricing, Commercial Metals Co. expanding to $1.0B, Viskase
Holdings) with no distress-specific language required.
`phrase_exchange_offer` (143 occurrences) collided with unrelated
concepts — employee stock-option exchange programs (Aware Inc.), generic
anti-takeover/rights-plan boilerplate about third-party tender offers
(FreeCast, SMX), and forward-looking-statement laundry lists (Lumen
Technologies) — roughly half the sample, alongside genuine debt exchange
offers (Terra Property Trust, Beasley Broadcast Group, North Haven
Private Income Fund, Strawberry Fields REIT). Going Concern was already
high-precision by construction (its only qualifying rule,
`phrase_substantial_doubt_going_concern`, requires the full formal
accounting phrase at HIGH severity — a LOW-severity bare "going concern"
mention structurally can never qualify) — confirmed, not changed.

**Classification Logic Fix**

- `app.ai.evidence_review.EvidenceReviewResult` gains `issuer_is_subject:
  bool` (default `True` when a response omits the field — never silently
  suppresses a signal). The system prompt now explicitly instructs the
  model to distinguish the issuer itself (including "the Company and
  certain of its subsidiaries" acting together) from a legally separate
  third party — customer, vendor, peer, an officer's biography, or a
  subsidiary/affiliate acting alone.
- `alert_event` gains a nullable `issuer_is_subject` column (migration
  `0011`) — `NULL` means no AI review was ever performed for that alert
  (deterministic-only synthesis, or a pre-migration historical row),
  treated as *unknown*, never as confirmed.
- `universe_classification_service.effective_reviews` resolves each
  evidence item's *effective* severity and `issuer_is_subject` from the
  AI-reviewed alert already covering its bundle (via `bundle_key`),
  falling back to the item's own raw Layer-1 severity with an unknown
  entity signal only when no alert exists yet.
- `compute_expected_memberships` (a new pure function, extracted from
  `classify_issuer` so both the live incremental path and the
  reconciliation script share identical rules) requires an *explicit*
  `issuer_is_subject is True` — not merely "not `False`" — for automatic
  `verified` status on definitive evidence (Chapter 11 /
  bankruptcy-or-receivership / plan-confirmed). An unresolved/unknown
  attribution now correctly demotes to `partial` rather than defaulting to
  `verified` — a deliberate tightening: an objective, highest-precision
  category must never auto-verify without positive confirmation. A
  subsidiary/third party's real event still surfaces (`partial`, never
  discarded) — it just never overclaims the parent itself filed.
  Suggestive-universe gating is unchanged in shape (still HIGH/MEDIUM
  effective severity → `partial`), it simply now reads the AI-reviewed
  effective severity instead of the raw one.
- `classify_issuer` (the live, per-call path used by
  `market_discovery_service`/`enrichment_orchestrator`) stays
  upgrade-only by design — it still cannot downgrade or remove an
  existing membership, exactly as before.

**SEC Full-Text-Search `forms` Parameter Bug (found via the required 2026 benchmark check)**

Checking Nexus's Jan–Aug 2026 discovery results against known real 2026
Chapter 11 filers found 4 confirmable, real misses: FAT Brands, Bitcoin
Depot, Inotiv, GoHealth — all with genuine, structured 8-K Item 1.03
filings squarely inside the discovery window, live-confirmed via direct
SEC full-text-search queries. (Sangamo Therapeutics, Cumulus Media, QVC
Group, and Trinseo — the other 4 benchmark names — were correctly found
and classified; Broad Street Realty and IO Biotech returned zero hits for
"chapter 11"/"going concern" even via a correctly-parameterized, direct
SEC query, so no bug is claimed for those two — an honest "not found, not
provably a Nexus gap" rather than a fabricated result.)

Root cause, live-verified directly against `efts.sec.gov` (not guessed):
mixing an amendment-suffix form (e.g. `"8-K/A"`) into the same
comma-separated `forms` value as base forms silently corrupts SEC's
server-side filter. `forms=8-K` alone returned 577 real "chapter 11" hits
over a fixed window; `forms=8-K,10-K` returned 1002; `forms=8-K,10-K/A`
(one amendment suffix mixed in) returned **0**. The actual 10-form
`MONITORED_FORM_TYPES` list (5 base + 5 amendment types) Milestone 7.5's
Layer-0 discovery sends on every one of its 18 queries returned just 50
hits instead of the ~1460 confirmed to genuinely exist — a >96% real
coverage loss on every query, the entire milestone, silently.

Fixed in `market_discovery_service._split_forms_for_full_text_search`:
splits any `forms` tuple into a base-forms group and an amendment-forms
group (both independently confirmed correct), calling
`search_full_text_fn` once per group per query/page instead of once with
the corrupted combined list. This preserves the exact 10 form types
`MONITORED_FORM_TYPES` already specifies — not a query/scope expansion,
a fix to how the already-approved list is transmitted to SEC's API, per
explicit instruction not to broaden discovery scope absent a proven
high-value bug (this one is proven, live, reproducibly). **Not yet
re-run against historical data this milestone** — re-running the full
Jan–Aug backfill was out of scope for a signal-quality calibration pass;
tracked as TD-014's resolution note for a future discovery run to pick
up naturally.

**Reconciliation**

`app.scripts.reclassify_system_universes` (new, idempotent, auditable):
Phase 1 backfills `issuer_is_subject` for existing definitive-category
alerts that predate migration `0011`, re-reviewing each alert's *complete*
original `evidence_ids` (not a reconstructed subset) so the AI sees the
same context the original review did. Phase 2 recomputes every affected
issuer's memberships from their full evidence history via
`compute_expected_memberships`, applying the result via a new
`apply_correction` (upgrade, downgrade, add, *and* remove — the one and
only path permitted to downgrade/remove, `classify_issuer` itself stays
upgrade-only). Only ever touches the 8 `system_seeded` evidence-driven
collections; a defensive check skips any non-`system_seeded` membership
found at one of those slugs (should be architecturally impossible per the
existing collision guard). Supports `--dry-run` for a read-only preview.

Run against the live shared Supabase project, 5 passes total (retries are
safe/idempotent by design — each pass only re-attempts alerts still at
`issuer_is_subject IS NULL`, converging with diminishing returns:
32 → 31 → 20 → 18 → 19 review failures across passes, the residual
tracked as TD-015). **Zero canonical rows deleted**: `issuer` (541),
`sec_filing` (6,036), `research_evidence` (5,417), and `alert_event`
(1,856) counts are byte-for-byte unchanged before and after every pass —
only `collection_membership` rows in the 8 evidence-driven collections
were added, upgraded, downgraded, or removed.

**Before / After (system-generated Research Universe memberships)**

| Universe | Before (verified / partial) | After (verified / partial) |
|---|---|---|
| Chapter 11 | 54 / 0 | 16 / 4 |
| Post-Emergence | 0 / 0 | 13 / 1 |
| Distressed Core | 54 / 344 | 22 / 277 |
| Default / Covenant Stress | — / 281 | — / 173 |
| Going Concern | — / 210 | — / 244 |
| Liability Management | — / 68 | — / 33 |
| Refinancing Risk | — / 130 | — / 115 |
| Restructuring / Strategic Alternatives | — / 49 | — / 45 |

Chapter 11 fell 54 → 20 total (63% reduction), matching the audit's
~65% false-positive estimate. Distressed Core (the broadest,
union-of-everything universe) fell 398 → 299 (25% reduction) — smaller
and more trustworthy, per the milestone's own guiding principle.
Default/Covenant Stress fell 281 → 173 (38%); Liability Management 68 →
33 (51%); Refinancing Risk 130 → 115 (12%). **Post-Emergence rose 0 → 14**
— this category was *structurally dead* before this fix: its only
qualifying evidence type (`plan_confirmed`) scores `medium` at the Layer-1
level, which could never satisfy the old raw-severity `HIGH` gate no
matter what evidence existed; the new AI-reviewed effective-severity gate
correctly recognizes genuine post-emergence disclosures (Cumulus Media,
Trinseo, Nine Energy Service, Old QVC Group, Spirit Aviation Holdings,
ProPhase Labs, and others) that were always present in the evidence but
structurally unreachable. **Going Concern rose 210 → 244** — its rule was
already high-precision, and the AI-reviewed bundle-level severity
correctly surfaces genuine signal the old per-item-only view sometimes
missed; not a red flag.

**Alert Engine Audit**

Sampled across severity/detection-method combinations; confirmed sound,
not touched. No true duplicate `bundle_key`s exist (DB-enforced, verified
`0` rows). One real but low-frequency, low-severity pattern found: a
same-day batch of delinquent amended filings (Apex 11 Inc., 6 separate
real accession numbers, 10-Q/A and 10-K/A catch-up filings all dated
2026-01-26) each correctly produces its own alert since each is a
genuinely distinct real SEC filing, but the practical effect reads as
repetitive on that one day. Documented as a known, minor limitation
(cross-filing same-day bundling would be a materially larger bundling-
architecture change, out of this calibration pass's scope) rather than
fixed. EchoStar/Hughes Satellite Systems Corporation's alerts were
independently confirmed already correctly worded ("an EchoStar
subsidiary") — direct evidence the alert engine itself needed no repair.

**Morning Brief Delta / CourtListener Metric**

Confirmed correct, not a bug: `since` correctly resolves to
`max(latest successful filing_monitor_run, latest successful
market_discovery_run)`; all 665 existing `court_docket_entry` rows were
created before the current watermark, and Milestone 7.5's backfill found
zero new verified CourtListener links (consistent with ADR-020 holding
steady at scale) — "New court events = 0" is an honest reflection of both
facts, not a query defect.

**2026 Benchmark Check**

| Company | Found? | Classification | Notes |
|---|---|---|---|
| Sangamo Therapeutics | Yes | Correct (`verified` Chapter 11, HIGH, `issuer_is_subject=True`) | |
| Cumulus Media | Yes | Correct (`verified` Chapter 11 + Post-Emergence) | |
| QVC Group (Old QVC Group, Inc.) | Yes | Correct (`verified` Chapter 11 + Post-Emergence) | |
| Trinseo | Yes | Correct (`verified` Chapter 11 + Post-Emergence) | |
| FAT Brands | No | — | Real miss — SEC `forms` bug (TD-014), confirmed live 8-K Item 1.03/2.04/3.01 filings exist in-window |
| Bitcoin Depot | No | — | Real miss — same cause |
| Inotiv | No | — | Real miss — same cause |
| GoHealth | No | — | Real miss — same cause, confirmed live Item 1.03/2.04/5.02/7.01/9.01 8-K |
| Broad Street Realty | No | — | No SEC full-text hits for "going concern"/"chapter 11" even via a correct, unrestricted direct query — not claimed as a Nexus bug |
| IO Biotech | No | — | Same as above |

**Tests Added**

- `test_universe_classification_service.py`: 3 gating regression tests
  (definitive evidence demoted to `partial` when `issuer_is_subject=False`;
  suggestive evidence excluded when the AI-reviewed alert downgrades
  severity; definitive evidence without any alert now falls back to
  `partial`, not `verified` — a deliberate behavior change, documented in
  the test itself) + 4 `apply_correction` tests (downgrade, removal,
  idempotency, never touching a non-`system_seeded` membership).
- `test_evidence_review.py`: `issuer_is_subject` parses correctly when
  `false`; defaults to `true` when a response omits the field.
- `test_research_universe_service.py`: `verification_status` surfaces
  correctly for both `verified` and `partial` issuer-universe memberships
  (previously dropped from the API response entirely).
- `test_market_discovery_service.py` +
  `test_market_discovery_forms_split.py`: the `forms`-splitting fix never
  produces a mixed base/amendment list, exact-order regression coverage,
  and the real `MONITORED_FORM_TYPES` list splits into the live-verified
  5/5 shape.
- `test_research_evidence_repository.py`: the new
  `list_evidence_by_issuer_and_types`/`list_issuer_ids_with_evidence_types`
  repository functions (added to eliminate an N+1 query pattern the
  reconciliation script's first draft had — ~500 issuers × up to 15 types
  of separate round-trips to a remote pooled connection, a real
  contributor to an early wall-clock blowup, see Problems Encountered).
- `IssuerPage.test.tsx`: a `partial` universe membership renders visibly
  distinct from a `verified` one (a `(suggested)` label, dashed outline,
  and clarified tooltip) — never presented identically to a settled fact.

**Test Results**

Backend: `ruff`, `black`, `mypy` clean; `pytest` — 380 passed, 0 failed.
Frontend: `eslint`, `prettier`, `tsc` clean; `vitest` — 68 passed, 0
failed; production build succeeds. `alembic check`: zero drift.
`pre-commit run --all-files`: all 15 hooks pass (see Problems Encountered
for two false starts along the way, neither a real code issue).

**Problems Encountered**

1. A live dry-run surfaced that Phase 1's first draft re-reviewed an
   *incomplete* reconstructed bundle (only the definitive-type evidence
   subset it had queried for) instead of the alert's real, complete
   original evidence set — Zhibao Technology Inc.'s `plan_confirmed`
   evidence was a boilerplate SEC cover-page checkbox bundled alongside
   genuinely severe `substantial_doubt`/`covenant_breach` evidence in the
   same real filing; reviewing the checkbox in isolation, stripped of that
   context, both under- and over-represented the bundle's real content
   depending on which items happened to be included.
2. The default `issuer_is_subject is not False` gate (treating `None` —
   unknown/unreviewed — the same as confirmed `True`) let an unconfirmed
   attribution silently qualify for `verified` status whenever a re-review
   attempt failed, defeating the fix's purpose for exactly the cases where
   AI confirmation was least available.
3. A destructive live `alembic downgrade -1` / `upgrade head` round-trip
   test, run *after* the reconciliation script had already backfilled
   real `issuer_is_subject` values in production, dropped and recreated
   the column — wiping all ~190 backfilled values back to `NULL`. The
   already-computed `collection_membership` corrections were unaffected
   (they were persisted independently and don't depend on
   `issuer_is_subject` remaining readable after the fact), but the audit
   trail column itself had to be fully re-backfilled.
4. Two initial background reconciliation runs, started concurrently with
   an unrelated full `pytest` run, took over 5 hours each and one hit a
   transient `psycopg.OperationalError: server closed the connection
   unexpectedly` — traced to Supabase connection-pool contention from
   running two heavy, long-lived DB-bound processes simultaneously, not a
   logic defect (confirmed: the identical `pytest` suite completed in
   ~3 minutes when run alone immediately after).
5. The reconciliation script's own per-issuer error-isolation `try` block
   didn't actually wrap the issuer's initial `get_issuer` read — a
   transient connection drop on that specific line crashed the entire run
   instead of being caught and isolated to one issuer, exactly the
   per-issuer boundary this codebase's other long-running scripts already
   rely on.
6. `pre-commit run --all-files` intermittently failed `detect-private-key`
   and `check-yaml` with `[WinError 4551] An Application Control policy
   has blocked this file` — reproducing the hook's own file-read logic
   directly (plain `open(filename, 'rb')`) worked fine for every affected
   file, isolating the failure to the cached hook virtualenv's own
   subprocess launch, not file content or this milestone's code.

**Solutions**

1. Phase 1 now finds bundles containing definitive-type evidence, then
   re-reviews using the alert's own already-stored, complete
   `evidence_ids` (`research_evidence_repository.list_evidence_by_ids`) —
   matching exactly what the original review saw.
2. `compute_expected_memberships`'s definitive gate now requires
   `issuer_is_subject is True` explicitly; `None` and `False` are treated
   identically (both demote to `partial`, never silently promote).
   Existing tests asserting the old `not False` behavior were updated to
   reflect this deliberate tightening, with a new test
   (`test_definitive_evidence_falls_back_to_partial_without_an_alert`)
   documenting exactly why.
3. Re-ran the reconciliation script (4 more passes) to restore the
   backfilled data; going forward, destructive migration round-trip tests
   are only run *before* a migration's column is populated with real data
   this session created, never after.
4/5. Fixed the error-isolation scope (the full per-issuer body, including
   the initial reads, now sits inside the `try`), added a new
   `list_evidence_by_issuer_and_types` repository function to eliminate
   the N+1 query pattern, and added `-u`/`flush=True` real-time progress
   output so a stalled or slow run is visible immediately rather than
   discovered hours later. Re-ran alone (no concurrent heavy process) —
   completed cleanly with real-time visible progress each time after.
6. `pre_commit clean` followed by a fresh hook-environment rebuild
   resolved it immediately — confirms a corrupted/quarantined cached
   virtualenv, not a code or content issue.

**Remaining Work**

- TD-014 (new, resolved code, not yet re-run against historical data):
  the SEC `forms`-parameter fix is live in code; a future discovery
  delta/backfill run will benefit from it naturally, no separate backfill
  scheduled this milestone.
- TD-015 (new): 19 alerts still have `issuer_is_subject IS NULL` after 5
  reconciliation passes — safe (never wrongly promotes), tracked for a
  future investigation into why these specific re-reviews persistently
  fail.
- TD-001 through TD-013 unchanged, carried forward.
- Milestone 8 (Watchlists) — unstarted, requires separate explicit
  approval to begin.

**Git Commit Hash**

`f11ef00` — implementation, reconciliation, tests, documentation.

**Developer Notes**

The single most validating moment of this milestone was discovering that
the AI-reviewed *alert* for BlackSky Technology's Chapter 11 evidence
already read "relates to a director's prior company, not BlackSky" at
`severity=low` — while the *classification* layer, looking at the same
underlying evidence, had confidently marked BlackSky `verified` System-
Detected: Chapter 11. The fix wasn't building new intelligence; it was
teaching one already-correct part of the system to talk to another. That
pattern held for essentially every false positive sampled across every
category — proof that the AI review mechanism was sound from the moment
it shipped, and that the real defect was an architectural gap in what
data flowed downstream from it, not a model-quality problem for a bigger
model or a fancier prompt to fix. The reconciliation script's design —
computing "what should be true" as a pure function shared with the live
path, then applying it via a separate, explicitly correction-capable
writer — is the same shape this codebase already uses for provenance and
evidence: never trust a process that can only move state one direction to
also be the process responsible for admitting the state was wrong.

**GitHub Remote and Push Results**

- `git push origin main` — succeeded: `80f880b..7c921db  main -> main`.
- Post-push verification: `git ls-remote origin main` returns
  `7c921dbd1e6aa34e8cc976ba3a4655feb3524203`, matching the local commit
  exactly.
- Remote branch: https://github.com/kirantoday/nexus-credit-intelligence/tree/main

---

## 2026-08-09 — Milestone 7.5.2: Daily Delta Run & Morning Research Brief Semantics

**Summary**

Inserted before Milestone 8 by explicit direction to prove the real
day-to-day operating loop — a genuine 2026-08-07 daily delta through the
production market-discovery pipeline — before building anything further
on top of it. Two real bugs were root-caused (not guessed) and fixed: the
Morning Research Brief's "Last successful run" display silently pointed
at a historical `backfill` run instead of any genuine daily run, and,
discovered only by actually running the real delta, the fix's own `since`
boundary initially excluded the very run's output it was supposed to
report. TD-014's SEC `forms` fix (Milestone 7.5.1) was active for this
run; the January–August historical repair itself is explicitly deferred
to the newly-inserted Milestone 7.5.3, not run here.

**Root Cause Investigation (before any code change)**

Production's Morning Research Brief reported "Last successful run: Aug 6,
2026 around 6:01 PM" despite Milestones 7.5 and 7.5.1 having both run
(and pushed) after that. Read `filing_monitor_api_service.get_morning_brief`,
`filing_monitor_run_repository.get_latest_successful_run`, and
`market_discovery_repository.get_latest_successful_run` before changing
anything, then queried the live database directly:

- `filing_monitor_run`'s most recent successful row (`dbf7430b`) was
  `mode=backfill`, `completed_at=2026-08-06 22:01:15 UTC` — exactly
  matching the stale "Aug 6, 6:01 PM" display.
- `market_discovery_run`'s most recent successful row (`62abe8ab`) was
  also `mode=backfill`, `completed_at=2026-08-07 14:11:01 UTC`.
- **No `mode=delta` run of either pipeline had ever completed in this
  database.** `get_latest_successful_run` on both repositories filters
  only by status (`success`/`baseline_established`), never by mode, so a
  historical backfill's completion time was silently standing in for "the
  last time we checked in on a normal operating day."

**One Authoritative Daily-Run Concept**

Added `get_latest_successful_daily_run`/`get_latest_daily_run` to both
`filing_monitor_run_repository` and `market_discovery_repository` —
identical mode filter (`delta`/`baseline` only, `backfill` excluded) on
top of the existing status filter — added *alongside*, not replacing,
the existing `get_latest_successful_run` functions, which are still
correct for their original purpose (a `delta` run's own watermark
resume-point legitimately should include a prior backfill's work, so it
never needlessly re-scans it). `filing_monitor_api_service._latest_
successful_daily_run`/`_latest_daily_run` combine both pipelines,
preferring whichever is more recent, and expose the result as a new
pipeline-agnostic `DailyRunSummary` schema — an analyst reading the brief
never needs to know or care whether `filing_monitor_run` or
`market_discovery_run` produced it. `get_morning_brief` was rewritten to
scope every "new_*"/actionable-alert count to this one boundary via a new
`triggered_since` parameter threaded through `alert_repository.list_alerts`/
`count_alerts_by_severity`/`count_ai_assisted_alerts` (filters
`alert_event.triggered_at`, Nexus's own processing time — deliberately
independent of `as_of_date`, the event's real-world date, per the existing
Milestone 7.5 event-date-vs-processing-date distinction). The frontend
(`MorningResearchBriefPage.tsx`) now defaults its alert list to the same
`since` boundary the summary bar used, with an explicit "Show historical
alerts" toggle as the one escape hatch — the page can no longer show a
small "actionable alerts" count above a list of hundreds of unrelated
historical alerts. `format.ts`'s `formatDateTime` now renders in explicit
`America/New_York` rather than the viewer's local timezone, matching this
milestone's "today's Morning Brief" being a shared analyst-facing concept.

**A Second Real Bug, Found Only By Running The Real Delta**

Running the actual 2026-08-07 delta (below) revealed the fix above was
still incomplete: the brief's own printed `since` reflected the new
`market_discovery` `delta` run correctly, but `new_sec_filings`/
`new_research_evidence`/`actionable_alerts_total` all reported **0**
immediately after a run that had genuinely just created 1207 SEC filings,
822 evidence rows, and 356 alerts (confirmed via direct row counts —
`created_at`/`triggered_at >= now() - 2 hours` returned exactly those
figures). Root cause: `since` was set to the latest successful run's
`completed_at` — but every filing/evidence/alert a run discovers is
necessarily written *before* that run's own completion timestamp, so a
`completed_at` boundary silently excluded the entire run's own output.
Corrected to `started_at`, which is safe and non-overlapping across
consecutive daily runs by construction (a run's own `started_at` always
follows the previous run's `completed_at` in this pipeline's sequential
operating model, and for the very first-ever daily run, "since I started
running" is exactly the right definition of "new"). Re-verified against
the live database after the fix: `new_sec_filings=1207`,
`new_research_evidence=822`, `actionable_alerts_total=356` (49 high / 65
medium / 242 low; 351 AI-assisted / 5 deterministic) — matching the real
row counts exactly.

**Real 2026-08-07→08 Daily Delta Run**

Ran `python -m app.scripts.run_market_discovery --mode delta` — the
existing, unmodified production entry point, no one-off Aug-7-specific
code. `delta` mode self-computed its window from the current watermark
(`previous_watermark.date()=2026-08-07` from the last successful — a
backfill — run, `resolved_end=date.today()=2026-08-08`), landing exactly
on the requested "source activity on 2026-08-07" window without any
manual override.

| Metric | Value |
|---|---|
| Status | `success`, 0 errors |
| Window | 2026-08-07 .. 2026-08-08 |
| Started / completed (UTC) | 2026-08-08 23:19:05.994 / 2026-08-09 00:19:08.138 |
| Elapsed | 3509.0s (~58.5 minutes) |
| SEC full-text-search queries executed | 38 |
| Filings examined (raw FTS hits) | 519 |
| Candidate filings (unique `(cik, accession_no)`) | 285 |
| Issuers resolved — already known (`matched_existing`) | 39 |
| Issuers resolved — newly discovered (`verified_new`) | 246 |
| Issuers ambiguous / rejected | 0 / 0 |
| New SEC filings (`created_at >= since`) | 1207 |
| New research evidence (`created_at >= since`) | 822 |
| New CourtListener docket entries | 0 |
| Actionable alerts (`triggered_at >= since`) | 356 |
| — High / Medium / Low | 49 / 65 / 242 |
| — AI-assisted / deterministic | 351 / 5 |
| OpenFIGI enrichment outcomes | `complete` 73, `no_data` 182, `failed_retryable` 20 |
| SEC enrichment outcomes | `complete` 247, `no_data` 27, `failed_retryable` 1 |
| CourtListener enrichment outcomes | `no_data` 3, `unsupported` 272 |

The large evidence/alert/filing counts relative to a single day's window
are real and explained, not a bug: 246 newly-discovered issuers each
triggered the enrichment orchestrator's `_enrich_sec` (never-checked
issuer → `SEC_FIRST_CHECK_LOOKBACK_DAYS=90`-day lookback, independent of
the discovery run's own narrower window), which found and processed real
prior SEC activity for issuers that had just qualified as
distress-relevant. This is existing Milestone 7.5 enrichment-orchestrator
behavior, unmodified by this milestone.

`new_court_events=0` was investigated, not assumed correct. Root cause:
`enrichment_orchestrator._enrich_courtlistener` only attempts a
CourtListener search when the issuer already has docket-relevant evidence
on file (`DOCKET_RELEVANT_EVIDENCE_TYPES`) — of the 285 processed
candidates, only 3 had such evidence at the time CourtListener enrichment
ran (272 were `unsupported`, correctly skipped without a search); all 3
searches returned no matching docket (`no_data`). Zero is the genuinely
correct outcome for this window, not a manufactured or suppressed count.

**Idempotency Re-Run**

`delta` mode self-advances its window from the watermark, so a second
literal `--mode delta` invocation would move forward to a new window
(2026-08-09), not repeat the same one. To prove idempotency over the
*identical* 2026-08-07→08 window and exercise the identical dedup code
paths a repeated delta would use, re-ran the same window explicitly via
`--mode backfill --start 2026-08-07 --end 2026-08-08` (a backfill-mode run
never affects the daily-run boundary, since it's structurally excluded
from `get_latest_successful_daily_run`).

| Table | Before rerun | After rerun |
|---|---|---|
| `issuer` | 787 | 787 |
| `sec_filing` | 7243 | 7243 |
| `research_evidence` | 6239 | 6239 |
| `alert_event` | 2212 | 2212 |
| `market_discovery_candidate` | 891 | 891 |
| `security` | 566 | 566 |
| `court_docket_entry` | 665 | 665 |

Zero new rows in any table. The rerun completed in 38.7s (vs. 3509.0s the
first time): all 285 candidates were skipped immediately via the existing
`existing.rule_version == RULE_VERSION` idempotency check
(`market_discovery_service.run_discovery`), so `issuers_resolved_existing`/
`issuers_resolved_new`/`evidence_created`/`alerts_created` were all `0` —
full idempotent skip, not a partial/silent one. `GET /api/morning-brief`
was re-verified after the rerun to still report the original `delta`
run (`2a6d174c`) as `last_successful_run`, confirming the backfill-mode
idempotency check never contaminates the daily-run boundary.

**Watermark and Failure Safety**

Verified by code (both existing, unmodified this milestone, and exercised
live by the real run above) rather than by manufacturing a live
production failure:

- `get_latest_successful_daily_run` filters `status IN (success,
  baseline_established)` — a `completed_with_errors` run can never be
  reported as "the last successful daily run," regression-covered by
  `tests/integration/test_filing_monitor_service.py`'s existing
  `COMPLETED_WITH_ERRORS` assertions (still passing, unmodified).
- `market_discovery_service.run_discovery`'s `resolved_watermark =
  previous_watermark if errors_count else now()` means a run with any
  error never advances the watermark, so the next run safely re-attempts
  the same unresolved window.
- Per-candidate (`resolve_issuer_fn`) and per-issuer
  (`process_issuer_filings_fn`, `enrich_issuer_fn`) `try/except`
  isolation, each with its own `db.rollback()`, means one candidate's or
  one provider's failure cannot roll back another's already-committed
  success — confirmed live: the real run above completed with
  `errors_count=0`, and TD-013 already documents this isolation holding
  under real transient-failure conditions during Milestone 7.5's much
  longer historical backfill.

**AI Usage / Cost Observability**

Per explicit instruction, no cost estimate was invented. Investigated
what is actually capturable: `AnthropicProvider.complete()`
(`backend/app/ai/providers/anthropic_provider.py`) discards the raw
Anthropic SDK response's `usage` (input/output token counts) entirely,
returning only `text`/`model`/`stop_reason`; no counter exists anywhere
for total AI review invocations, including calls that didn't produce a
qualifying alert. What could be reliably reported: LLM provider
`anthropic`, model `claude-sonnet-5` (from `Settings.anthropic_model`),
and a DB-verified **lower bound** of 351 successful AI-assisted alert
syntheses (`alert_event.detection_method=ai_assisted`, scoped to this
run's `since` boundary) — not a true call count, and no token/cost
figure. Recorded as new Technical Debt (TD-016).

A second, related gap was found investigating why the run's own printed
summary showed `evidence_created: 0, alerts_created: 0` despite the real
822/356 counts above: `market_discovery_run`'s counters only tally
evidence/alerts created directly inside the discovery loop's own
`process_issuer_filings_fn` call, never the enrichment orchestrator's
separate `_enrich_sec` call for the same issuer in the same run. The
Morning Brief itself is unaffected (it queries `created_at`/`triggered_at`
directly, never these run-row counters), but an operator reading the
run's own CLI output or the persisted run row would be misled. Recorded
as new Technical Debt (TD-017) rather than expanding this milestone's
scope into `enrichment_orchestrator`'s return-value contract.

**Milestone 15 Bookkeeping**

While verifying this milestone's production behavior, discovered
Milestone 15 (Railway/Vercel deployment validation) was already fully
satisfied, just never marked complete in `PLAN.md`. Live-verified, not
assumed: `GET https://nexus-credit-intelligence-production.up.railway.app/health`
→ `200 {"status":"healthy","environment":"production"}`;
`GET https://nexus-credit-intelligence.vercel.app/` → `200`; a real
`OPTIONS` CORS preflight from the Vercel origin to the Railway API
returns `access-control-allow-origin:
https://nexus-credit-intelligence.vercel.app`; Alembic migrations already
applied live via `DIRECT_DATABASE_URL` (KI-001, closed 2026-08-05).
Marked "Completed Early" in `PLAN.md` §Milestone Status — roadmap
bookkeeping only, no deployment action taken by this milestone.

**Railway Cron — Deliberately Not Activated**

`PLAN.md` §24.6 documents a target nightly schedule; per explicit
instruction, the scheduler was not activated this milestone. The daily
run was proven manually (above); the exact production command for a
future nightly invocation is documented in `README.md` § Operational
scripts. Activation requires separate, explicit approval.

**Files Created**

- `backend/tests/integration/test_daily_run_boundary.py`

**Files Modified**

- `backend/app/repositories/filing_monitor_run_repository.py` —
  `get_latest_successful_daily_run`, `get_latest_daily_run`.
- `backend/app/repositories/market_discovery_repository.py` — mirrored.
- `backend/app/repositories/alert_repository.py` — `triggered_since`
  parameter on `list_alerts`/`count_alerts_by_severity`/
  `count_ai_assisted_alerts`.
- `backend/app/schemas/filing_monitor.py` — new `DailyRunSummary`;
  `MorningBriefSummary.last_successful_run`/`latest_run` retyped to it,
  new `since` field.
- `backend/app/services/filing_monitor_api_service.py` — daily-run
  combination helpers, rewritten `get_morning_brief`, `triggered_since`
  threaded through the service-level `list_alerts`.
- `backend/app/api/routes/alerts.py` — `triggered_since` query parameter.
- `web/src/api/filingMonitor.ts` — `DailyRunSummary` type,
  `MorningBriefSummary` retyped, `AlertsQuery.triggeredSince`.
- `web/src/components/BriefSummaryBar.tsx` — "Latest successful daily
  run"/"Data through"/"Run window" display.
- `web/src/pages/MorningResearchBriefPage.tsx` — default `triggeredSince`
  scoping, "Show historical alerts" toggle.
- `web/src/pages/MorningResearchBriefPage.test.tsx` — fixture updated to
  `DailyRunSummary` shape.
- `web/src/lib/format.ts` — `formatDateTime` explicit `America/New_York`.
- `PLAN.md` — Milestone 7.5.2/7.5.3 inserted, Milestone 15 marked
  Completed Early, TD-016/TD-017 added, Project Status/Next Immediate
  Goal updated.
- `README.md` — Operational scripts section (backfill/delta/nightly
  commands, which run powers the Morning Brief), stale KI-001 references
  corrected.

**Database Changes**

None — no migration this milestone. All changes are read/query-path
(repository filters, service composition) and one existing-column
semantics fix (`since` derivation).

**API Endpoints Added**

None new. `GET /api/alerts` gained an optional `triggered_since` query
parameter (backward compatible — omitted, behavior is unchanged).
`GET /api/morning-brief`'s response gained a `since` field and retyped
`last_successful_run`/`latest_run` to `DailyRunSummary`.

**Frontend Pages Added**

None new — `MorningResearchBriefPage.tsx` modified in place.

**Environment Variables Added**

None.

**Tests Added**

`backend/tests/integration/test_daily_run_boundary.py` (4 new integration
tests, all passing against the live shared Supabase project):
- `test_filing_monitor_repo_daily_run_excludes_more_recent_backfill`
- `test_market_discovery_repo_daily_run_excludes_more_recent_backfill`
- `test_get_morning_brief_daily_boundary_ignores_later_backfill`
- `test_alert_repository_triggered_since_filters_by_processing_time`

`web/src/pages/MorningResearchBriefPage.test.tsx` updated in place for
the new `DailyRunSummary` fixture shape and subtitle wording (all 4
existing tests, unchanged in intent, still passing).

**Test Results**

- Backend: 384 passed (380 pre-existing + 4 new), 0 failed.
- Frontend: 68 passed across 12 files, 0 failed.
- `ruff check` / `black --check` / `mypy app` — all clean (152 backend
  source files).
- `eslint` / `tsc -b` / `prettier --check` — all clean.
- `alembic check` — "No new upgrade operations detected" (zero drift).
- Backend boots (`GET /health` → 200 locally and in production).
- Frontend production build succeeds (`vite build`).

**Commands Executed**

```
python -m app.scripts.run_market_discovery --mode delta
python -m app.scripts.run_market_discovery --mode backfill --start 2026-08-07 --end 2026-08-08
python -m pytest -q
python -m ruff check app/ tests/
python -m black --check app/ tests/
python -m mypy app/
python -m alembic check
npm run lint / npm run typecheck / npm run format:check / npm run build
npx vitest run
```

**Deployment Validation**

Pushed to `main` (`ca41b13`, `859072e`); Railway/Vercel auto-deployed.
Re-verified live in production (Chrome, `nexus-credit-intelligence.vercel.app`
+ `nexus-credit-intelligence-production.up.railway.app`) after the deploy
landed — polled `GET /api/morning-brief` until its response included the new
`since` field (confirming the new backend was live) before verifying:

- Morning Research Brief loads; subtitle reads "New Research Alerts — Since
  Last Successful Daily Run."
- "Latest successful daily run: Aug 8, 2026, 8:19 PM" / "Current run: success"
  — correctly the real `market_discovery` `delta` run, not a backfill.
- "Data through: Aug 8, 2026, 7:19 PM · Run window: Aug 7, 2026 – Aug 8, 2026"
  — `since` (`started_at`) and `completed_at` correctly shown as two distinct
  timestamps, both in America/New_York.
- Summary metrics match the live API and the real run exactly: 1207 new SEC
  filings, 0 new court events, 822 new research evidence, 356 actionable
  alerts (49/65/242 high/medium/low), 351 AI-assisted.
- Severity filter (`High`) and Research Universe filter
  (`System-Detected: Chapter 11`) both correctly re-scope the alert list via
  URL query params.
- "Show historical alerts" toggle correctly switches the subtitle to "All
  Research Alerts — All-Time" and removes `triggered_since` from the
  underlying request.
- Evidence drill-down ("Why was this flagged?") expands real excerpts with
  matched rule names, exactly as stored.
- Issuer Detail drill-down (Dropbox, Inc.) loads real OpenFIGI-sourced
  securities with `live` provenance badges.
- A compound alert (Olenox Industries — subsidiary SG Echo LLC's Chapter 11
  alongside the issuer's own going-concern doubt) rendered with cautious,
  explicit wording distinguishing the subsidiary event from the issuer's own
  — the 7.5.1 fix's alert-wording discipline is intact.
- Research Universes page shows `verified` (curated) vs. `Not yet verified`
  (system-suggested) labels correctly, unchanged from 7.5.1.
- Credit Universe loads with real, live-badged data.
- `read_network_requests` confirmed every `/api/*` call returned `200`,
  including `GET /api/alerts?triggered_since=2026-08-08T23:19:05.994383Z...`
  — the exact `since` boundary threaded through to the alert list, proving
  the summary and the displayed rows share one boundary end to end.
- A live `OPTIONS` CORS preflight from the Vercel origin to the Railway API
  returned `access-control-allow-origin:
  https://nexus-credit-intelligence.vercel.app` — no CORS errors.
- `read_console_messages` found only a known Chrome-extension messaging
  artifact ("message channel closed"), no application-level errors.

**Problems Encountered**

1. The Morning Brief's `since` boundary, as first implemented, excluded
   the very run whose output it was meant to report — see "A Second Real
   Bug" above. Found by actually running the real delta and comparing its
   printed/reported metrics against direct database row counts, not by
   inspection alone; this is exactly why the milestone required a real
   run rather than a synthetic/mocked proof.
2. `alert_event.triggered_at` is a `server_default=now()` column, and
   Postgres's `now()` returns the enclosing transaction's start time —
   constant across every statement in a single test transaction. The new
   `triggered_since` regression test initially failed because two alerts
   seeded moments apart in test code received an identical `triggered_at`.
   Fixed by setting `triggered_at` explicitly post-creation in the test,
   modeling two genuinely distinct processing times the way two separate
   real daily-run invocations naturally would.
3. `delta` mode cannot be asked to repeat a past window (it always
   self-advances from the current watermark), so the idempotency re-run
   used `--mode backfill` with the identical explicit window instead —
   documented above as a deliberate substitution, not an oversight.

**Solutions**

All three were caught by direct verification against the live database
and live run output rather than trusting the implementation's own
self-reported numbers — the same discipline this project has applied at
every prior milestone.

**Remaining Work**

- TD-016 (new): No AI call/token/cost observability exists in the
  codebase.
- TD-017 (new): `market_discovery_run.evidence_created`/`alerts_created`
  undercount real activity (enrichment-orchestrator-triggered evidence
  isn't tallied).
- Milestone 7.5.3 (Historical Discovery Coverage Repair) — planned, not
  started, deliberately deferred out of this milestone's scope.
- Railway Cron activation — documented, not activated; requires separate
  explicit approval.

**Git Commit Hash**

`ca41b13` — implementation, real daily-delta run, idempotency proof,
documentation.

**Approximate Time Spent**

~4 hours (governance/diagnosis, implementation, real ~59-minute live
discovery run + ~1-minute idempotency rerun, verification, documentation).

**Developer Notes**

The most consequential moment of this milestone wasn't the initial fix —
it was the decision to actually run the real Aug 7 delta rather than
trust the fix by inspection alone. The first version of `since` looked
correct in isolation (it read the latest successful daily run's
completion time, which sounds exactly right for "as of when this brief is
current"), and every existing unit-shaped test would have passed against
it. Only running it for real, then independently cross-checking its
reported zeros against direct `created_at`/`triggered_at` row counts,
surfaced that "as of when the run finished" and "since before the run's
own work began" are different boundaries — and that the whole point of a
daily-delta brief is the second one. This mirrors Milestone 7.5.1's
lesson almost exactly: a plausible-sounding implementation and a
literally-verified one are not the same thing, and this codebase's
recurring habit of checking real data before declaring success is what
keeps catching the gap between them.

---

## 2026-08-09 — Milestone 7.5.2 (correction): Morning Research Brief user-relative semantics

**Summary**

Same-day, explicit follow-up direction: the daily-run-boundary fix
completed earlier this milestone was still, at bottom, "what did the
last pipeline run do" — correct, but not the actual product question.
Corrected the Morning Research Brief's definition to "what materially
changed since this user last reviewed the Morning Research Brief?" —
a user-relative boundary, issuer-grouped and severity-ranked
developments, new-vs-historical partitioning, Research Universe
membership-change surfacing, and pipeline/run counters demoted to a
secondary block. A genuine performance regression was found and fixed
live before this shipped, not after.

**Pre-Implementation Inspection (reported before any code change)**

Per explicit instruction, inspected and reported findings before
implementing:

- **(a) Current boundary**: `since` = the latest successful `delta`/
  `baseline`-mode pipeline run's `started_at` (7.5.2's first-pass fix) —
  entirely pipeline-run-driven, no concept of when a person last looked.
- **(b) User-level state**: none exists, confirmed by direct inspection,
  not assumption. `Settings.auth_enabled = False` (TD-002, open); no
  `user` table; no session/cookie middleware anywhere in `app/api`; no
  `Depends(get_current_user)`; zero `localStorage`/`sessionStorage`
  usage anywhere in the frontend. Only free-text labels
  (`owner_user_id`, `acknowledged_by`, `dismissed_by`) exist — labels,
  not identity. Decision: do not fake per-user state; use a single
  shared timeline as the documented interim posture, with the real
  per-user requirement recorded as new Technical Debt.
- **(c) Proposed design**: reported in full before implementing — new
  `morning_brief_view` table (pure-read `GET`, side-effecting `POST
  /view` gated by a `MIN_VIEW_GAP` heuristic), reuse of the already-
  correct `alert_event.is_backfill` signal for the new/historical split
  (verified live during 7.5.2's original browser walkthrough — no new
  field needed), a new `collection_membership.updated_at` column for
  membership-upgrade detection, and the reshaped `MorningBriefSummary`/
  `IssuerDevelopment`/`RunDetails` response shape.
- **(d) Migration required**: yes — confirmed and flagged before writing
  any schema.

**Implementation**

- Migration `0012`: `morning_brief_view` (append-only: `id`, `viewed_at`,
  `created_at`) and `collection_membership.updated_at` (backfilled to
  `added_at` for all ~540+ pre-existing rows via an explicit `UPDATE` in
  the same migration — the naive `ADD COLUMN ... DEFAULT now()` behavior
  would otherwise have made every existing membership appear to have
  "just changed" the first time the corrected boundary logic ran).
  Applied live against the shared Supabase project; `alembic check`
  confirms zero drift; live-verified the backfill (`0` rows with
  `updated_at != added_at` out of `1167`).
- New `app/models/brief_view.py`, `app/domain/brief_view.py`,
  `app/repositories/brief_view_repository.py` (`record_view`,
  `get_latest_view` — dumb, no business logic; the gap policy lives in
  the service layer).
- `app/services/morning_brief_service.py` (new): `_resolve_period_start`
  (real view or previous-business-day-morning fallback, 06:00
  America/New_York, Mon-Fri only — federal holidays not specially
  handled, low-stakes since this path is reachable only once),
  `_should_record_new_view`/`record_brief_view` (the idempotent-refresh
  gap predicate, factored out as a pure function mirroring
  `enrichment_orchestrator._should_run`'s shape for direct unit
  testing), and the relocated (unchanged) daily-run-boundary logic from
  7.5.2's first pass, now backing a secondary `RunDetails` block.
  `get_morning_brief` is a pure read; `record_brief_view` is the only
  function with a side effect, called separately.
- `app/repositories/collection_repository.py`:
  `list_system_seeded_memberships_changed_since` (added-or-upgraded
  memberships since a boundary, scoped to `system_seeded=True` only —
  a manually-curated membership change is an analyst's own action, not
  a research "development").
  `upgrade_membership_verification`/`set_membership_verification` now
  set `updated_at` on real changes.
- `app/schemas/morning_brief.py` (new): `MorningBriefSummary`,
  `IssuerDevelopment`, `UniverseMembershipChange`, `RunDetails`. The old
  `MorningBriefSummary` in `app/schemas/filing_monitor.py` was removed
  (superseded, not duplicated); `DailyRunSummary`/`SeverityCounts` are
  still reused from there.
- `app/api/routes/morning_brief.py`: `GET` unchanged in shape (now backed
  by the new service); new `POST /view` (`response_model=None` — a
  FastAPI/Starlette quirk requires this explicitly for a 204 response
  with a `None`-typed handler, discovered live when the app failed to
  import).
- Frontend: `IssuerDevelopmentCard.tsx` (new — issuer header + universe-
  change chips + nested `AlertCard`s), `RunDetailsPanel.tsx` (new —
  collapsed-by-default secondary diagnostics), `BriefSummaryBar.tsx`
  rewritten (period/analyst-relevant counts only),
  `MorningResearchBriefPage.tsx` rewritten (records a view once per
  mount via a `useRef` guard, after the brief query has already
  resolved; existing severity/universe/detection/status filters now
  apply client-side to the pre-grouped `new_developments`/
  `historical_intelligence` arrays; "Show historical alerts" toggle
  preserved unchanged, still backed by the flat, ungrouped
  `GET /api/alerts`). `client.ts`'s `apiFetch` now handles a `204` body
  (the app's first 204 endpoint).

**A Real Performance Regression, Found and Fixed Before Shipping**

Live-tested the actual `GET /api/morning-brief` endpoint against the
real production database before considering this done — it did not
return within 50 seconds. Root cause: the first implementation called
`alert_to_row` per alert, which itself issues two queries (an issuer
lookup, a universe-membership lookup) — fine at the existing
`/api/alerts` endpoint's page-capped scale (≤200), but applied to a
whole period's worth of alerts (~350 real alerts, 225 distinct issuers,
confirmed via direct query) meant 700+ sequential round trips to the
shared, remote Supabase instance. Fixed with two new batch-lookup
functions — `issuer_repository.list_issuers_by_ids`,
`collection_repository.list_collections_for_issuers` — replacing the
N+1 pattern with two queries total regardless of alert volume. The
same real request, re-tested after the fix, completed in 1.687 seconds
(response body 3.5MB). This also collapsed the new test suite's own
runtime from 274s to 7.5s, confirming the fix's effect wasn't
observation-specific.

**Files Created**

- `backend/alembic/versions/0012_brief_view_and_membership_updated_at.py`
- `backend/app/models/brief_view.py`, `backend/app/domain/brief_view.py`,
  `backend/app/repositories/brief_view_repository.py`
- `backend/app/services/morning_brief_service.py`
- `backend/app/schemas/morning_brief.py`
- `backend/tests/unit/test_morning_brief_boundary.py`
- `backend/tests/integration/test_morning_brief_service.py`
- `web/src/components/IssuerDevelopmentCard.tsx`,
  `web/src/components/RunDetailsPanel.tsx`

**Files Modified**

- `backend/app/models/collection.py`, `backend/app/domain/collection.py`,
  `backend/app/repositories/collection_repository.py` — `updated_at`,
  `list_system_seeded_memberships_changed_since`,
  `list_collections_for_issuers`.
- `backend/app/repositories/issuer_repository.py` —
  `list_issuers_by_ids`.
- `backend/app/schemas/filing_monitor.py` — old `MorningBriefSummary`
  removed (moved to the new schema module).
- `backend/app/services/filing_monitor_api_service.py` — `get_morning_brief`
  and its daily-run-boundary helpers removed (relocated to
  `morning_brief_service.py`); `_alert_to_row` renamed to public
  `alert_to_row` (still used by the unaffected flat `/api/alerts` path).
- `backend/app/api/routes/morning_brief.py` — new service, new `POST
  /view` endpoint.
- `backend/tests/integration/test_filing_monitor_api_service.py`,
  `backend/tests/integration/test_daily_run_boundary.py` — updated for
  the relocated/renamed functions; 3 tests whose coverage moved to the
  new test file removed (not duplicated).
- `web/src/api/filingMonitor.ts` — reshaped `MorningBriefSummary`,
  new `IssuerDevelopment`/`UniverseMembershipChange`/`RunDetails` types,
  `recordMorningBriefView`.
- `web/src/api/client.ts` — `204` response handling.
- `web/src/queries/useMorningBrief.ts` — `useRecordMorningBriefView`.
- `web/src/queries/useAlerts.ts` — `useAlerts` accepts an `enabled`
  option (the historical-alerts toggle now conditionally fetches).
- `web/src/pages/MorningResearchBriefPage.tsx`,
  `web/src/pages/MorningResearchBriefPage.test.tsx`,
  `web/src/components/BriefSummaryBar.tsx`.
- `PLAN.md` — Milestone 7.5.2's entries extended with the correction;
  TD-018 added.

**Database Changes**

Migration `0012`: `morning_brief_view` (new table),
`collection_membership.updated_at` (new column, backfilled).

**API Endpoints Added**

`POST /api/morning-brief/view` (204, no body). `GET /api/morning-brief`
response shape changed (not backward compatible with the pre-correction
shape) — the same milestone's own frontend is the only consumer, updated
in the same change.

**Tests Added**

- `tests/unit/test_morning_brief_boundary.py` (7 tests): fallback
  weekday math (weekday/Monday/Sunday reference points), the
  idempotent-refresh gap predicate (none-exists, within-gap,
  past-gap, exactly-at-gap).
- `tests/integration/test_morning_brief_service.py` (9 tests, the full
  explicitly-required scenario set): previous-day return, a
  Friday-to-Monday-shaped multi-day gap, a longer multi-day skip, a
  first-ever view (fallback), an old filing discovered today
  (historical intelligence), a genuinely new event today (new
  development), a Research Universe membership change, no material
  changes, idempotent refresh/reopen.
- `web/src/pages/MorningResearchBriefPage.test.tsx` rewritten: summary +
  issuer development cards, records-a-view-once, fallback-boundary
  message, no-material-changes empty state, historical-intelligence
  section, brief-fetch error, historical-toggle behavior (7 tests).

**Test Results**

- Backend: 397 passed (400 attempted minus 3 tests whose coverage moved,
  net from 384; one unrelated pre-existing test failed once on a
  transient shared-connection-pool drop — TD-013's documented pattern —
  and passed cleanly on immediate re-run in isolation).
- Frontend: 71 passed across 12 files.
- `ruff check` / `black --check` / `mypy app` — clean (157 backend
  source files). `eslint` / `tsc -b` / `prettier --check` — clean.
- `alembic check` — zero drift. `pre-commit run --all-files` — clean.
- Backend boots; frontend production build succeeds.

**Commands Executed**

```
python -m alembic revision --autogenerate -m "brief view and membership updated_at"
python -m alembic upgrade head
python -m pytest -q
python -m mypy app/
npm run build
npx vitest run
pre-commit run --all-files
```

**Deployment Validation**

Recorded in a follow-up entry once pushed and production is re-verified
with this correction deployed.

**Problems Encountered**

1. **A real performance regression** — see "A Real Performance
   Regression" above. Caught by actually calling the live endpoint
   against real production data before considering the milestone done,
   not by inspection or by trusting the passing test suite (the
   integration tests were passing throughout, since they exercise the
   same live database but at a scale — and, before the fix, an
   incidentally slow but not-yet-timed-out one — that didn't surface the
   problem until it was tested end-to-end as a real HTTP request).
2. **FastAPI `status_code=204` requires `response_model=None`
   explicitly** when the handler's return annotation is `None` — without
   it, the app failed to import entirely
   (`AssertionError: Status code 204 must not have a response body`).
   Fixed immediately; no other endpoint in this codebase had used 204
   before, so this was a first-time gap, not a regression.
3. **Test flakiness from assuming ordering/emptiness of a shared,
   already-populated table.** Several new integration tests initially
   assumed either that a freshly-seeded `morning_brief_view` row would
   be the global "latest" one, or that a multi-day-old boundary would
   safely include a test's own alert within `list_alerts`'s DESC-ordered,
   capped fetch window — both false once real production data (2200+
   alerts, much of it with recent `triggered_at` from this same
   session's earlier real runs) is already in the shared database.
   Fixed by monkeypatching the view-lookup directly for boundary-value
   tests (deterministic regardless of ambient rows) and by keeping
   seeded alerts' `triggered_at` safely recent (so they rank within the
   fetch window regardless of real data volume) while varying
   `period_start` alone to test gap size — the same "assume real data
   already exists" discipline this project has applied at every prior
   milestone, just newly relevant in the opposite direction (too much
   data, not too little).

**Solutions**

All three were caught by direct verification against live behavior — an
actual HTTP call for the performance issue, an actual app-import attempt
for the FastAPI quirk, and actual live-database test runs (not just
green-in-isolation ones) for the ordering assumptions.

**Remaining Work**

- TD-018 (new): the brief's "since you last looked" boundary is a single
  shared timeline, not per-user, since no authentication/session
  infrastructure exists yet (TD-002).
- Milestone 7.5.3 (Historical Discovery Coverage Repair) — still planned,
  not started, still deliberately out of scope.
- Railway Cron activation — still documented, not activated.

**Git Commit Hash**

`427b535` — implementation, real performance fix, comprehensive
scenario tests, documentation.

**Approximate Time Spent**

~3 hours (pre-implementation inspection and reporting, schema/service/
frontend implementation, the live performance investigation and fix,
comprehensive scenario testing, documentation).

**Developer Notes**

The performance regression is the second time in this same milestone
that a real, live, end-to-end check caught something the test suite
alone did not (the first was `since` excluding a run's own output). Both
share a shape: the implementation was internally consistent and every
existing test passed, but a property only observable by actually running
the real thing — real timing, real data volume, real request/response
cycle — was wrong. Neither gap was subtle in hindsight (of course querying
per-alert doesn't scale; of course a `completed_at` boundary excludes a
run's own writes), but neither was caught by static analysis, type
checking, or a green test suite either. The discipline this project keeps
returning to — run the real thing before calling it done, independently
verify its own reported numbers, and treat "the tests pass" as necessary
but not sufficient — is what turned two real, shippable-looking bugs into
fixed ones instead of production incidents.

---

## 2026-08-09 — Milestone 7.5.2 (second correction): Morning Brief response-size fix

**Summary**

Production browser verification of the first correction (`427b535`)
surfaced a third real, live-only bug: `POST /api/morning-brief/view`
intermittently returned `503` from Railway's edge when triggered by the
real page — never when tested directly. Investigated to root cause
(not patched blindly) and fixed by capping the Morning Brief's response
size.

**Investigation**

`GET /api/morning-brief` succeeded every time (200); the `POST /view`
that follows it (fired only after the `GET` resolves, per the
correction's own sequencing design) returned `503` consistently across
three separate browser tabs, on every genuinely fresh full page load.
Extensive attempts to reproduce it any other way all succeeded:

- 15+ direct `curl` calls, including explicit CORS preflight simulation
  and true 3-way concurrency (`GET`/`GET`/`POST` fired together via
  backgrounded shell jobs), all `204`.
- Manual `fetch()` calls from the browser's own JS console — including
  one replaying the exact `GET`-then-`POST` sequence with a forced,
  never-before-seen preflight header — all `204`.
- A client-side (SPA) route change back to the brief, which happened to
  fire the `POST` *before* a slow fresh `GET` resolved (using cached
  query state), also succeeded.

The one property every failure shared and every success lacked: a
`POST` immediately following a real, freshly-completed `GET` whose
response body was large (the first-ever-view fallback pulls in a wide
window — 621 historical-intelligence issuers, measured at 3.5MB).
Diagnosis: the backend runs as a single Uvicorn worker
(`backend/railway.toml`, no `--workers` flag); serializing a
multi-megabyte Pydantic response is synchronous, CPU-bound work that
can transiently occupy the single worker's event loop, and a new
request landing on the same reused keep-alive connection during that
window can be rejected by Railway's edge with a `503` — consistent with
curl never reproducing it (separate process invocations rarely reuse a
connection across commands) and manual same-page `fetch()` calls never
reproducing it either (issued after the page had already fully settled,
never immediately trailing a fresh multi-megabyte response).

**Fix**

Capped the number of issuer-grouped developments actually *returned* in
`new_developments`/`historical_intelligence` to 100 each
(`_ISSUER_DISPLAY_CAP`), computed after severity-ranking so the most
consequential issuers are never the ones cut — while
`issuers_with_developments`/`historical_intelligence_issuer_count`
remain the true, uncapped totals, so a capped display never
misrepresents how much is actually new. Verified locally against the
same real large-window scenario (forced via the same view-lookup
monkeypatch the test suite uses): response size dropped from 3.5MB to
727KB. Recorded as new Technical Debt (TD-019) rather than treated as
fully resolved — this mitigates the specific endpoint, not the
underlying single-worker/synchronous-serialization exposure, which
could recur on a different sufficiently large future response.

**Files Modified**

- `backend/app/services/morning_brief_service.py` — `_ISSUER_DISPLAY_CAP`.
- `PLAN.md` — TD-019 added.

**Test Results**

- Backend: full suite re-run clean after the change (397 passed).
- `ruff check` / `black --check` / `mypy app` — clean.
- `pre-commit` — clean.
- Verified locally: real large-window payload 3.5MB -> 727KB, true
  counts unaffected.

**Deployment Validation**

Recorded in a follow-up entry once pushed, deployed, and re-verified
live that the `503` no longer reproduces on a fresh page load.

**Problems Encountered**

The `503` itself — see Investigation above. Root-caused via systematic
elimination (curl, concurrent curl, manual fetch, forced preflight,
exact-sequence replay) rather than guessed at or dismissed as
"probably transient." The eventual explanation was corroborated, not
just plausible: it was the *only* hypothesis consistent with every
success and every failure observed, and the fix it implied (reduce
response size) produced a large, real, measured reduction.

**Solutions**

Direct browser-based production verification (not just passing tests)
caught this a third time in the same milestone — reinforcing the same
lesson as the two prior corrections: an implementation can be correct
in isolation and still fail under real conditions that isolated testing
doesn't reproduce.

**Remaining Work**

- TD-019 (new): single-worker/synchronous-serialization exposure — this
  endpoint is mitigated, the underlying architectural exposure is not.

**Git Commit Hash**

`307ca17`

**Approximate Time Spent**

~45 minutes (live reproduction, systematic elimination of hypotheses,
fix, verification).

---

## 2026-08-09 — Milestone 7.5.2 (third correction): honest re-diagnosis of the `503`, retry mitigation

**Summary**

Re-verified the response-size fix (`307ca17`) against production and
found it did **not** resolve the `503` — a direct, live re-test with a
now-tiny (1106-byte) `GET /api/morning-brief` response still reproduced
the exact same failure on a fresh browser page load. The payload-size
hypothesis from the prior entry is disproved. Rather than claim a fix
that didn't work, this entry corrects the record and ships an honest
mitigation: a safe retry.

**Re-investigation**

With the capped response deployed and confirmed live-small, a fresh
page load in a fourth separate tab still produced `GET 200` / `POST
503`. Further checks: fetched and grepped the deployed JS bundle
directly (`curl` + `grep` against the live Vercel asset) to rule out a
stale-build or bundling artifact — the request construction matches the
source exactly. Every manual/scripted reproduction attempt (curl,
concurrent curl, manual same-page `fetch()`, forced-fresh-preflight
`fetch()`) continued to succeed; only a genuine fresh browser page load
fails, and every retry — manual or automated — succeeds. No further
hypothesis was confirmable from this environment (no access to
Railway's own edge/request logs). Recorded honestly as **not
conclusively root-caused**, correcting the prior entry's payload-size
conclusion rather than letting an unverified fix stand undisputed in
the record.

**Mitigation shipped**

`useRecordMorningBriefView` now retries twice with a 1s delay — safe,
since `record_brief_view` is idempotent by construction (a retry either
finds the gap already advanced, a no-op, or genuinely records the
view). Verified live: a manual 3-call retry loop against the production
endpoint succeeded 3/3. This does not block core functionality — `GET
/api/morning-brief` has never failed in any test, live or scripted; a
failed `POST /view` only means the boundary doesn't advance that one
visit, self-healing on the next successful call (same session, on
retry, or next real visit).

**Files Modified**

- `web/src/queries/useMorningBrief.ts` — `useRecordMorningBriefView`
  retry.
- `PLAN.md` — TD-019 corrected: response-size cap kept (good practice
  regardless) but explicitly no longer claimed as the fix; retry
  recorded as the actual mitigation; root cause recorded as open, not
  resolved.

**Test Results**

`tsc -b` / `eslint` / `prettier --check` — clean. No backend change this
pass (frontend-only).

**Problems Encountered**

The real problem here was almost documenting a fix that didn't actually
work — caught only by re-testing the *specific claim* ("payload size is
the cause") against production after deploying it, rather than trusting
the plausible-sounding investigation from the previous entry. A
diagnosis that explains every observation is still a hypothesis until
the fix it implies is independently re-verified.

**Solutions**

Re-tested the exact claim in production before accepting it. When it
failed, corrected the documentation rather than leaving a disproved
conclusion in the permanent record, and shipped a mitigation whose
effectiveness (retry succeeds) was itself verified live rather than
assumed.

**Remaining Work**

- TD-019 (updated): `POST /api/morning-brief/view`'s intermittent `503`
  on fresh browser page loads remains **not root-caused** — mitigated
  via retry, which is empirically reliable but not an explanation.

**Git Commit Hash**

`9218743`

**Approximate Time Spent**

~30 minutes (re-verification, retry mitigation, honest documentation
correction).

---

## 2026-08-09 — Milestone 7.5.2 (fourth correction): TanStack Query mutation retry didn't fire; replaced with a direct retry

**Summary**

Live-verified the retry mitigation from the previous entry
(`useMutation({retry: 2})`) against production and found it did not
actually retry: the Resource Timing API showed exactly one network
request for `POST /api/morning-brief/view` regardless of the `503`,
even though the deployed bundle was confirmed (via direct `grep` of the
live Vercel asset) to contain the correct `retry:2,retryDelay:1e3`
configuration. A second real, live-caught surprise in the same
investigation. Replaced with a direct, manual retry loop that doesn't
depend on TanStack Query's mutation retry mechanism at all.

**Fix**

`recordMorningBriefView` (`web/src/api/filingMonitor.ts`) now retries
up to 3 attempts with a 1-second delay, implemented as a plain
try/catch loop around `apiFetch`. `useRecordMorningBriefView`'s own
`retry` option was removed (dead/misleading now that the real retry
lives in the API function). Verified the retry loop's mechanics
directly in the browser console against the live production endpoint
before shipping.

**Files Modified**

- `web/src/api/filingMonitor.ts` — `recordMorningBriefView` direct retry.
- `web/src/queries/useMorningBrief.ts` — removed the ineffective
  `useMutation` retry option.
- `PLAN.md` — TD-019 updated with the TanStack Query retry finding.

**Test Results**

`tsc -b` / `eslint` / `prettier --check` / `vitest run` (71 passed) —
clean. No backend change this pass.

**Problems Encountered**

TanStack Query v5's `useMutation({retry: N})` did not cause a retry in
this real production scenario, despite being documented, standard
behavior and despite the config being verifiably present in the
deployed bundle. Root cause of *that* not investigated further (out of
proportion to this milestone's scope) — recorded as an open sub-item of
TD-019 rather than either silently dropped or exhaustively chased.

**Solutions**

Verified the mitigation's actual effect (via Resource Timing API showing
request count, not just "no visible error") rather than trusting that a
correctly-configured option must be working. Replaced it with a
mechanism simple enough to verify directly.

**Remaining Work**

- TD-019 (updated): `POST /api/morning-brief/view`'s `503` remains not
  root-caused; mitigated via a direct, verified retry. Why TanStack
  Query's own mutation retry didn't fire is a separate, also-unresolved
  question noted for anyone picking this up later.

**Git Commit Hash**

`e8a70ff`

**Approximate Time Spent**

~20 minutes.

---

## 2026-08-09 — Milestone 7.5.2 (fifth correction): business-day research-cycle semantics, not page views

**Summary**

Same-day, final explicit follow-up direction for this milestone: even
the user-relative `morning_brief_view` boundary (the first correction,
above) was still the wrong business concept. Direct instruction: "opening,
refreshing, closing, or revisiting Morning Research Brief must NEVER
alter the comparison window" — a page view is not a research boundary,
a completed business-day research cycle is. Corrected the brief's
definition to "what materially changed during the latest completed
business-day research cycle, compared with the preceding completed
business-day research cycle?" — e.g., for the currently completed Aug 7
cycle: "Latest research day: Aug 7, 2026 · Compared with: Aug 6, 2026,"
unchanged by any number of page opens, and unchanged on a weekend
(Aug 8/Aug 9) until a new business-day cycle actually completes.
`morning_brief_view` served no remaining purpose once period calculation
stopped depending on it, so it — and its only writer, `POST
/api/morning-brief/view` — were removed entirely, closing both TD-018
and TD-019 by removal rather than by further patching.

**Implementation**

- `DailyRunSummary` (`app/schemas/filing_monitor.py`) gains a
  `research_day: date` field — the real-world business day a daily run's
  data represents, distinct from `started_at`'s wall-clock execution
  time. For `market_discovery_run` this is `window_start_date` directly;
  `filing_monitor_run` has no window fields, so
  `_filing_monitor_research_day` derives it from `previous_watermark`'s
  date in America/New_York, falling back to `started_at`'s date only if
  no watermark exists.
- `app/services/morning_brief_service.py` rewritten around two new pure,
  DB-independent functions: `_previous_business_day` (strictly before a
  given date, Mon-Fri only, skips weekends — Friday's preceding day is
  Thursday, Monday's is the prior Friday) and `_most_recent_business_day`
  (a date itself if a weekday, else walks back to the most recent
  Friday). `_resolve_research_cycle` determines `latest_research_day`
  from the latest successful daily run's `research_day` (`is_fallback =
  False`), or, only when no successful daily run has ever completed,
  falls back to `_most_recent_business_day(today)` (`is_fallback =
  True`) — reachable only once, on a genuinely empty deployment.
  `preceding_research_day` is always `_previous_business_day
  (latest_research_day)` — computed by calendar arithmetic, never by
  requiring a second real run to exist, so even the very first
  completed daily run already has a well-defined comparison. `since`
  (the alert `triggered_since` boundary) is midnight America/New_York on
  `latest_research_day`; `as_of` is `datetime.now(UTC)` at read time,
  clearly separated in the schema from the (now non-side-effecting)
  window fields so a reader can't mistake "when I looked" for "what
  period this covers." `get_morning_brief` is now a fully pure function
  with zero side effects — no view recording, no write path at all.
  All of `MIN_VIEW_GAP`, `_previous_business_day_morning_boundary` (the
  first correction's version), `_resolve_period_start`,
  `_should_record_new_view`, and `record_brief_view` were deleted, not
  deprecated in place.
- `app/schemas/morning_brief.py`: `MorningBriefSummary.period_start`/
  `period_start_is_fallback`/`period_end` replaced with
  `latest_research_day`/`preceding_research_day`/
  `research_cycle_is_fallback`/`as_of`. Docstrings rewritten to state
  explicitly that these values can only change when a new successful
  daily run completes, never on read.
- `morning_brief_view` removed outright: deleted
  `app/models/brief_view.py`, `app/domain/brief_view.py`,
  `app/repositories/brief_view_repository.py`; removed the import from
  `app/models/__init__.py`; removed `POST /api/morning-brief/view`
  from `app/api/routes/morning_brief.py` (only `GET` remains).
  Migration `0013` drops the `morning_brief_view` table (with a full
  `create_table` in `downgrade()` for reversibility). Confirmed, before
  writing the migration, that nothing else in the codebase ever read
  `morning_brief_view` (no "unread" badge, no other UX consumer) — its
  only purpose was the period-boundary calculation this correction
  removes. Applied live against the shared Supabase project;
  `alembic check` confirms zero new upgrade operations.
  `collection_membership.updated_at` (also from migration `0012`) is
  untouched — still needed for membership-upgrade detection.
- Frontend: `web/src/api/filingMonitor.ts` updated field names, removed
  `recordMorningBriefView`; `web/src/queries/useMorningBrief.ts`
  simplified to a bare `useQuery`, `useRecordMorningBriefView` deleted;
  `web/src/pages/MorningResearchBriefPage.tsx` lost its view-recording
  `useEffect`/`useRef`; `web/src/components/BriefSummaryBar.tsx`
  rewritten to render "Latest research day: {date} · Compared with:
  {date}" (or the fallback message when `research_cycle_is_fallback`)
  plus a separate "Data as of {as_of}" line, so the *window* and the
  *read time* are visually distinct. The already-built product-focused
  UI (issuer-grouped developments, severity ranking, new-vs-historical
  partitioning, `RunDetailsPanel` behind "Show run/data details") is
  otherwise unchanged.

**Files Created**

- `backend/alembic/versions/0013_drop_morning_brief_view.py`
- `backend/tests/unit/test_research_cycle_boundary.py`

**Files Deleted**

- `backend/app/models/brief_view.py`, `backend/app/domain/brief_view.py`,
  `backend/app/repositories/brief_view_repository.py`
- `backend/tests/unit/test_morning_brief_boundary.py` (superseded by
  `test_research_cycle_boundary.py` — the old boundary logic it tested
  no longer exists)

**Files Modified**

- `backend/app/schemas/filing_monitor.py` — `DailyRunSummary.research_day`.
- `backend/app/schemas/morning_brief.py` — `MorningBriefSummary` field
  replacement, docstring rewrite.
- `backend/app/services/morning_brief_service.py` — business-day-cycle
  resolution logic, `record_brief_view`/view-gap logic removed.
- `backend/app/api/routes/morning_brief.py` — `POST /view` removed.
- `backend/app/models/__init__.py` — `brief_view` import removed.
- `backend/tests/integration/test_morning_brief_service.py` — rewritten
  around real seeded daily runs and the new field names.
- `web/src/api/filingMonitor.ts`, `web/src/queries/useMorningBrief.ts`,
  `web/src/pages/MorningResearchBriefPage.tsx`,
  `web/src/components/BriefSummaryBar.tsx`,
  `web/src/pages/MorningResearchBriefPage.test.tsx`.
- `PLAN.md` — TD-018/TD-019 marked resolved by architecture change (not
  by adding auth or by root-causing the `503`); Milestone 7.5.2's Next
  Immediate Goal narrative extended with this correction.

**Database Changes**

Migration `0013`: drops `morning_brief_view` (reversible —
`downgrade()` recreates it). No other schema change; `research_day` is
a computed/derived field, not a new column.

**API Endpoints Removed**

`POST /api/morning-brief/view` — removed entirely, not deprecated.
`GET /api/morning-brief`'s response shape changed (not backward
compatible with the pre-correction shape); the same milestone's own
frontend is the only consumer, updated in the same change.

**Tests Added**

- `tests/unit/test_research_cycle_boundary.py` (6 tests):
  `_previous_business_day` (Friday→Thursday, Monday→Friday skipping the
  weekend, midweek) and `_most_recent_business_day` (weekday-is-itself,
  Saturday→Friday, Sunday→Friday) — using real 2026 calendar dates
  (2026-08-07 confirmed to be a genuine Friday).
- `tests/integration/test_morning_brief_service.py` rewritten (9 tests):
  Friday/Monday research-day comparisons, a first-ever-cycle fallback
  (via monkeypatching `_latest_successful_daily_run`, since the shared
  production database already has real daily runs and can never be
  assumed empty), old-filing-vs-new-event partitioning, a universe
  membership change, no material changes, and two idempotency proofs —
  three repeated calls to `get_morning_brief` return byte-identical
  windows, and only a genuinely new, later-completing daily run (never
  a repeated read) ever advances the window.
- `web/src/pages/MorningResearchBriefPage.test.tsx`: a new test
  asserting the page never calls any view-recording endpoint at all
  (`"recordMorningBriefView" in filingMonitorApi === false`), and a new
  idempotent-refresh test that mounts, unmounts, and remounts the page,
  asserting an identical comparison-window string both times.

**Test Results**

- Backend: full suite 396 passed (213.41s); targeted morning-brief
  suite (6 unit + 9 integration) 15 passed in 9.21s in isolation.
- Frontend: 72 passed across 12 files.
- `ruff check` / `black --check` / `mypy app` (154 source files) —
  clean. `eslint` / `tsc -b` / `prettier --check` — clean. Production
  build succeeds (`vite build`, pre-existing >500kB chunk-size warning
  only, unrelated to this change). Backend imports and boots (24 routes).
- `alembic check` against the live shared Supabase project — zero new
  upgrade operations; `alembic current` confirms `0013 (head)`.

**Problems Encountered**

None new this pass — this correction was primarily a semantic/design
change (page-view boundary → business-day-cycle boundary) plus a
deletion (unused `morning_brief_view` architecture), not a bug fix. The
main risk — accidentally leaving `preceding_research_day` dependent on
a second real run existing, which would break on the very first daily
run ever completed — was avoided by deriving it from calendar
arithmetic instead, verified directly by
`test_first_ever_research_cycle_uses_most_recent_business_day_fallback`.

**Solutions**

N/A (no bug this pass).

**Remaining Work**

- TD-018 (Morning Brief boundary is not per-user): **resolved by
  architecture change**, not by adding authentication. A research cycle
  is inherently a shared, system-wide concept, not a per-user
  preference, so the per-user-scoping concern this debt item described
  no longer applies to period calculation. Per-user *read/unread* state
  remains a legitimate, currently-unimplemented future feature — if
  ever built, it must not be allowed to influence period semantics
  again.
- TD-019 (`POST /morning-brief/view`'s intermittent `503`): **resolved
  by removing the endpoint**, not by root-causing the `503`. The
  underlying cause — including why TanStack Query's own mutation retry
  never fired in production — was never conclusively identified. This
  is recorded here as a permanent, honest historical note per explicit
  instruction not to silently drop it from the record, not because it
  was solved.
- Milestone 7.5.3 (Historical Discovery Coverage Repair) — still
  planned, not started, still deliberately out of scope. Not to begin
  until the user explicitly approves it.

**Deployment Validation**

Pushed to `origin/main` (`eafb77e`, then `7d06b91` docs follow-up).
Railway's redeploy was caught mid-transition on the first post-push
check — `GET /api/morning-brief` returned a real `500` for a few
minutes because the *old* deployed code was still running against the
already-migrated database with `morning_brief_view` dropped (migration
`0013` had been applied live ahead of the code push). Polled every 15s
until the endpoint returned `200`; resolved once Railway's build/deploy
completed, with no manual intervention required. Live-verified against
production afterward:

- `GET /api/morning-brief` (direct `curl`, three separate requests):
  `latest_research_day: "2026-08-07"`, `preceding_research_day:
  "2026-08-06"`, `research_cycle_is_fallback: false` — identical across
  all three calls.
- `POST /api/morning-brief/view` → `404` (route genuinely removed, not
  just erroring — direct proof TD-019's endpoint no longer exists).
- Browser walkthrough (Chrome, production Vercel frontend against
  production Railway API): `https://nexus-credit-intelligence.vercel.app/research-brief`
  renders "Latest research day: Aug 7, 2026 · Compared with: Aug 6,
  2026" — an exact match to the milestone's required example. Reloaded
  the page fully (fresh navigation, not a soft refresh) and confirmed
  byte-identical text after reload. Network tab showed exactly one
  request to `/api/morning-brief` (200) and zero requests to `/view` —
  confirming the frontend no longer calls the removed endpoint at all,
  not just that the call would fail gracefully. Console showed zero
  errors. Expanded "Show run/data details" and confirmed the secondary
  operational panel (`Latest successful daily run`, `Run window: Aug 7,
  2026 – Aug 8, 2026`, universes/issuers monitored, filing/evidence
  counts) still renders correctly, unaffected by the primary summary's
  redesign.
- Note: browser verification was performed on 2026-08-08 (a Saturday,
  per this entry's own timestamp) — real-world confirmation, not just a
  seeded-test one, that the brief correctly continued showing the Aug
  7/Aug 6 business-day comparison on a non-business day rather than
  computing an artificial empty weekend period.

**Git Commit Hash**

`eafb77e` (implementation), `7d06b91` (docs: commit-hash + PLAN.md
follow-up)

**Approximate Time Spent**

~2 hours (design correction, service/schema/route rewrite,
`morning_brief_view` removal and migration, full test suite rewrite,
documentation, full verification pass, deployment, and live production
browser verification).

---

## 2026-08-09 — Milestone 7.5.3: Historical Discovery Coverage Repair — three live incidents, AI cost-control correction (backfill itself not yet completed)

**Summary**

Milestone 7.5.3 set out to re-run the 2026-01-01→2026-08-06 historical
discovery window with TD-014's corrected SEC full-text-search `forms`
behavior active. Three live attempts against production (all 2026-08-09)
each ended in a real incident rather than completion, and the milestone
is paused, by explicit user direction, before the historical backfill
itself — this entry documents the incidents, the CourtListener fix, and
the substantial AI cost-control/observability/routing correction built
and tested in response. **The Jan–Aug backfill has not yet run to
completion.**

**Incident 1 — a launch-time operator error (self-resolved, no data risk)**

The first launch attempt appeared as two concurrent `python.exe`
processes under Task Manager (a git-bash `$!` PID-tracking artifact, not
a real duplicate worker — confirmed later to be a normal parent-launcher/
child-worker pair for this venv). Killed out of caution; verified via
direct query that only 6 candidates were actually processed under that
run id before termination, zero duplicate `(cik, accession_no)` pairs or
duplicate issuer CIKs anywhere in the database. The run row was closed
out honestly as `failed` with the real reconstructed counts (not zeros)
in its `error_summary`, matching this project's established "never
silently drop from the record" discipline. Relaunched cleanly.

**Incident 2 — the real CourtListener `Retry-After` defect**

The relaunched run hung for 39+ minutes with zero CPU movement and an
`idle in transaction` database connection. Initially suspected — at the
user's explicit prompt — as a Windows sleep/Modern-Standby artifact;
investigated via Windows event logs (no `Kernel-Power` sleep/wake events,
no reboot, sleep already disabled on the active power plan) and mitigated
with an explicit keep-awake helper (`SetThreadExecutionState`) before
relaunching a third time. The same stall reproduced identically with the
machine confirmed awake throughout, ruling out the environmental
explanation. A live `py-spy dump --pid <child> --locals` (installed
one-off for this diagnosis) captured the exact stack: the process was
inside `ThrottledHttpClient.get()`'s `time.sleep(self._retry_after_seconds(response))`
call, mid-retry against CourtListener's docket search after a `429`.
Root cause: `_retry_after_seconds` did a bare `float(header_value)` with
no upper bound — CourtListener's `Retry-After` header, whatever value it
actually sent, was trusted verbatim, and nothing capped the resulting
`time.sleep()`. **Fixed** (`backend/app/providers/base/http_client.py`):
RFC 7231-correct parsing of both valid `Retry-After` forms (delta-seconds
and HTTP-date, via `email.utils.parsedate_to_datetime`), plus a new hard,
configurable `max_retry_after_seconds` ceiling (`Settings.courtlistener_retry_after_max_seconds`,
default 60s) — beyond it, `get()` raises `RetryAfterTooLongError` instead
of sleeping. This project's existing per-issuer/per-provider isolation
(`enrichment_orchestrator.enrich_issuer`'s try/except) already converts
that into a `FAILED_RETRYABLE` status with a `next_retry_at`, so a
CourtListener stall can never again block the rest of a discovery batch.
9 regression tests added (normal/malformed/huge/HTTP-date/repeated-429),
including a live proof that a pathological `Retry-After` value now raises
in <1 second instead of sleeping for hours. The exact value CourtListener
actually sent during the real incident was never captured (the process
was killed via `py-spy`+`Stop-Process`, not instrumented mid-flight) —
recorded as TD-020, resolved by the ceiling regardless.

**Incident 3 — the user paused the milestone for AI cost control**

With the CourtListener fix applied, a fourth relaunch was in progress
(and itself hit the identical hang pattern a second time, still under
investigation) when the user paused Milestone 7.5.3 entirely: this
project's Anthropic spend had zero call/token/cost observability (TD-016,
open until this entry) and used Sonnet unconditionally for every AI
review regardless of task complexity — a historical repair over a
~600-candidate window could legitimately generate large, unbounded, and
completely unmonitored AI spend. The user required a full audit,
observability, hard budgets, and complexity-based Haiku/Sonnet routing
before any further live run.

**AI call-path audit (verified from code, not assumed)**

Traced every path that can reach `llm.complete()`. Exactly one function —
`app.ai.evidence_review.review_evidence_candidates` — ever calls it.
Exactly two real call sites existed before this correction:

1. `alert_synthesis_service.synthesize_alerts_from_evidence` (via
   `_synthesize_one_alert`) — gated by (a) `alert_repository.get_alert_by_bundle_key`
   (an already-alerted bundle is skipped before any AI involvement — the
   pre-existing idempotency guarantee that also protects against
   duplicate spend on a re-run) and (b) `check_send_to_llm` (licensed-data
   policy gate). Reached from **every** real workflow that creates
   evidence: `market_discovery_service.run_discovery` (discovery/backfill),
   `filing_monitor_service.run_monitor` (nightly monitor),
   `court_docket_service.sync_one_docket` (CourtListener docket sync,
   itself called from `attempt_auto_link` during enrichment and from the
   standalone `sync_court_dockets.py`/`link_court_dockets.py` scripts).
2. `app.scripts.reclassify_system_universes` — a one-off maintenance
   script (already run once for Milestone 7.5.1) that backfills
   `alert_event.issuer_is_subject` for pre-7.5.1 alerts, gated by
   "already backfilled" + the same policy gate.

**One real path was missed on the first audit pass and caught during
implementation**: `POST /api/filing-monitor/runs/trigger`
(`app/api/routes/filing_monitor.py`), an admin/demo-only, non-production-gated
endpoint that manually triggers `filing_monitor_service.run_monitor` —
constructed its own `LLMProvider` via `get_llm_provider` exactly like the
CLI scripts, and needed the identical `router` rewiring. Recorded here
honestly rather than silently absorbed into "the audit was complete."

**Built: `app/ai/model_router.py` — deterministic → Haiku → Sonnet routing**

- `ModelRouter.review_evidence`: (1) a deterministic floor — if every
  candidate's own Layer-1 confidence is below `ai_deterministic_confidence_floor`
  (default 0.5), no model is called at all; today's calibrated Layer-1
  rules all sit at ≥0.5, so this is currently a no-op against real data,
  not a lever tuned to cut recall — infrastructure for the future, tested
  honestly as such. (2) Definitive/high-impact categories
  (`universe_classification_service.definitive_evidence_types()` —
  Chapter 11, bankruptcy/receivership, plan-confirmed) go **straight to
  Sonnet, never through Haiku at all** — see the quality-validation
  finding below for why. (3) Everything else: Haiku first, escalating to
  Sonnet (bounded to exactly one attempt) only when Haiku's own call
  fails/returns unparseable JSON, or its reported `confidence` is below
  `ai_haiku_confidence_threshold` (default 0.75).
- `AiCallBudget`: one mutable tracker per run — `max_calls`/`max_cost_usd`/
  `max_sonnet_calls`, `None` = unlimited. `can_call()` is checked
  immediately before every provider call inside `ModelRouter`, never
  delegated to a caller, so no code path can bypass it. Once exhausted,
  a bundle that genuinely needed AI is `deferred` (no alert created at
  all, not a low-confidence deterministic alert masquerading as
  reviewed) — `alert_synthesis_service._synthesize_one_alert` now returns
  `None` in that case, and `synthesize_alerts_from_evidence` simply
  omits it from the created list, leaving it reachable by a future run
  with fresh budget via the same `bundle_key` idempotency check.
  Already-completed deterministic work is never rolled back.
- Model ids are entirely settings-driven (`Settings.ai_haiku_model_id`,
  `ai_sonnet_model_id`) — never hardcoded in business logic.
  `Settings.ai_routing_enabled=False` collapses to Sonnet-only (no Haiku
  attempt ever made), still fully budgeted and logged.
- New `ai_call_log` table (migration `0014`) — one row per real Anthropic
  request: model, route, routing reason, issuer/bundle id, input/output
  tokens, estimated cost (`app/ai/pricing.py`, an explicitly maintained,
  clearly-labeled-as-estimate model-pricing table), latency, success/
  failure, retry count, timestamp. `discovery_run_id`/`filing_monitor_run_id`
  are both nullable FKs (mirrors ADR-018's nullable-per-provider-FK
  pattern) — a call made outside either run context (the reclassify
  script) leaves both null. `ai_call_log_repository.aggregate_for_discovery_run`
  is the sole source of run-level usage reporting; nothing is duplicated
  onto `market_discovery_run` itself.
- `run_market_discovery.py`: new `--ai-mode {full,zero}` (zero-AI mode
  runs the full deterministic pipeline — SEC discovery, issuer
  resolution, filing ingestion, Layer-1 evidence extraction — with zero
  Anthropic calls, implemented as a `ModelRouter` with both providers
  `None`, so every AI-needing bundle is `deferred` rather than
  downgraded), `--max-ai-calls`/`--max-ai-cost-usd`/`--max-sonnet-calls`,
  and `--estimate-only` (a pre-run report using a sample of already-
  persisted `research_evidence.confidence` values to estimate "bundles
  needing no AI" vs. "bundles that would reach model review" — explicitly
  labeled a sample from existing data, never a precise forecast of a
  specific future live search's volume). Every run now prints full AI
  usage (total/Haiku/Sonnet calls, tokens, cost by model/operation,
  budget-blocked/deferred counts).

**Live quality validation — two real bugs found and fixed before any
production use**

Per explicit instruction, compared representative real production
Sonnet-reviewed alerts against the new routing behavior (7 cases: Chapter
11 true positive, Chapter 11 third-party false positive, going concern,
covenant/default stress, refinancing, liability-management, ambiguous
attribution) using real Anthropic calls (~$0.036 total, logged to
`ai_call_log` like any other real call):

1. **Haiku wraps JSON in a markdown code fence** despite the system
   prompt's explicit "no markdown" instruction — all 7 cases failed to
   parse on the first pass. Sonnet does not exhibit this. Would have
   made Haiku fail 100% of the time in production, silently escalating
   every single call to Sonnet and defeating the entire cost-saving
   purpose. **Fixed**: `app/ai/evidence_review.py` now strips a leading/
   trailing ` ``` ` fence (with or without a language tag) before
   `json.loads`.
2. **Haiku confidently (0.98) misclassified the Chapter 11 third-party
   case** — the exact EchoStar-subsidiaries-style attribution error
   Milestone 7.5.1 was built to catch — at a confidence above even the
   originally-planned stricter high-impact threshold, meaning a pure
   confidence-threshold escalation policy would not have caught it.
   **Corrected the policy**: high-impact categories now bypass Haiku
   entirely (see above) rather than trusting any Haiku confidence value.
   Re-validated after the fix: the same case now reaches Sonnet — but a
   **fresh Sonnet call also returned the same (arguably wrong, or at
   least differently-judged) answer** as the errant Haiku call, disagreeing
   with the original stored value. This means the mismatch is not a
   Haiku-specific reliability gap but genuine model non-determinism on a
   legitimately hard nested-subsidiary attribution judgment call — the
   routing correction (never trust Haiku on this category) is still the
   right conservative default, but does not fully close the underlying
   instability. Recorded honestly as TD-021, not overclaimed as fixed.

The other 5 of 7 cases matched the original Sonnet judgment correctly
(going concern, refinancing, liability-management, ambiguous-attribution
— which correctly escalated to Sonnet under the new policy — and the
Chapter 11 true positive).

**Files Created**

- `backend/alembic/versions/0014_ai_call_log.py`
- `backend/app/ai/model_router.py`, `backend/app/ai/pricing.py`
- `backend/app/domain/ai_call_log.py`, `backend/app/models/ai_call_log.py`,
  `backend/app/repositories/ai_call_log_repository.py`
- `backend/tests/integration/test_model_router.py` (13 tests),
  `backend/tests/unit/test_http_client_retry_after.py` (9 tests)

**Files Modified**

- `backend/app/config.py` — new AI routing/budget/CourtListener-ceiling settings.
- `backend/app/core/types.py` — `AiRoute`, `AiOperation` enums.
- `backend/app/providers/base/http_client.py` — `RetryAfterTooLongError`,
  RFC 7231-correct `Retry-After` parsing, `max_retry_after_seconds`.
- `backend/app/providers/courtlistener/client.py` — threads the ceiling through.
- `backend/app/ai/evidence_review.py` — markdown-fence stripping.
- `backend/app/ai/providers/base.py`, `backend/app/ai/providers/anthropic_provider.py` —
  `CompletionResponse.input_tokens`/`output_tokens`.
- `backend/app/ai/factory.py` — `get_llm_provider(..., model=...)` override,
  new `build_model_router`.
- `backend/app/services/alert_synthesis_service.py`,
  `backend/app/services/market_discovery_service.py`,
  `backend/app/services/filing_monitor_service.py`,
  `backend/app/services/court_docket_service.py`,
  `backend/app/services/enrichment_orchestrator.py`,
  `backend/app/services/filing_monitor_api_service.py`,
  `backend/app/api/routes/filing_monitor.py` — `llm: LLMProvider | None`
  replaced with `router: ModelRouter | None` throughout; `discovery_run_id`/
  `filing_monitor_run_id` threaded through for `ai_call_log` attribution.
- `backend/app/scripts/run_market_discovery.py` — full CLI rewrite (AI
  mode, budgets, estimate, usage reporting).
- `backend/app/scripts/run_overnight_filing_monitor.py`,
  `backend/app/scripts/sync_court_dockets.py`,
  `backend/app/scripts/link_court_dockets.py`,
  `backend/app/scripts/reclassify_system_universes.py` — routed through
  `build_model_router` instead of `get_llm_provider` directly.
- `backend/app/repositories/research_evidence_repository.py` —
  `sample_confidence_values` (pre-run estimate data source).
- `backend/tests/integration/test_market_discovery_service.py` — one
  existing test's fake `enrich_issuer_fn` updated for the new
  `discovery_run_id` keyword (caught by a full-suite rerun, not missed).

**Database Changes**

Migration `0014`: new `ai_call_log` table. Applied live against the
shared Supabase project; `alembic check` confirms zero drift.

**Tests Added**

22 new tests (13 `test_model_router.py`, 9 `test_http_client_retry_after.py`)
covering: deterministic floor, Haiku-only, confident-Haiku-skips-Sonnet,
ambiguous-Haiku-escalates, high-impact-always-Sonnet, failed-Haiku-escalates,
call/dollar/Sonnet-call budget enforcement, zero-AI mode, `ai_call_log`
field correctness, the reclassify operation logged distinctly,
already-reviewed-bundle makes zero further calls, and Retry-After
normal/malformed/huge/HTTP-date/repeated-429/ceiling-enforcement cases.

**Test Results**

Full backend suite: 418 passed (396 → 418, +22), including one real
regression caught by the full rerun (a pre-existing test's fake
`enrich_issuer_fn` needed the new `discovery_run_id` keyword — fixed).
`ruff check` / `black --check` / `mypy app` (159 source files) — clean.
`alembic check` — zero drift. Backend boots (24 routes, unchanged — this
correction is entirely backend, no frontend files touched).

**Problems Encountered**

Documented in full above (the launch-time PID artifact, the CourtListener
`Retry-After` stall, the two real bugs caught by live quality validation).
A meta-observation: three of this session's real findings — the
CourtListener stall's true cause, the Haiku markdown-fence bug, and the
Sonnet-also-disagrees subsidiary-attribution case — were each invisible
to static analysis, a passing test suite, or an initial design review,
and were only surfaced by actually running the real thing (a live
`py-spy` stack capture; a real Haiku API call; a real Sonnet API call)
and checking its output against ground truth rather than trusting the
design's own reasoning. Consistent with this project's recurring
discipline, restated once more.

**Remaining Work**

- The 2026-01-01→2026-08-06 historical backfill itself has **not yet
  run to completion** — this entry documents preparatory/corrective work
  only. Awaiting explicit user approval of an AI budget before restarting.
- TD-020 (CourtListener `Retry-After` defect): resolved by the fix; the
  exact value CourtListener sent during the live incident was never
  captured.
- TD-021 (model non-determinism on nested-subsidiary attribution): open,
  a product-policy question, not purely an engineering one.
- FAT Brands and Inotiv (2 of the 4 originally-cited TD-014 benchmark
  issuers) had not yet been discovered as of the last partial run;
  Bitcoin Depot Inc. and GoHealth, Inc. were confirmed found.
- Milestone 7.5.4/7.6/Milestone 8 explicitly not to begin.

**Git Commit Hash**

`bc7afd0`

**Approximate Time Spent**

~5 hours (three live incident investigations and recoveries, CourtListener
root-cause via `py-spy` and fix, full AI call-path audit, model-routing/
budget/observability design and implementation across ~20 files, live
quality validation with two real bugs found and fixed, 22 new tests,
full verification pass, documentation).

---

## 2026-08-10 — Milestone 7.5.3 zero-AI historical ingestion confirmed complete; resumption of normal daily production research cycle; SEC query-loop reliability fix; Morning Research Brief event-date classification fix; DST-safe nightly scheduler wrapper

**Context**

Picking back up after the prior entry's pause. This entry covers four
distinct pieces of work performed in one continuous session at the
user's explicit direction: (1) documenting the Milestone 7.5.3 zero-AI
historical backfill's real completion, which happened via a separate
session this environment has no transcript access to; (2) resuming and
running the normal daily/delta production research cycle for 2026-08-10;
(3) a real production bug found and fixed in Morning Research Brief's
classification logic; (4) implementing (but not yet Railway-deploying) a
DST-safe nightly scheduler.

**Part 1 — Milestone 7.5.3 Zero-AI Historical Ingestion (documented from database inspection)**

Direct inspection of `nexus.market_discovery_run` found 5 `mode=backfill`
attempts (window `2026-01-01`→`2026-08-06`) between 2026-08-09 03:26 UTC
and 2026-08-10 08:41 UTC — user-confirmed as the authorized zero-AI
(`--ai-mode zero`, $0 Anthropic spend) historical coverage re-run,
approved in a separate session. 4 attempts crashed on genuine
infrastructure issues (2 SEC-side transient `500`s on the top-level query
loop — see TD-022 below; 2 previously-undocumented stalls — a DB
idle-in-transaction hang and an SEC-document-fetch hang, both safely
killed and resumed via existing `(cik, accession_no)`/`rule_version`
idempotency, zero corruption confirmed via direct query each time); the
5th completed with 0 errors. Final state: 2,652 issuers (from 787),
28,170 SEC filings (from 7,243), 22,252 research evidence rows (from
6,239), 3,123 alerts (from 2,212), 4,727 `market_discovery_candidate`
rows (from 891) — all real, zero duplicate `(cik, accession_no)` pairs or
issuer CIKs. `ai_call_log` confirmed unchanged at 8 rows across all 5
attempts — $0 Anthropic spend maintained exactly as required. AI review
of the resulting deferred bundles (evidence that needed model judgment
but received none, per zero-AI mode's design) remains separate,
still-deferred work — not run by this pass, not auto-triggered by
anything.

**Part 2 — Resuming the Normal Daily/Delta Cycle for 2026-08-10**

Before running anything, inspected `market_discovery_repository.
get_latest_successful_run` (used by `delta` mode to compute its own
resume watermark) and found it does not exclude `mode=backfill` — by
design, unlike `get_latest_successful_daily_run` (Morning Brief display
only). Because the Part 1 backfill's declared window ended `2026-08-06`
but it didn't actually complete until `2026-08-10`, and `resulting_
watermark` for a successful run is stamped with real completion time
(`datetime.now(UTC)`), a bare `--mode delta` invocation would have
silently skipped Sunday `2026-08-09` entirely (Saturday `2026-08-08` was
already covered by the real `2026-08-07`→`08` delta run). See TD-023.

Corrected with an explicit `--mode backfill --start 2026-08-09 --end
2026-08-10` catch-up run (not counted as a Morning Brief research day,
since `backfill` mode is excluded from the daily-run boundary), followed
by a `--mode delta` labeling pass so the cycle is correctly recorded as
`2026-08-10` from the product's perspective. AI budget for the whole
night, explicitly user-authorized: max cost $2.00, max calls 300, max
Sonnet calls 75 — enforced proactively by the existing `AiCallBudget`/
`ModelRouter` (verified: `deferred_no_budget=0`, `calls_blocked_by_
budget=0` on every invocation; budget was never actually exhausted).
Each retry's own budget was computed as the *remaining* allowance after
subtracting all prior spend that night, so the cumulative total across
every invocation never exceeded the authorized $2.00/300/75 ceiling.

Real SEC-side transient `500` errors were hit repeatedly overnight (an
elevated error rate specific to that night, not a code defect) —
`market_discovery_service.run_discovery`'s top-level query loop had no
per-query isolation, so the first two attempts crashed entirely (8
candidates processed before each crash, both times leaving the run row
stuck at `status='running'` with no error recorded). Rather than keep
blindly retrying, applied a scoped fix (TD-022, code below) mirroring the
existing per-candidate/per-issuer isolation one level down: a query-level
failure is now caught, counted as an error, and the loop continues to
the next query. After the fix, every subsequent run degraded gracefully
instead of crashing.

| Run | Mode | Window | Status | Result |
|---|---|---|---|---|
| Catch-up attempt 1 | backfill | Aug 9–10 | crashed (pre-fix, uncaught SEC 500) | 8 candidates |
| Catch-up attempt 2 | backfill | Aug 9–10 | crashed (pre-fix, uncaught SEC 500) | 8 candidates |
| Catch-up attempt 3 (post-fix) | backfill | Aug 9–10 | `completed_with_errors` (6 isolated SEC 500s out of ~64 query/form combos) | **281 candidates, 119 existing + 125 new issuers, 537 evidence, 177 alerts** |
| Delta labeling, 3 attempts | delta | Aug 10 | 2× `completed_with_errors`, 1× **`success`** | Final: `8a67a94a-bfc7-4453-a68b-f9ee5229dd83`, window `2026-08-10`→`2026-08-11`, 0 errors, 264 candidates all idempotent-skipped (0 new — confirms no duplicate processing) |

Providers: CourtListener 2 `failed_retryable` / 20 `no_data` / 201
`unsupported`; OpenFIGI 62 `complete` / 14 `failed_retryable` / 147
`no_data`; SEC 148 `complete` / 27 `no_data`. Cumulative AI usage across
the whole night: 291 calls (220 Haiku, 70 Sonnet, 1 failed/unattributed),
$1.044921 total — well within the $2.00/300/75 authorization. Residual
gap, honestly reported: 6 of ~64 query/form combinations in the catch-up
run hit unrecoverable transient SEC `500`s and were not retried further
that night to conserve budget/time (TD-022 records this).

**Part 3 — Morning Research Brief classification bug found and fixed**

After the corrected run, `GET /api/morning-brief` showed
`latest_research_day=2026-08-10`/`preceding_research_day=2026-08-07`
correctly, but `new_developments: 0` and `no_material_changes: true`
despite 225 real alerts having just been created (177 counted by the
run's own loop; TD-017's known undercount explains the gap — the
enrichment orchestrator's own evidence/alert creation isn't tallied by
the discovery loop's local counters). Root cause, found by inspection
before any fix: `alert_event.is_backfill` — set purely from the
*invocation mode* (`mode is FilingMonitorRunMode.BACKFILL`) — was being
used as the sole signal for "is this a new development or historical
intelligence" in `morning_brief_service.get_morning_brief`. The Aug
9–10 catch-up window necessarily used `--mode backfill` (since `--mode
delta` cannot accept an explicit `--start`/`--end`), so all 225 of its
alerts — genuinely current Aug 9–10 activity — were mechanically
mislabeled `is_backfill=True` and filed as historical.

Investigated the real split before touching any production data, per
explicit instruction: of 225 alerts from the catch-up run, 178 had
`as_of_date=2026-08-10`, 47 had `as_of_date<=2026-08-07`, 0 missing/
ambiguous. Spot-checked both groups against real SEC filing text —
correct in both directions (e.g. a same-day loan-maturity-extension
alert dated Aug 10 vs. a "Term Loan Repricing Amendment executed in
February 2026" alert dated Aug 6).

Fixed by decoupling classification from `is_backfill` entirely:
`morning_brief_service._is_new_development` now classifies purely by
`alert.as_of_date` relative to the research-cycle boundary
`(preceding_research_day, latest_research_day]` — `is_backfill` is left
completely untouched as ingestion-mode provenance (still exposed on
`AlertRow`), never repurposed or removed. The same event-date-vs-
creation-time issue existed in `RunDetails.new_sec_filings`/
`new_court_events`/`new_research_evidence` (all counted by `created_at`
relative to a specific run's `started_at`, which is why they showed 0
too) — fixed with three new repository functions
(`sec_filing_repository.count_filings_by_filing_date_between`,
`court_docket_entry_repository.count_entries_by_entry_date_between`,
`research_evidence_repository.count_evidence_by_source_date_between`,
the last joining through `sec_filing.filing_date`/`court_docket_entry.
entry_date` since `research_evidence` itself carries no date column per
ADR-018), all scoped to the same `(preceding_research_day,
latest_research_day]` window. The old `created_at`-based functions are
left in place, unused by the Brief but still available for any caller
that genuinely wants a discovery-time metric — not deleted, per explicit
instruction not to repurpose existing signals globally.

Verified against real production data (read-only, before any commit):
`issuers_with_developments` 0→191, `severity_counts` 0/0/0→65/26/110,
`no_material_changes` true→false, `historical_intelligence_issuer_count`
254→93, `run_details.new_sec_filings` 0→373,
`run_details.new_research_evidence` 0→581.

9 new regression tests added to `test_morning_brief_service.py`: Saturday
event → new development, Sunday event → new development, older June
filing discovered Monday → remains historical, backfill-mode invocation
does not force an in-window event to historical, delta-mode invocation
does not force an old event to new (the reverse-direction proof), counts
and displayed cards use identical event-date semantics (cap-aware, since
the live shared database now has 191 real new-development issuers
against a 100-issuer display cap), and `RunDetails.new_sec_filings` uses
event-date not creation-time. All 7 existing Morning Brief tests
continue passing unchanged.

**Part 4 — DST-safe nightly scheduler (implemented, not yet Railway-deployed)**

`app.scripts.run_nightly_scheduled_discovery` (new): a thin wrapper
intended to be invoked by **two** Railway Cron triggers nightly (`0 2 *
* *` and `0 3 * * *` UTC — Railway Cron has no timezone parameter,
verified against Railway's own docs, not assumed). The wrapper computes
the real `America/New_York` wall-clock hour via `zoneinfo` (the actual
IANA timezone database — the 2026 US DST transition dates are never
hardcoded anywhere) and only the trigger landing on hour 22 (10 PM)
launches the real `run_market_discovery --mode delta` subprocess; the
other exits immediately as a no-op. Before launching, it also checks
`market_discovery_repository.get_latest_successful_daily_run` — the same
function the Brief itself uses — and no-ops if a daily cycle already
completed for the current Eastern date, layered on top of Railway's own
overlapping-execution skip. `TZ=America/New_York` is set for the
subprocess so the underlying script's naive `date.today()` also resolves
to the correct Eastern business date rather than a container's default
UTC (live-verified locally: `TZ=UTC` shifted `date.today()` to the next
calendar day at 11:14 PM ET — the exact failure mode this guards
against). Recurring nightly AI budget defaults to tonight's authorized
$2.00/300/75, overridable via `NIGHTLY_MAX_AI_COST_USD`/
`NIGHTLY_MAX_AI_CALLS`/`NIGHTLY_MAX_SONNET_CALLS` env vars.

10 new tests: 7 pure-logic unit tests for the `should_run` decision
function (EDT, EST, wrong-trigger no-op in both directions, a real
DST-transition proof via `zoneinfo` rather than hardcoded dates,
duplicate-day no-op, prior-day completion does not block tonight) plus 3
integration tests for `main()` (valid invocation launches exactly one
subprocess, already-completed day no-ops, wrong hour no-ops).

Railway cron trigger creation itself was **not performed** — this
working environment has no Railway CLI/dashboard access. See KI-002 for
the exact operator steps to activate it.

**Technical Debt**

- **TD-022 (new)**: `market_discovery_service.run_discovery`'s top-level
  SEC full-text-search query loop had no per-query error isolation — one
  transient SEC `500` crashed the entire run, stranding its
  `market_discovery_run` row at `status='running'` forever. Fixed with a
  scoped `try`/`except` around the search call (mirrors the existing
  per-candidate/per-issuer isolation pattern), tested
  (`test_query_level_failure_does_not_crash_the_run`). Observed 4 times
  total across tonight's work (2 crashes pre-fix, plus 6+2 isolated
  post-fix occurrences that no longer crashed the run).
- **TD-023 (new)**: `get_latest_successful_run`'s `resulting_watermark`
  for a `backfill`-mode run reflects real completion time, not its
  declared window end — correct by design for most cases, but creates a
  gap when a backfill's declared window and its real completion time
  diverge significantly (exactly what happened here). Not fixed in
  `market_discovery_service`/`market_discovery_repository` itself this
  pass (a genuine design tradeoff between two valid interpretations,
  deserving its own explicit decision) — worked around with one manual
  explicit-window catch-up run.

**Tests Added**

20 new tests total: 9 `test_morning_brief_service.py` (event-date
classification), 1 `test_market_discovery_service.py` (TD-022 query
isolation), 7 unit + 3 integration for the nightly scheduler wrapper.

**Test Results**

Full backend suite: 456 passed (449 → 456, +7 net; some new tests
replaced/extended existing coverage). `ruff check` / `black --check` /
`mypy` — clean on every touched file. One test (`test_valid_invocation_
launches_exactly_one_delta_run`) initially collided with tonight's own
real production data (hardcoded a near-term date that, after tonight's
real run, now genuinely has a completed daily cycle) — fixed by moving
to a date far enough in the future (2030) to never collide with real
data, same caution `test_daily_run_boundary.py` already documents for
this shared, real database.

**Commands Executed**

```
python -m app.scripts.run_market_discovery --mode backfill \
    --start 2026-08-09 --end 2026-08-10 \
    --max-ai-calls <remaining> --max-ai-cost-usd <remaining> --max-sonnet-calls <remaining>
    # (3 attempts; budget recomputed as remaining allowance each retry)
python -m app.scripts.run_market_discovery --mode delta \
    --max-ai-calls <remaining> --max-ai-cost-usd <remaining> --max-sonnet-calls <remaining>
    # (3 attempts, final one status=success)
python -m pytest -q   # 456 passed
python -m ruff check app/ tests/
python -m black --check app/ tests/
python -m mypy app/
```

**Remaining Work**

- KI-002 (new): Railway Cron trigger creation for the nightly scheduler
  is documented and ready but not performed — needs operator action with
  Railway dashboard/CLI access.
- TD-022/TD-023 above.
- 6 query/form combinations in tonight's catch-up window (substantial
  doubt, restructuring advisor, restructuring support agreement,
  debtor-in-possession financing ×2 form-groups, auditor resignation)
  never successfully completed against live SEC EDGAR — a future run
  could pick these up.
- The historical AI-review pass over Milestone 7.5.3's deferred bundles
  remains separate, still-deferred, not authorized by this pass.
- Milestone 7.5.4/7.6/Milestone 8 explicitly not to begin.

**Approximate Time Spent**

~4 hours (production database investigation, watermark-gap diagnosis,
3 catch-up run attempts with a live reliability fix applied mid-session,
3 delta labeling attempts, Morning Brief root-cause investigation with
a real-data spot-check before any fix, the classification fix itself
across 4 files, 20 new tests, DST-safe scheduler wrapper design and
implementation, full verification pass, documentation).

---

## 2026-08-11 — Stale Market Context (SOFR/HY OAS) investigated and fixed; TD-024

**Context**

Production showed SOFR `3.64%` as of `2026-08-05` and HY OAS `2.73%` as
of `2026-08-04` — user flagged these as suspiciously stale on
`2026-08-11`. Investigated per explicit instruction: no UI change until
root cause was found; no fabricated dates; no hiding of staleness.

**Investigation**

- `app.providers.fred.provider.sync_series` is the only function that
  fetches new FRED observations. Grepped the entire `app/` tree for any
  caller besides its own definition — none exists. No script, no API
  route, no scheduled job ever invokes it.
- `fred_series_registry.last_synced_at` for both `SOFR` and
  `BAMLH0A0HYM2`: `2026-08-06 14:20:49`/`50 UTC` — identical to the
  moment Milestone 5 first seeded them, five days prior, confirming zero
  syncs since.
- `fred_repository.get_latest_observation` (`ORDER BY obs_date DESC
  LIMIT 1`) and `app.core.freshness.compute_freshness` (measuring age
  from `retrieved_at`, correctly returning `cached` for 5-day-old data
  under FRED's `live_within=1 day`/`cached_within=30 days` policy) were
  both inspected and found correct — freshness was honestly reporting
  "cached," never falsely "live," and the query logic was never
  selecting the wrong row. This was purely an ingestion-cadence gap, not
  a caching, TTL, or selection bug.
- Queried live FRED directly (`api.stlouisfed.org/fred/series/
  observations`, real API key, no mock): `SOFR` latest real observation
  is `2026-08-10 = 3.63`; `BAMLH0A0HYM2` latest real observation is
  `2026-08-07 = 2.70` (weekends correctly absent from both; HY OAS
  publishes on a short lag even from FRED's own side).
- Stored rows confirmed via direct query: Nexus's actual latest stored
  SOFR observation before any fix was `2026-08-05 = 3.64`; HY OAS was
  `2026-08-04 = 2.73` — exactly matching what production displayed.
  Genuinely stale, not a display bug.

**Fix**

Two parts, both scoped to exactly `SOFR`/`BAMLH0A0HYM2` — no historical
discovery, SEC backfill, CourtListener sync, or Anthropic call involved:

1. **Immediate one-time refresh**: called the existing, unmodified
   `sync_series` directly against production for both series. 3 new
   observations each. Verified live via `GET /api/market-context`:
   `sofr.value=3.63, as_of_date=2026-08-10, freshness=live`;
   `high_yield_oas.value=2.70, as_of_date=2026-08-07, freshness=live`.
2. **Recurring refresh**: `app.scripts.run_nightly_scheduled_discovery`
   (the 10 PM ET wrapper from the prior entry) now also calls
   `_refresh_market_context` — `sync_series` for exactly these two
   series — on every correct-hour trigger, deliberately independent of
   the market-discovery research-cycle duplicate-check (FRED publishes
   on its own cadence; refreshing it is unconditionally safe/idempotent
   regardless of whether a research day already completed) and isolated
   per-series (a `SOFR` failure never blocks `BAMLH0A0HYM2` or the
   research cycle launch, matching this codebase's existing
   per-provider-isolation convention throughout). No API key configured
   → skips gracefully, logged, never crashes the wrapper.

**Tests Added**

4 new tests in `test_run_nightly_scheduled_discovery.py`:
correct-hour trigger refreshes Market Context (even when the research
cycle itself is a duplicate no-op, proving independence), wrong-hour
trigger does not refresh, skips gracefully without an API key, and a
per-series failure is isolated (one fails, the other still succeeds).

**Test Results**

Full backend suite: 456 → 460 passed (+4 net new tests). The 3
pre-existing tests in this file continue passing unchanged, now
implicitly exercising the `_no_close_session` fixture's new
`_refresh_market_context` stub with no behavior change. `ruff check` /
`black --check` / `mypy` — clean.

**Production Verification**

`GET /api/market-context` on the live Railway backend, post-manual-fix:

```
sofr:          value=3.63  as_of_date=2026-08-10  freshness=live
high_yield_oas: value=2.70  as_of_date=2026-08-07  freshness=live
```

**Remaining Work**

- KI-002 (Railway cron trigger creation) still governs whether this
  recurring refresh actually runs automatically in production — the
  code path is proven and tested, but not yet live on a schedule.
- TD-024 recorded, resolved.

**Approximate Time Spent**

~45 minutes (investigation across provider/service/repository code,
live FRED API verification, one-time production refresh, recurring-fix
implementation in the existing nightly wrapper, 4 new tests, full
verification, documentation).

---

## 2026-08-11 — Railway nightly cron services provisioned; KI-002 resolved

**Context**

Verified the existing `run_nightly_scheduled_discovery` wrapper matched
its documented behavior exactly (37 relevant tests re-run, all passing,
no defect found — see the two prior entries this same day) before any
Railway write. Installed the Railway CLI (npm, v5.37.3), ran
`railway setup agent -y` (skills + MCP config for Claude Code),
completed the official browser OAuth login, then used read-only
GraphQL queries to positively identify the target before any write:
workspace `kirantoday's Projects`, project `wonderful-dream`
(`3de98e8a-8dee-4af3-b931-694129774016`), environment `production`
(`81bd460e-f353-4718-ba66-5fbc4691d47b`), existing service
`nexus-credit-intelligence` — all matching exactly what the user had
independently confirmed from the dashboard, plus confirmed its real
build config (repo `kirantoday/nexus-credit-intelligence`, branch
`main`, root directory `/backend`, Dockerfile build) before creating
anything.

**Provisioning**

Created two new sibling services via `railway add --repo ... --branch
main` + `serviceInstanceUpdate` GraphQL mutations:
`nexus-nightly-10pm-edt` (`cronSchedule=0 2 * * *`) and
`nexus-nightly-10pm-est` (`cronSchedule=0 3 * * *`), both
`rootDirectory=/backend`, both `startCommand=python -m
app.scripts.run_nightly_scheduled_discovery`.

**Real defect found and fixed mid-provisioning**: the first attempt set
`startCommand`/`cronSchedule` via the API alone, then noticed the raw
`builder` field read back as `RAILPACK` rather than `DOCKERFILE` —
investigated by comparing against the *existing* service's own raw
field (also `RAILPACK`, also `railwayConfigFile: null`, yet genuinely
builds via Dockerfile in production), which proved Railway auto-detects
`railway.toml` by file presence at `rootDirectory` regardless of that
field — a false alarm. But confirming this raised the real question of
precedence, checked against Railway's own docs (not assumed): "Configuration
defined in code will always override values from the dashboard" — meaning
the two new cron services, sharing `backend/railway.toml` with the web
service, would have had their `startCommand` silently overridden back
to the web service's own `uvicorn ...` command on every deploy,
defeating the entire purpose. Fixed with two new, minimal, dedicated
config files (`backend/railway.nightly-edt.toml`,
`railway.nightly-est.toml` — same `[build]` Dockerfile section, correct
`[deploy] startCommand`/`cronSchedule` each), committed, pushed
(`b7913e1`), then pointed each cron service's `railwayConfigFile` at
its own file. The existing web service's `railway.toml` was never
touched. Both cron services then built successfully via Dockerfile
(`status: SUCCESS`), confirming the fix.

**Secrets handling**: variable names were listed via `railway variable
list --json`, piped directly into a script that printed only sorted
keys — raw values were never rendered to any visible output. All
required variables (`DATABASE_URL`, `DIRECT_DATABASE_URL`,
`SEC_USER_AGENT`, `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`,
`LLM_PROVIDER`, `COURTLISTENER_API_TOKEN`, `FRED_API_KEY`,
`ENVIRONMENT`, `LOG_LEVEL`) were set on both new services as Railway
reference variables (`${{nexus-credit-intelligence.VAR}}`, confirmed
syntax against Railway's own docs) — live references to the existing
service's own values, never duplicated/copied raw. Plus
`TZ=America/New_York` and explicit `NIGHTLY_MAX_AI_COST_USD=2.00`/
`NIGHTLY_MAX_AI_CALLS=300`/`NIGHTLY_MAX_SONNET_CALLS=75` (redundant with
the wrapper's own code defaults, set explicitly for dashboard-visible
auditability of the safety ceiling).

**Verification**

Pushing the two new config files auto-triggered a rebuild of all three
services (standard Railway behavior for a GitHub-connected branch,
unrelated files or not) — confirmed this built/deployed only, never
executed the nightly script: it was 12:42 PM ET at the time (nowhere
near the wrapper's 22:00 ET gate), and `ai_call_log`/
`market_discovery_run` were confirmed unchanged before and after.
`railway status` afterward correctly categorizes the two new services
under "Cron jobs" (not "Services"), both `● Online`, `0/1 running`
(idle, correctly not executing), with accurate next-run countdowns
(~9-10 hours from the time of provisioning, matching that night's 10 PM
ET). The existing web service confirmed unchanged and healthy
(`GET /health` → 200) throughout.

**Tests Added**

None — no application code changed, only Railway configuration and two
new minimal deployment config files (validated by the pre-commit hook's
`check toml`).

**Commands Executed**

```
npm install -g @railway/cli
railway setup agent -y
railway login
railway api '{ ... }'            # multiple read-only verification queries
railway add --repo kirantoday/nexus-credit-intelligence --branch main --service nexus-nightly-10pm-edt --json
railway add --repo kirantoday/nexus-credit-intelligence --branch main --service nexus-nightly-10pm-est --json
railway api 'mutation { serviceInstanceUpdate(...) }'   # x2, then x2 more for railwayConfigFile fix
railway variable set --service nexus-nightly-10pm-edt --environment production --skip-deploys --json ...
railway variable set --service nexus-nightly-10pm-est --environment production --skip-deploys --json ...
git add backend/railway.nightly-edt.toml backend/railway.nightly-est.toml
git commit ...   # b7913e1
git push origin main
railway status
```

**Remaining Work**

- First real nightly execution has not happened yet — next expected at
  the next 10:00 PM America/New_York. Per explicit instruction, not
  triggered manually and not waited for during this task.
- KI-002 resolved.

**Commit Hash**

`b7913e1` (Railway config files only — no application code changed)

**Approximate Time Spent**

~50 minutes (Railway CLI/agent setup, browser login, target
verification, service creation, the config-as-code precedence discovery
and fix, secret-safe variable wiring, full read-only verification,
documentation).

## 2026-08-11 — Milestone 8: Watchlists

**Summary**

Analyst Watchlists — "which issuers do I personally care about, and
what's changed?" A Phase 0 architecture check (required by this
milestone's own brief and by CLAUDE.md's Architecture Change Policy)
found that the incoming spec's proposed dedicated `watchlist`/
`watchlist_member` tables would silently contradict ADR-016, an
already-accepted decision that Research Universes and Watchlists share
one generalized `collection`/`collection_membership` table pair,
discriminated by `collection_type`. This was reported to the user before
any implementation code was written. The user's explicit direction:
reuse the existing schema exactly (`collection_type=watchlist`,
`scope=personal`, `curation_method=user_created`, membership through the
existing `collection_membership` table), add only what was genuinely
missing, and prefer one real "CFO Demo Watchlist" over reviving §14's
eleven-seeded-list plan (superseded by ADR-016's Research-Universes/
Watchlists split, functionally covered already by the 23 real Research
Universes built in Milestone 6.5/7.5.1).

**What was genuinely missing (and built)**

- Backend: `collection_repository.update_collection`/`delete_collection`
  (rename/delete a collection, deleting its own memberships first —
  never issuers, securities, evidence, alerts, or other collections'
  memberships); three batch repository functions
  (`alert_repository.list_alerts_by_issuers`,
  `security_repository.count_securities_by_issuers`,
  `collection_repository.list_collections_with_membership_for_issuers`)
  so a Watchlist's per-issuer aggregation is O(1) queries per resource
  type, not O(issuers); `research_universe_service
  .get_issuer_universe_memberships`/`_batch` explicitly exclude
  `collection_type=WATCHLIST` (a real regression risk caught during
  Phase 0: without this, a personal Watchlist membership would leak into
  Issuer Detail's "Which Research Universes is this issuer in?"
  section); a shared `derive_current_status` helper extracted from
  `issuer_timeline_service` so "current status" means the same thing on
  the Distress Timeline and on Watchlist detail; `morning_brief_service
  ._resolve_research_cycle`/`_is_new_development` renamed to public
  (`resolve_research_cycle`/`is_new_development`) so `watchlist_service`
  can call them directly rather than re-deriving the research-cycle
  boundary — the exact same "new" as the Morning Research Brief, no
  second definition; `issuer_timeline_service._qualifies` renamed to
  public `qualifies` for the same reuse-not-copy reason (a "latest
  development" must exclude the same dismissed/third-party alerts
  everywhere it's computed).
- New `watchlist_service.py` (create/rename/delete Watchlist, add/remove
  issuer — idempotent, never a duplicate-membership error) and
  `app/api/routes/watchlists.py`: `GET/POST /api/watchlists` (optional
  `issuer_id` query param populates `contains_issuer` per Watchlist, for
  the Add to Watchlist UI), `GET/PATCH/DELETE /api/watchlists/{id}`,
  `POST /api/watchlists/{id}/issuers`,
  `DELETE /api/watchlists/{id}/issuers/{issuer_id}`.
- Frontend: `WatchlistsPage.tsx` (landing page — real per-Watchlist
  counts, never fabricated demo numbers), `WatchlistDetailPage.tsx`
  (header + issuer table with Issuer/Current status/Latest development/
  Severity/Development date/New developments/Securities columns, mobile
  cards via the existing `DataTable`/`useIsMobile` pattern, rename/
  delete with a confirmation dialog explaining issuer data is never
  affected), and one reusable `AddToWatchlistButton.tsx` — a menu of
  every Watchlist with already-added state (checkbox), toggle add/
  remove, and inline "create a new Watchlist and add" — wired into
  Issuer Detail's header (the minimum integration point the spec
  required; not added to every screen, per its own "don't clutter"
  instruction). Watchlists enabled in primary nav, positioned after
  Morning Research Brief.
- Real "CFO Demo Watchlist" created via the application's own
  `watchlist_service` (not a raw-SQL fixture) after inspecting current
  production data: DIEBOLD NIXDORF Inc. (post-emergence monitoring,
  2023 Ch. 11), Trinseo PLC (active Ch. 11, going-concern doubt, event
  of default), EchoStar Corp (subsidiary Hughes Satellite Systems Ch. 11
  filings), Community Health Systems Inc (covenant-breach risk language,
  hospital-divestiture impairments), Lumen Technologies Inc (repeated
  debt exchange offers, upcoming maturity wall), iHeartMedia Inc (ABL
  facility maturity extension) — six real issuers, real alerts, real
  provenance, no synthetic data.

**Zero migration** — confirmed at every layer before writing code:
`CollectionType.WATCHLIST`, `CollectionScope.PERSONAL`,
`CurationMethod.USER_CREATED` already existed in `app/core/types.py`,
the DB `ck_collection_type`/`ck_collection_curation_method` CHECK
constraints already permitted `watchlist`/`user_created`, and
`ix_collection_collection_type` already existed — exactly as ADR-016's
own "Consequences" section anticipated.

**No per-user authentication exists** (TD-002, unchanged) — every
Watchlist is `scope=personal`/`owner_user_id=NULL` in a single shared
analyst workspace. `owner_user_id` already exists on `collection` for
real per-user ownership once authentication exists; no schema change
will be needed then.

**Verification**

- Backend: 481 tests pass (21 new — Watchlist CRUD, duplicate-add
  idempotency, delete-doesn't-delete-issuer, nonexistent watchlist/
  issuer handling, issuer counts, latest-development calculation
  (excludes dismissed/third-party alerts), the research-cycle
  "new development" boundary reusing `morning_brief_service`'s own
  helpers (deterministically pinned via the same `_seed_daily_run`
  pattern `test_morning_brief_service.py` already established), severity
  aggregation, and that a Watchlist membership never appears as
  "current status"). `ruff`, `black`, `mypy` all clean.
- Frontend: 130 tests pass (17 new — landing page incl. empty/error
  states and Watchlist creation, detail page incl. rename/delete/remove-
  issuer/mobile-card rendering/not-found, and the Add to Watchlist
  component incl. already-added state and inline create-and-add).
  `tsc --noEmit`, `eslint`, `prettier --check` all clean; production
  build succeeds.
- A real FK-ordering bug was found and fixed live during testing:
  `delete_collection` deleted a collection's memberships and the
  collection row in the same `flush()` with no ORM `relationship()`
  linking the two mapped classes, so the unit of work had no dependency
  information to order the deletes safely — SQLAlchemy attempted the
  parent-row delete first and hit a live FK violation. Fixed by
  flushing the membership deletes before deleting the parent row.
- Live-verified via the deployed application's own service layer (not
  raw SQL) that the CFO Demo Watchlist's real aggregation is correct:
  6 issuers, 1 with a new development this research cycle, mixed
  high/medium/low severities, correct per-issuer securities counts, and
  `current_status` correctly sourced from each issuer's real verified
  Research Universe memberships (never the Watchlist itself).

**Tests Added**

`backend/tests/integration/test_watchlist_service.py` (21 tests),
`web/src/pages/WatchlistsPage.test.tsx` (4),
`web/src/pages/WatchlistDetailPage.test.tsx` (8),
`web/src/components/AddToWatchlistButton.test.tsx` (5),
`web/src/components/Layout.test.tsx` (updated for the enabled nav item).

**Remaining Work**

- Production deploy/browser verification and the regression pass across
  Credit Universe, Research Universes, Morning Research Brief, Diebold
  Nixdorf/Trinseo timelines, and Market Context — see the follow-up
  entry/commit for results.
- `AboutPage.tsx`'s "Available Today vs. What's Next" copy is updated
  only after production verification confirms the deploy is genuinely
  live, per this milestone's own instruction not to claim availability
  ahead of actual deployment.

**Commit Hash**

`PENDING_COMMIT_HASH`

**Approximate Time Spent**

~3.5 hours (Phase 0 architecture investigation and conflict report,
backend repository/service/API implementation, frontend pages/
components, real-data CFO Demo Watchlist creation and verification,
full test/lint/type/build suite, documentation).
