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
