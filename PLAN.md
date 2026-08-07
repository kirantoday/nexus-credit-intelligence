# Nexus Credit Intelligence — POC Build Plan

A distressed-credit intelligence platform where every displayed fact carries full
provenance, built around **Credit Universe** — a screenable table of bonds and loans —
as the primary workflow, addressing the CFO's stated need to cut manual work for
investment professionals.

Design Principle: Build the smallest end-to-end working slice first. Every milestone must produce a runnable application with passing tests and visible user value before the next milestone begins. Prefer vertical feature completion over horizontal infrastructure expansion.

**Version 1 architecture and scope (§1–22) is feature-complete and approved.**
§23 documents Phase 2 / Future Architecture (canonical Credit Events, Time Machine
as-of queries, a Portfolio module, Data Quality scoring, background jobs) for
long-term continuity only — none of it is implemented, scheduled, or in the Version 1
build order (§18).

Stack, deployment target, provenance model, entitlement engine, and the eleven
watchlists are approved and carried forward from the prior revision. Version 1 adds:
Credit Universe, Dashboard, Capital Structure, Universal Search, AI Research
Assistant + LLM provider abstraction, Research Notes/Documents, Alerts, Users/Roles/
Audit, an explicit domain layer, and several data-model corrections (provenance
freshness, calculation lineage, admin-upload attribution).

---

# Project Governance

This document is the single source of truth for the architecture and implementation
roadmap. The architecture is intentionally version controlled. After **every**
completed milestone, this document **must** be updated before work begins on the next
milestone.

The repository always contains three documents, kept synchronized, each with a
distinct job:

| Document | Purpose |
|---|---|
| `PLAN.md` (this file) | Architecture, stack, domain model, provider architecture, AI architecture, security model, milestone roadmap, completion criteria, and **current implementation status**. Not a chronological log. |
| `BUILD_LOG.md` | The engineering journal — append-only, one entry per completed milestone, detailed enough that another engineer could reconstruct exactly how the system evolved. |
| `ARCHITECTURE_DECISIONS.md` | Architecture Decision Records (ADRs) — append-only, one record per significant architectural choice, including alternatives considered and tradeoffs accepted. |

`PLAN.md` tracks: overall progress, current milestone, completed milestones,
implementation status, technical debt, known issues, and the next milestone.
Chronological implementation history belongs in `BUILD_LOG.md`. Architecture
decisions belong in `ARCHITECTURE_DECISIONS.md` — never duplicated back into this
file beyond a pointer.

---

# Product Philosophy

Full detail — why Nexus exists, target users, product philosophy, the
Research Operating System vision, AI philosophy, provider philosophy,
long-term workflow, and future product direction — lives in
**`docs/VISION.md`**, the permanent, authoritative source. `PLAN.md` stays
the execution roadmap (architecture, data model, milestone status) and does
not duplicate it here.

As of 2026-08-06, this project is treated as the foundation of a commercial
institutional research platform for distressed-credit investment
professionals, not an interview/demo artifact — established after Milestone
6.5, formalized into `docs/VISION.md` after Milestone 7. That doesn't relax
any existing rule in this document or `CLAUDE.md`; if anything, it raises
the bar for provenance discipline, real providers over fabricated data, and
the milestone-by-milestone stop-and-wait workflow.

---

# Project Status

| Field | Value |
|---|---|
| **Overall Progress** | ~44% — Milestone 7 of 16 complete (6.5 inserted, approved) |
| **Current Milestone** | Milestone 7 — CourtListener adapter + docket view (§18 step 7) (complete) |
| **Current Status** | Milestone 7 is complete — see its entry above and ADR-019. 3 real CourtListener/RECAP dockets (Diebold Nixdorf, EchoStar/Hughes Satellite Systems Corporation, Office Properties Income Trust) live-verified and linked to already-seeded real issuers; 665 real docket entries ingested; 28 real evidence records and 27 real alerts produced through the same provider-agnostic evidence/alert pipeline SEC filings already use. The Morning Research Brief now shows 55 combined real alerts across two independent real providers (SEC EDGAR + CourtListener). |
| **Last Updated** | 2026-08-07 |
| **Current Git Branch** | main |
| **Latest Commit** | `9154e9e` — Milestone 7: CourtListener adapter + docket view |
| **Next Milestone** | Milestone 8 — Watchlists (§18 step 8), unstarted, pending explicit approval |

---

# Milestone Status

Mirrors the Version 1 build order in §18. All milestones are `Not Started` as of this
writing — this table is updated in place (status/date/commit columns) as each
milestone completes; it is not itself a log (see `BUILD_LOG.md` for that).

| Milestone | Feature | Status | Completion Date | Git Commit | Notes |
|---|---|---|---|---|---|
| 1 | Foundation: Supabase connection, Alembic skeleton, FastAPI `/health`, React shell | Complete (+ hardening + Supabase schema-isolation validation) | 2026-08-05 | `79ca395` (foundation), `c6c2811` (hardening), `9f753c4` (schema-isolation validation) | Full Supabase connectivity now verified live: `alembic upgrade head` succeeded against the real, shared project (ADR-013); `nexus` schema, `nexus.alembic_version`, and `vector`/`pg_trgm` extensions all confirmed in place with no cross-contamination of the other application's objects. KI-001 closed — see Known Issues and `BUILD_LOG.md`. Hardening pass (branch rename, `CLAUDE.md`, pre-commit, `README.md`, GitHub templates, GitHub remote) tracked as "Milestone 1 Hardening" in `BUILD_LOG.md`, not counted as Milestone 2. |
| 2 | Provenance, `raw_provider_payload`, `calculation`/`calculation_input`, entitlement engine | Complete | 2026-08-06 | `27af3c1` | Migration `0002` applied and round-tripped live against the shared `nexus` schema. 60 tests pass (39 unit, 21 integration against the live DB). ADR-014 records the domain-layer conventions (Pydantic domain objects, function-style repositories, text+CHECK enums) established here for all later canonical entities. |
| 3 | SEC adapter vertical slice (real issuer + filing + financial fact, full domain-layer path) | Complete | 2026-08-06 | `36bfaff` | Migration `0003` (`issuer`, `financial_fact`) applied and round-tripped live. Real, permanently-committed proof: Apple Inc. (CIK 0000320193) + one real XBRL revenue fact, both with full provenance/raw-payload lineage. 91 tests pass (54 unit, 37 integration incl. 3 genuinely live SEC EDGAR calls). Found and fixed a real Alembic autogenerate bug (search_path on the migration connection made existing tables invisible to schema comparison). |
| 4 | Credit Universe initial page (seeded canonical securities) | Complete | 2026-08-06 | `34fd088` | Migration `0004` (`security` table + issuer synthetic columns) applied and round-tripped live. Real, permanently-committed proof: one real SEC-sourced Apple Inc. bond (aggregate XBRL figure, honestly represented as such — no fabricated CUSIP/maturity) plus 10 synthetic leveraged-loan positions across 8 fictional issuers, all tagged `SYNTHETIC_DEMO_DATA`. Credit Universe is now the post-login landing page: sortable/filterable/paginated TanStack Table v8 grid, every row carrying a provenance badge. Found and fixed two real bugs during this milestone: a search-box keystroke-loss race (fixed with a debounce hook) and a Supabase pgbouncer/psycopg3 prepared-statement incompatibility causing intermittent `InvalidSqlStatementName` errors (fixed by disabling server-side prepare in `app/db/session.py`). 134 backend tests pass (91→134), 26 new frontend tests pass. |
| 5 | OpenFIGI + FRED adapters | Complete | 2026-08-06 | `a7f11f2` | Migration `0005` (`security.figi` unique index, `fred_series_registry`, `fred_observation`) applied and round-tripped live. Real, permanently-committed proof: five real Apple corporate bonds (real FIGI + maturity/coupon via OpenFIGI) plus real, live-synced SOFR and ICE BofA HY OAS FRED observations. Credit Universe gained a "Current Benchmark Rate" column and a Market Context panel — both real, reported facts, not a blended calculation. Found and fixed two real bugs: `conftest.py`'s separate test engine had the same pgbouncer/psycopg3 issue as Milestone 4's `app/db/session.py` (fixed independently there too), and OpenFIGI's unauthenticated tier hit a live 429 under back-to-back live tests (fixed with a longer test-client throttle + optional API-key header wiring). 166 backend tests pass (134→166), 3 new frontend tests pass (26→29). |
| 6 | Issuer detail page + Capital Structure page/model | Complete | 2026-08-06 | `2262e7c` | Migration `0006` (`capital_structure_position`) applied and round-tripped live. Real, permanently-committed proof: a new full-stack synthetic issuer (Cobalt Ridge Energy Corp, 8 layers, real illustrative recovery waterfall against a stated EV) plus reported capital-structure layers for all 8 Milestone 4 loan issuers. Issuer Detail (`IssuerPage.tsx`) is the primary research workspace, organized around analyst questions rather than tables; Capital Structure renders as an embedded section, not a separate page, per this milestone's explicit brief. 204 backend tests pass (166→204), 9 new frontend tests pass (29→38). |
| 6.5 | Research Universes + Overnight Distress Filing Monitor (inserted, approved — see §24) | Complete | 2026-08-06 | `4900162` | Migration `0007` (`collection`, `collection_membership`, `sec_filing`, `filing_monitor_run`, `research_evidence`, `alert_event`) applied and round-tripped live. Real, permanently-committed proof: 23 real SEC-verified issuers (23 accepted / 7 rejected of 30 candidates — RAD/MNK/YELL/BIG/FYBR/SAVE/COMM excluded, none resolvable in SEC's live `company_tickers.json`) organized into 15 Research Universes (14 distress-oriented + Investment Grade Benchmarks, kept visually and structurally separate). A live baseline run + a real, explicitly-labeled 60-day Historical Backfill Demo produced 85 real `sec_filing` rows, 83 `research_evidence` rows, and 28 real `alert_event` rows (4 high / 5 medium / 19 low severity; 0 deterministic-only / 28 AI-reviewed by live Anthropic calls), with zero run errors. AI review demonstrably worked as designed: real high-severity Chapter 11 events (EchoStar/DISH subsidiaries, Office Properties Income Trust) were correctly flagged high, while routine "chapter 11" mentions in benign contexts (JPMorgan tax-code reference, Johnson & Johnson historical subsidiary dismissal, Ford/Microsoft boilerplate) were correctly downgraded to low severity with honest "no distress" wording rather than false alarms. Provider-specific AI credential config (ADR-017) replaced the unused generic `LLM_API_KEY`. 274 backend tests pass (204→274, +70), 61 frontend tests pass (38→61, +23) across 11 files. Found and fixed two genuine test-design defects during this milestone (a CIK/ticker false-positive substring-match bug in the seed script's issuer resolver — corrected with word-boundary matching and cleaned up live; and 5 integration tests whose fake test doubles weren't CIK-scoped, which broke once real seed data existed). Full live browser walkthrough completed: Research Universes (benchmark separation), Morning Research Brief (real alerts, severity filter, evidence expansion with real excerpts), drill-down into Issuer Detail (Research Universe Memberships section), Credit Universe filtered by universe (chip, real Apple securities returned for Investment Grade Benchmarks). See ADR-016/017/018. |
| 7 | CourtListener adapter + docket view | Complete | 2026-08-07 | `9154e9e` | Migrations `0008` (`court_docket`, `court_docket_entry`, `docket_document`, `research_evidence.docket_entry_id`) and `0009` (corrective — see Problems Encountered) applied and round-tripped live. Real, permanently-committed proof: 3 real CourtListener/RECAP dockets live-searched, live-verified by exact `courtlistener_docket_id` match, and linked to 3 already-seeded real issuers with independently-confirmed real Chapter 11 events (Diebold Nixdorf, EchoStar/Hughes Satellite Systems Corporation, Office Properties Income Trust) — 665 real docket entries ingested (429 + 111 + 125), 28 `research_evidence` rows, 27 `alert_event` rows (24 high / 2 medium / 1 low), all AI-reviewed, all correctly wired into the same provider-agnostic evidence/alert pipeline ADR-018 anticipated before this milestone existed (`evidence_provider=courtlistener`, no `alert_event` schema change). Combined Morning Research Brief now shows 55 total alerts across both real providers (28 SEC + 27 CourtListener). Docket discovery is a curated, live-verified linking step, not an automatic per-issuer feed like SEC filings — see ADR-019 for why. 300 backend tests pass (274→300, +26), 67 frontend tests pass (61→67, +6) across 12 files. Found and fixed three genuine live-caught issues (see Problems Encountered): an Alembic `checkconstraint_byname` blind spot requiring a corrective migration; a real signal-to-noise problem where routine Chapter 11 case boilerplate flooded evidence via the ambiguous-context "bare mention" rule (fixed with `DOCKET_EXCLUDED_RULE_IDS`); and an unbounded Anthropic SDK timeout that let a real, severely degraded CourtListener response (66.7s for a single page, confirmed via isolated diagnostic) stall a sync run with no error. Full live browser walkthrough completed: Issuer Detail's new "What happened in court?" section (real docket header + entries, honest "(no description on file)"/"Not on RECAP" for genuinely incomplete real PACER data), Morning Research Brief showing cross-provider real alerts together. See ADR-019. |
| 8 | Watchlists (10 coverage + 1 benchmark) + comparison view | Not Started | — | — | |
| 9 | Research notes/documents + audit events | Not Started | — | — | |
| 10 | Alerts (rules, engine, panel/page) | Not Started | — | — | |
| 11 | TRACE adapter/sample | Not Started | — | — | |
| 12 | Universal Search | Not Started | — | — | |
| 13 | AI Research Assistant + gated embeddings | Not Started | — | — | |
| 14 | Disabled licensed-provider capability cards | Not Started | — | — | |
| 15 | Railway/Vercel deployment validation | Not Started | — | — | |
| 16 | End-to-end verification against Completion Criteria (§20) | Not Started | — | — | |

---

# Technical Debt

Shortcuts the architecture *intentionally* accepts for the POC, tracked so they don't
get forgotten or mistaken for oversights. Populated from architecture decisions
already made in §1–23; will grow with genuine shortcuts taken during implementation.

| ID | Description | Priority | Planned Resolution | Status |
|---|---|---|---|---|
| TD-001 | Domain-layer boundary (providers must not call SQLAlchemy directly, §3) is enforced by code review/directory convention only — no automated import-boundary lint rule | Low | Add an import-linter/ruff rule restricting SQLAlchemy imports outside `repositories/` once core patterns stabilize | Open (deferred by design) |
| TD-002 | Authentication disabled (`AUTH_ENABLED=false`) for the V1 demo; every request treated as an implicit administrator | Medium | Wire Supabase Auth JWT validation per §13 once the demo audience needs real user/role separation | Open (deferred by design) |
| TD-003 | Search index storage shape (single `search_document` table vs. per-table `tsvector` columns, §4.13) not yet decided | Low | Decide during build step 12 based on query-performance testing | Open (deferred by design) |
| TD-004 | `backend/app/db/session.py` uses synchronous SQLAlchemy (`create_engine`/`sessionmaker`), not an async engine, even though FastAPI/provider adapters are async-capable | Low | Revisit if a provider-heavy milestone (SEC/FRED/CourtListener concurrency) shows the sync DB layer is a real bottleneck; async SQLAlchemy is a drop-in-ish swap behind the repository layer (§3) | Open (pragmatic choice, not a gap) |
| TD-005 | `data_entitlement.derived_data_permission` exists on the model/domain object (PLAN.md §4.8) but `policy_check` doesn't yet use it — deciding whether a *calculated* value derived from licensed inputs may be treated less restrictively than the raw input requires walking `calculation_input` lineage back to the strictest governing entitlement, which has no real licensed provider to test against yet | Low | Implement once Milestone 14 (disabled licensed-provider capability cards) or a real licensed adapter makes this testable against actual data | Open (deferred by design, ADR-014) |
| TD-006 | SEC EDGAR company-facts responses (hundreds of us-gaap concepts, several MB for a large filer) are stored inline in `raw_provider_payload.payload_json` (JSONB) rather than Supabase Storage — PLAN.md §4.4 names "SEC JSON" as an example of a *small* inline-appropriate response, but company-facts specifically is not small. `SUPABASE_STORAGE_BUCKET` isn't configured yet (deferred per Milestone 2), so storing large payloads there wasn't an option this milestone; skipping raw-payload persistence entirely was rejected as a correctness violation (breaks "every raw payload must be recoverable") | Medium | Move large provider responses (company-facts JSON, filings, court documents) to Supabase Storage via `storage_object_path` once the bucket is configured (Milestone 9/document milestone, or whenever Storage is first genuinely needed) | Open (deferred by design) |
| TD-007 | `security` (PLAN.md §4.5) carries a single `provenance_id` for the whole row, not per-field provenance — a real security often blends fields sourced/verified at different times (e.g. CUSIP from OpenFIGI, coupon from the issuer's indenture) that a single provenance row can't distinguish | Low | Milestone 5's OpenFIGI adapter — the scenario this TD anticipated — deliberately did NOT resolve it: OpenFIGI-identified bonds became new `security` rows (purely OpenFIGI-sourced, so a single `provenance_id` is already correct), not enrichments of the existing SEC-sourced aggregate row (which would have misattributed a specific bond's FIGI to a balance-sheet-total row). Still revisit once a milestone actually needs to blend two providers on one existing row | Open (deferred by design, `backend/app/domain/security.py`) |
| TD-008 | SEC EDGAR's XBRL company-facts API (the only SEC EDGAR endpoint this codebase uses) exposes only issuer-level aggregate concepts (e.g. `LongTermDebtNoncurrent`), not per-instrument dimensional data — real, per-instrument bond data (CUSIP, specific maturity/coupon) is not obtainable from this endpoint at all. `normalize_bond_security` honestly represents this by leaving `cusip`/`isin`/`figi`/`maturity_date`/`coupon` as `None` rather than fabricating instrument-level detail | Medium | Milestone 5's OpenFIGI adapter now supplies real FIGI/maturity/coupon for specific bond issues (a different data source, as this TD anticipated) — partially resolved for the issuers OpenFIGI covers. SEC EDGAR itself still can't provide this; CUSIP/ISIN remain unavailable from either provider | Open (real external API limitation, not a design shortcut) |
| TD-009 | `providers/fred/provider.py`'s `sync_series` pulls only the most recent `limit` observations (default 10), not a full historical backfill to a series' `observation_start` — a deliberate first-vertical-slice scope choice, not an oversight | Low | Add a bulk/historical sync path once a feature actually needs trend history (e.g. a rate chart) rather than just the latest value | Open (deferred by design, `backend/app/providers/fred/provider.py`) |
| TD-010 | Real issuers (Apple Inc.) have no `capital_structure_position` rows — neither SEC EDGAR's company-facts API nor OpenFIGI's search endpoint reports seniority/lien position/ranking for a specific instrument (same underlying gap as TD-008), so this milestone deliberately did not force real securities into a stack layer it can't honestly support. The Issuer Detail page falls back to a flat Securities table for any issuer with no capital structure layers on file, so nothing is hidden — it just isn't organized into a priority stack yet | Medium | Populate real capital structure layers once a provider that actually reports lien/seniority/ranking data exists (a licensed provider, Milestone 14, or a future SEC dimensional-XBRL parse) | Open (real external data limitation, not a design shortcut, `backend/app/synthetic/capital_structure_generator.py`) |
| TD-011 | Issuer Detail's pre-existing "What filings support this?" and "What changed recently?" sections (`issuer_service.py`, Milestone 3) are driven solely by `financial_fact`-linked provenance — they were never extended to also surface the new `sec_filing`/`research_evidence`/`alert_event` rows Milestone 6.5 introduces. Live-verified during the Milestone 6.5 browser walkthrough: EchoStar Corp has 2 real `sec_filing` rows and 2 real `alert_event` rows (visible on the Morning Research Brief, with a working drill-down link into this same Issuer Detail page), yet its own "What filings support this?" section reads "No filings on file for this issuer yet" — correct for the financial-fact-evidentiary question that section actually answers (EchoStar was seeded identity-only, no XBRL pull), but easy to misread as "this issuer has no SEC filings at all." Not a scope violation — PLAN.md §24.9 committed only to a new, separate "Research Universe Memberships" section (present and correct) — but a real UX gap worth closing | Low | Extend `issuer_service.get_issuer_detail` to include `sec_filing`/`alert_event` activity in "What filings support this?"/"What changed recently?", or re-label the existing sections to make their financial-fact scope explicit, once Issuer Detail has a real design pass for it | Open (discovered during Milestone 6.5 browser walkthrough, not a regression) |
| TD-012 | `app.providers.courtlistener.provider.sync_docket_entries` always re-walks a docket's full pagination from CourtListener on every call — it has no "resume from where a partial run left off" mode. A docket already fully synced re-fetches every page again on the next run (harmless but slow — idempotent inserts are skipped, but the live API calls themselves are not), and a run interrupted mid-docket (e.g. a network stall) loses that docket's entire in-progress pagination on rollback, not just the unsynced remainder. Real, live-observed cost during Milestone 7: a 429-entry docket's ~22-page re-sync took over 20 minutes at CourtListener's live (and, at the time, unusually slow — 60-70s/page) response rate | Low | Track a per-docket pagination cursor (e.g. the last successfully processed page URL or `courtlistener_entry_id`) so a re-run resumes instead of restarting, once a real caller needs frequent incremental re-sync rather than the current occasional-backfill usage pattern | Open (deferred by design, `backend/app/providers/courtlistener/provider.py`) |

---

# Known Issues

| ID | Description | Impact | Status |
|---|---|---|---|
| KI-001 | ~~No real Supabase project credentials available.~~ **Resolved 2026-08-05.** `DIRECT_DATABASE_URL` (a true direct endpoint, port 5432 — not the IPv4-compatible session pooler) was supplied and `alembic upgrade head` run successfully against the live, shared Supabase project (ADR-013). Verified live: `nexus` schema exists; `nexus.alembic_version` exists at revision `0001`; `vector`/`pg_trgm` extensions exist in `public`; no Nexus object exists in `public` or any other schema; no existing non-Nexus object was modified; a SQLAlchemy session opened/closed cleanly via `DATABASE_URL` with `search_path` confirmed as `nexus, public`; `/health` returns 200. One anomaly was found and corrected during validation: the migration's original `CREATE EXTENSION IF NOT EXISTS pg_trgm` (no explicit target schema) installed into `nexus` rather than `public`, because the connection's `search_path` is `nexus, public` and `pg_trgm` did not previously exist. Corrected live via one approved `ALTER EXTENSION pg_trgm SET SCHEMA public` (verified relocatable, verified freshly created by this same run, not a pre-existing/shared extension being moved) and fixed at the source by pinning `WITH SCHEMA public` explicitly in `0001_enable_extensions.py` for all future runs. Full details in `BUILD_LOG.md`. | Blocked Milestone 2 start and full closure of Milestone 1 / Milestone 15 success criteria — now unblocked. | **Closed** |

This section tracks open defects discovered during and after each milestone; entries
are added here (current state) and also narrated in `BUILD_LOG.md` (how/when they
were found and fixed).

---

# Next Immediate Goal

**Milestones 1 through 6 are complete.** The provenance spine, raw-response
store, entitlement engine, three real provider adapters (SEC EDGAR, OpenFIGI,
FRED), Credit Universe, and the Issuer Detail research workspace (with an
embedded Capital Structure section, `capital_structure_position` per §4.6)
are implemented, tested, and manually verified end-to-end against the live,
shared Supabase project — including a real, live-browser walkthrough of both
a fully-modeled synthetic distressed issuer (Cobalt Ridge Energy Corp, full
recovery waterfall) and a real issuer with no capital structure data (Apple
Inc., correctly falling back to its flat securities list).

**Milestone 6.5 (Research Universes + Overnight Distress Filing Monitor, §24)
is complete**, inserted before Milestone 7 by explicit approved direction. 23
real SEC-verified issuers are ingested and grouped into 15 Research
Universes; Credit Universe filters by Research Universe; Issuer Detail shows
universe memberships; the overnight monitor's baseline and backfill modes
both work with safe watermark behavior (delta mode shares the same code path
and is exercised by the integration test suite, though not yet run live —
there is no second day of real overnight data to process yet); deterministic
and AI-assisted evidence/alerts are real, evidence-backed, and cautiously
worded (verified via a live 60-day Historical Backfill Demo — 85 filings, 83
evidence records, 28 alerts); the Morning Research Brief renders and
drill-down reaches Issuer Detail; the full test/lint/type/build/migration
suite passes; `PLAN.md`/`BUILD_LOG.md`/ADR-016/017/018 are updated. See §24.10
for the full completion record.

**Milestone 7 (CourtListener adapter + docket view, §18 step 7) is
complete.** Per the frozen §4.5 schema (`court_docket`, `court_docket_entry`,
`docket_document`) and §15 (PACER handling), plus ADR-018's already-documented
forward path: 3 real CourtListener/RECAP dockets (Diebold Nixdorf, EchoStar/
Hughes Satellite Systems Corporation, Office Properties Income Trust)
live-verified and linked to already-seeded real issuers; 665 real docket
entries ingested; 28 real evidence records and 27 real alerts produced
through the exact evidence/alert pipeline ADR-018 anticipated
(`evidence_provider = courtlistener`, no `alert_event` schema change).
Docket discovery is a curated, live-verified linking step, not an automatic
per-issuer feed like SEC filings — see ADR-019. `docs/VISION.md` has been
created as the permanent, authoritative source for why Nexus exists, target
users, product philosophy, the Research Operating System vision, AI
philosophy, provider philosophy, long-term workflow, and future product
direction; this Product Philosophy section above now only points to it.

**Milestone 8 (Watchlists, §18 step 8) has not started**, and awaits
explicit approval before beginning, per the same stop-and-wait rule that
gated Milestone 7.

---

# Implementation Rules

Claude Code must implement the application incrementally. Every milestone must
produce a runnable application. Before beginning the next milestone, **all** of the
following must be true:

1. Feature implementation completed.
2. Unit tests pass.
3. Integration tests pass.
4. Backend starts successfully.
5. Frontend starts successfully.
6. Database migrations succeed.
7. Linting passes.
8. Production build succeeds.
9. Git commit created.
10. `PLAN.md` updated (Project Status, Milestone Status, Technical Debt, Known Issues,
    Next Immediate Goal).
11. `BUILD_LOG.md` updated with a new appended entry for the milestone.
12. `ARCHITECTURE_DECISIONS.md` updated with a new ADR if the milestone changed
    architecture (it normally shouldn't — see Architecture Change Policy).
13. Milestone marked complete in the Milestone Status table.
14. Overall progress percentage updated in Project Status.
15. Next milestone identified in Next Immediate Goal.
16. Completed functionality demonstrated before continuing.

### Milestone completion checklist (what actually runs, each time)

At the end of every completed milestone: run all tests → fix failures → run linting →
verify builds → commit to Git → update `PLAN.md` → update `BUILD_LOG.md` → update
`ARCHITECTURE_DECISIONS.md` if applicable → update milestone progress → update overall
project completion percentage → list remaining work → recommend the next milestone.
This operationalizes rules 1–16 above; it is not a separate, looser process.

---

# Architecture Change Policy

**Architecture Version: 1.0 — frozen.**

The architecture documented in §1–23 of this file is frozen as of this revision.
Claude Code must **not** silently modify architecture while implementing. "Silently"
includes convenient-seeming deviations made mid-milestone without stopping to flag
them — e.g. adding a table not in §4, changing a provider contract, letting a provider
touch SQLAlchemy directly, or picking a different frontend data-fetching pattern than
TanStack Query.

If implementation reveals that an architectural change is genuinely required:

1. **Stop.** Do not continue implementation on the affected path.
2. **Explain**: why the change is needed, the tradeoffs, the impact on the roadmap
   (§18), and alternatives considered.
3. **Update** `PLAN.md` (the affected section) and `ARCHITECTURE_DECISIONS.md` (a new
   ADR recording the change, superseding the prior one it replaces rather than
   deleting it).
4. **Mark the affected architecture version** (e.g. "Architecture Version: 1.1") so
   the change is traceable.
5. Do not continue implementation on the affected path until the proposed change has
   been reviewed and confirmed.

---

## 1. Guiding constraints

1. **Provenance-first.** No code path may render a value without a `provenance` row
   backing it. Fact tables store a `provenance_id` FK, never inline source/date/URL
   strings.
2. **Domain layer boundary (new).** Provider adapters never touch SQLAlchemy directly.
   The flow is fixed:

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

   Provider modules may produce provider DTOs and canonical domain objects, but must
   not call SQLAlchemy session operations. Only repositories touch the ORM/session.
   This keeps normalization logic testable without a database and keeps persistence
   concerns out of adapters that already have enough responsibility (throttling,
   retry, schema validation).
3. **AI has no raw SQL access.** The Research Assistant works exclusively through a
   fixed set of typed tools backed by repositories — never an LLM-authored query.
4. **Every list, chart, and answer states its as-of date and source.** Curated
   groupings (watchlists) and computed screens (Credit Universe, Dashboard) never
   assert status; they surface dated records and let the reader see the evidence.

---

## 2. Stack (approved, unchanged)

**Database**
- Supabase-managed PostgreSQL only, in every environment (local dev, test, staging,
  production). No local PostgreSQL container, no Docker Compose database service, no
  SQLite.
- **Shared Supabase project, schema-isolated** (ADR-013): Nexus reuses an existing
  Supabase project that also supports another application, rather than provisioning
  a dedicated one. Isolation is enforced by Postgres schema, not by project: every
  Nexus-owned object (tables, indexes, sequences, enum types where practical, views,
  the Alembic version table) lives in the `nexus` schema. Nexus never reads, writes,
  migrates, renames, truncates, or drops anything belonging to the other
  application, and never drops/recreates a shared extension. `Base.metadata` (SQLAlchemy)
  defaults to schema `nexus`; Alembic runs with `include_schemas=True`,
  `version_table_schema="nexus"`, and an `include_name` filter restricting
  autogenerate/comparison to the `nexus` schema only. The connection's
  `search_path` is set to `nexus, public` as a second layer, never relied on alone.
  The `nexus` schema is not exposed to PostgREST/the Supabase Data API — the
  frontend reaches Nexus data only through FastAPI.
- Extensions enabled in Supabase: `pgvector` (gated embeddings, §4.9) and `pg_trgm`
  (trigram fuzzy search, §7). Extensions are database-wide, shared with the other
  application on this project — Nexus migrations only ever `CREATE EXTENSION IF NOT
  EXISTS`, never drop/downgrade/relocate one.
- SQLAlchemy 2 (ORM + Core) and Alembic for migrations.
- `DATABASE_URL` — Supabase pooled/runtime connection string, used by the running app.
- `DIRECT_DATABASE_URL` — Supabase direct connection, used by Alembic when a
  non-pooled connection is required for migrations.

**Backend**
- Python 3.12, FastAPI, Pydantic 2, SQLAlchemy 2, Alembic.
- Hosted on Railway. Railway environment variables hold DB credentials, provider API
  keys, and feature flags — nothing secret in code or committed files.
- `GET /health` — cheap liveness check (no external calls) for Railway's health check.
- Railway's filesystem is ephemeral and is never used for durable storage.

**Frontend**
- React + TypeScript + Vite, Material UI, TanStack Query, TanStack Table.
- Hosted on Vercel, calling the Railway backend via `VITE_API_BASE_URL`.
- Deployed and built independently of the backend — no server-rendered coupling.

**Architecture**

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

**Local development**
- Run FastAPI locally (`uvicorn`) and Vite locally (`npm run dev`); both connect
  directly to a Supabase development project over the network — no local Postgres,
  no Docker database, no SQLite fallback of any kind.
- Use a separate Supabase project (or at minimum a separate schema) for dev/test vs.
  staging/production, where practical.
- Docker is kept **only** as an optional packaging step for the Railway backend
  (a `Dockerfile` for the FastAPI app), never for running a database.

---

## 3. Domain layer (new)

```
backend/app/domain/
    issuer.py             # Issuer, Security canonical objects
    security.py
    capital_structure.py  # CapitalStructurePosition canonical object
    financials.py          # FinancialFact canonical object
    market_data.py           # TraceObservation, TraceDerivedMetric, FredObservation
    research.py                # ResearchNote, ResearchNoteVersion canonical objects
    documents.py                 # ResearchDocument, DocketDocument canonical objects
    alerts.py                      # AlertRule, AlertEvent canonical objects
    provenance.py                     # Provenance, Calculation, CalculationInput canonical objects
    credit_events.py                    # docket/filing/rating-change events feeding alerts & dashboard

backend/app/repositories/
    issuer_repository.py
    security_repository.py
    capital_structure_repository.py
    financial_fact_repository.py
    market_data_repository.py
    provenance_repository.py
    research_repository.py
    document_repository.py
    alert_repository.py
    watchlist_repository.py
    search_repository.py
    audit_repository.py
```

Providers (`backend/app/providers/**`) call normalizers, which build canonical domain
objects (`backend/app/domain/**`); only repositories (`backend/app/repositories/**`)
open a SQLAlchemy session and write. API routes and the AI assistant's tools call
repositories, never the ORM directly. This boundary is enforced by convention +
code review in this POC (no separate lint rule planned for the POC stage, but the
directory structure makes a violation visible immediately).

---

## 4. Data model

All tables live in Supabase Postgres, defined as SQLAlchemy 2 models and versioned
through Alembic migrations. IDs are `UUID` (Postgres `gen_random_uuid()`) unless noted.

### 4.1 `provenance` (the spine — revised)

| column | type | notes |
|---|---|---|
| `id` | uuid PK | |
| `provider` | text | enum: `sec_edgar`, `finra_trace`, `openfigi`, `fred`, `courtlistener`, `pacer`, `admin_upload`, `sp_global_loan_pricing`, `sp_global_loan_reference`, `octus`, `bloomberg`, `lseg_lpc`, `synthetic`, `ai_generated` — **`provider` describes the ingestion channel, not necessarily the document's original author/publisher; see `original_source` below** |
| `original_source` | text, nullable | set when `provider = admin_upload`: where the uploaded material actually originated (`pacer`, `courtlistener`, `issuer_site`, `other`). Never left implicit — a manually uploaded document is not assumed to be a PACER retrieval (§9). |
| `source_attested_by` | text, nullable | who asserted `original_source` is accurate (an admin user id), set alongside `original_source` |
| `source_attested_at` | timestamptz, nullable | when that attestation was made |
| `source_record_id` | text | provider-native ID (accession no., docket id, series id, FIGI, trade id) |
| `source_url` | text, nullable | canonical fetch URL, no API keys embedded; null for admin uploads without a known source URL |
| `as_of_date` | date | date the underlying fact is true/reported for |
| `retrieved_at` | timestamptz | when *we* ingested it (fetch time for adapters, upload time for `admin_upload`) — sourced from the `raw_provider_payload` row, never recomputed |
| `transformation` | text enum | `reported` (verbatim from source) or `calculated` (derived — see `calculation_id`) |
| `classification` | text enum | `public`, `licensed`, `synthetic`, `ai_extracted` |
| `calculation_id` | uuid FK, nullable | → `calculation` table when `transformation = calculated` |
| `raw_payload_id` | uuid FK, nullable | → `raw_provider_payload` row this fact was extracted from, for audit replay |
| `created_at` | timestamptz | row insert time |

**Freshness is not a stored column (§10).** `freshness` (`live`/`cached`/`stale`) is
always computed at read time from `retrieved_at` + a per-provider TTL policy. If a
point-in-time snapshot is ever needed for historical reporting, it is named
`freshness_at_ingestion` explicitly and stored separately — never conflated with the
live, always-recomputed `freshness` value the API returns.

### 4.2 `calculation` (explains derived values — revised)

| column | type | notes |
|---|---|---|
| `id` | uuid PK | |
| `method` | text | e.g. `vwap`, `last_trade`, `days_since_last_trade`, `liquidity_flag`, `ev_coverage`, `illustrative_recovery` |
| `formula_note` | text | human-readable description |

`input_provenance_ids` (a JSONB array) is **removed**. Calculation inputs are now a
normalized join table (§4.3) so lineage supports referential integrity and queries
like "which calculations were invalidated by this fact changing."

### 4.3 `calculation_input` (new — normalized calculation lineage)

| column | type | notes |
|---|---|---|
| `calculation_id` | uuid FK → `calculation.id` | |
| `provenance_id` | uuid FK → `provenance.id` | |
| `input_role` | text, nullable | e.g. `trade_price`, `trade_size`, `denominator` — clarifies *how* the input was used |
| `sequence_number` | int, nullable | ordering hint when input order matters (e.g. time-ordered trades feeding VWAP) |

Composite primary key `(calculation_id, provenance_id)` — a given provenance record
feeds a given calculation at most once (use `input_role`/`sequence_number` for
multiplicity within a calc, not duplicate rows).

### 4.4 `raw_provider_payload` (durable raw-response store)

Because Railway storage is ephemeral, every raw provider response is persisted in
Supabase, never on the Railway filesystem beyond transient processing.

| column | type | notes |
|---|---|---|
| `id` | uuid PK | |
| `provider` | text | matches `provenance.provider` enum |
| `source_record_id` | text | provider-native identifier for this response |
| `request_fingerprint` | text | hash of the request (URL + params) for idempotent re-fetch checks |
| `payload_json` | jsonb, nullable | small raw responses (SEC JSON, OpenFIGI, FRED, CourtListener JSON) stored inline |
| `storage_object_path` | text, nullable | Supabase Storage object path for large payloads (filings, court documents, TRACE extract files, admin-uploaded documents) |
| `retrieved_at` | timestamptz | original fetch/retrieval timestamp, immutable once written |
| `checksum` | text | content hash, detects drift/corruption on replay |
| `content_type` | text | e.g. `application/json`, `application/pdf` |
| `provenance_id` | uuid FK, nullable | back-reference once a `provenance` row is created from this payload |

### 4.5 Canonical entity tables

- **`issuer`** — id, legal_name, cik (nullable), lei (nullable), ticker (nullable), sic (nullable), sector (nullable). Identity fields carry provenance too.
- **`security`** — id, issuer_id, instrument_type (`bond`|`loan`|`equity`), seniority (`first_lien`|`second_lien`|`senior_unsecured`|`subordinated`|`preferred`|`common`, nullable), lien_position (nullable), secured (bool, nullable), cusip/isin/figi (nullable each), description, maturity_date, coupon, amount_outstanding, benchmark (nullable, e.g. `SOFR`), spread (nullable) — each field with its own provenance row since fields arrive from different providers (OpenFIGI vs SEC vs synthetic).
- **`financial_fact`** — id, issuer_id, concept (`us-gaap:Revenues`, etc.), value, unit, fiscal_period, fiscal_year, form_type (10-K/10-Q/8-K/6-K/20-F), filing_date, accession_no, provenance_id.
- **`trace_observation`** — id, security_id, trade_price, trade_size, trade_datetime, side (nullable), provenance_id. Raw, one row per trade. Never labeled as an EOD valuation.
- **`trace_derived_metric`** — id, security_id, metric_date, metric (`vwap`|`last_trade`|`bid`|`ask`|`high`|`low`|`trade_count`|`days_since_last_trade`|`weekly_price_change`|`monthly_price_change`|`liquidity_flag`|`stale_flag`), value, provenance_id (→ `transformation = calculated`, `calculation_id` set).
- **`fred_series_registry`** — series_id, title, category, units, frequency, discontinued (bool), redistribution_allowed (bool), last_synced_at.
- **`fred_observation`** — id, series_id, obs_date, value, provenance_id.
- **`court_docket`** — id, issuer_id (nullable), court, docket_number, case_name, nature_of_suit, date_filed, provenance_id.
- **`court_docket_entry`** — id, docket_id, entry_number, entry_date, description, document_available (bool — never fetch sealed), provenance_id.
- **`docket_document`** — id, docket_entry_id, availability (`recap_available`|`unavailable_admin_upload_needed`|`admin_uploaded`), recap_document_url (nullable), raw_payload_id (nullable FK → `raw_provider_payload`), uploaded_by (nullable), uploaded_at (nullable), provenance_id. See §9 for the corrected provenance attribution on admin uploads.
- **`figi_mapping`** — id, security_id, figi, composite_figi, share_class_figi, mapping_query (jsonb), provenance_id.
- **`disabled_provider_capability`** — provider, dataset_name, business_capability_description, required_config_keys, licensing_note. Static seed data — no provenance needed.
- **`synthetic_flag`** — every synthetic row sets `classification = synthetic` on its provenance AND carries a denormalized `is_synthetic` boolean for cheap UI filtering, tagged `SYNTHETIC_DEMO_DATA` in a `synthetic_reason` text column.

### 4.6 `capital_structure_position` (new)

| column | type | notes |
|---|---|---|
| `id` | uuid PK | |
| `issuer_id` | uuid FK → `issuer.id` | |
| `security_id` | uuid FK, nullable | linked security when one exists; some layers (e.g. a revolver with no CUSIP) may have no `security` row |
| `layer_name` | text | e.g. "Revolving Credit Facility", "First Lien Term Loan B" |
| `rank_order` | int | ordering key for rendering the stack top (most senior) to bottom |
| `instrument_type` | text | `revolver`\|`first_lien_loan`\|`first_lien_notes`\|`second_lien`\|`unsecured`\|`subordinated`\|`preferred_equity`\|`common_equity` |
| `seniority` | text | |
| `lien_position` | text, nullable | |
| `secured` | bool | |
| `guarantor_scope` | text, nullable | |
| `amount_outstanding` | numeric | |
| `currency` | text | |
| `maturity_date` | date, nullable | |
| `price` | numeric, nullable | reported/observed, when applicable |
| `enterprise_value_coverage` | numeric, nullable | **calculated**, see §6 labeling rule |
| `illustrative_recovery` | numeric, nullable | **calculated + scenario-based**, see §6 labeling rule |
| `recovery_scenario` | text, nullable | which scenario (e.g. "base case EV $X") the recovery figure assumes |
| `provenance_id` | uuid FK | |
| `is_synthetic` | bool | |
| `synthetic_reason` | text, nullable | |

### 4.7 Watchlists (approved, unchanged — many-to-many)

- **`watchlist`** — id, slug, name, description, list_type (`coverage`|`benchmark`), created_at. Seeded with the eleven named lists in §14.
- **`watchlist_membership`** — id, watchlist_id, issuer_id, added_at, rationale_note. Unique on `(watchlist_id, issuer_id)`.

### 4.8 Entitlement engine (approved, unchanged)

- **`data_entitlement`** — id, provider, dataset, legal_entity, environment, permitted_users (jsonb), permitted_use, storage_allowed, retention_period_days, derived_data_permission, ai_processing_permission, embedding_permission, display_permission, redistribution_permission, effective_date, expiration_date, contract_reference.
- **`policy_check(action, entitlement, context)`** — pure Python function, single choke point. Actions: `display`, `export`, `send_to_llm`, `create_embedding`, `prompt_inclusion`, `document_download`, `api_expose`. Every route/service calls this before touching licensed data.
- Provider feature flags (`SP_GLOBAL_ENABLED`, `PACER_ENABLED`, etc.) are checked upstream — a disabled provider never reaches the entitlement layer at all.

### 4.9 `embedding` (pgvector — gated, approved, unchanged)

| column | type | notes |
|---|---|---|
| `id` | uuid PK | |
| `source_table` | text | which canonical table the embedded text came from |
| `source_id` | uuid | row id in that table |
| `vector` | `vector(n)` (pgvector) | embedding, dimension per chosen model |
| `model` | text | embedding model identifier |
| `provenance_id` | uuid FK | classification always `ai_extracted`; creation only after `policy_check(action="create_embedding", ...)` passes |

### 4.10 Research notes & documents (new)

- **`research_note`** — id, issuer_id, security_id (nullable), title, body_markdown, author_user_id, thesis_status, conviction (nullable), bull_case (nullable), base_case (nullable), bear_case (nullable), catalysts (nullable), risks (nullable), invalidation_conditions (nullable), access_classification, created_at, updated_at.
- **`research_note_version`** — id, research_note_id, version_number, body_markdown, thesis_status, conviction, bull_case, base_case, bear_case, catalysts, risks, invalidation_conditions, edited_by, edited_at. Full snapshot per edit — not a diff — so any prior version renders standalone.
- **`research_document`** — id, issuer_id, security_id (nullable), document_type, title, original_filename, raw_payload_id (FK → `raw_provider_payload`), extracted_text (nullable), document_date (nullable), confidentiality_classification, uploaded_by (nullable), provenance_id, created_at. Distinct from `docket_document` — this is for general research material (broker notes, analyst decks, internal memos), not court filings.

### 4.11 Alerts (new)

- **`alert_rule`** — id, owner_user_id, name, rule_type, rule_config (jsonb), watchlist_id (nullable), issuer_id (nullable), security_id (nullable), enabled, created_at, updated_at.
- **`alert_event`** — id, alert_rule_id, issuer_id (nullable), security_id (nullable), triggered_at, previous_value (jsonb, nullable), current_value (jsonb, nullable), explanation, provenance_id, acknowledged_at (nullable), acknowledged_by (nullable).

Initial `rule_type`s: `price_below_threshold`, `weekly_decline_above_threshold`,
`stale_price`, `maturity_within_period`, `new_sec_filing`, `new_court_docket_entry`,
`rating_downgrade` (only fires when a rating is actually available — no synthetic
ratings), `restructuring_status_change`, `leverage_above_threshold`.

### 4.12 Users, roles, audit (new)

- **`user`** — id, email, display_name, created_at.
- **`role`** — id, name (`investment_professional`|`research_analyst`|`administrator`).
- **`user_role`** — user_id, role_id.
- **`audit_event`** — id, user_id (nullable — system-initiated events allowed), event_type, entity_table, entity_id (nullable), detail (jsonb), occurred_at.

At minimum, audited: research-note creation/update, document upload/access,
watchlist changes, alert-rule changes, entitlement changes, administrative actions,
and AI assistant queries that touch restricted (licensed/internal) data.

Authentication may stay disabled for the first demo (`AUTH_ENABLED=false`, every
request treated as an implicit demo admin), but the schema and route dependencies are
built so Supabase Auth JWT validation can be turned on later without a redesign —
`user.id` is designed to align with a future Supabase `auth.users.id`.

### 4.13 Search infrastructure (new)

- A `tsvector` generated column (or maintained trigger column) on `issuer`
  (legal_name, ticker), `security` (description, identifiers), `court_docket`
  (case_name, docket_number), `research_note` (title, body), and `research_document`
  (title, extracted_text), combined into a single `search_index` materialized-ish
  approach: either one `search_document` table (id, entity_table, entity_id,
  tsvector_col, plain_text_for_trigram, updated_at) refreshed on write, or per-table
  `tsvector` columns unioned at query time. Decision deferred to implementation
  (§16 build order step 12), but the contract is fixed: exact identifier match
  (CIK/CUSIP/ISIN/FIGI/ticker) ranks above fuzzy name/text match, and `pg_trgm`
  similarity is used only for the fuzzy tier.

---

## 5. Credit Universe — primary application workflow

The CFO's first stated need: reduce manual work for investment professionals via a
screenable universe. Because the public-data POC mixes real bonds with synthetic loan
records (loan pricing has no public source, per the original brief), the screen is
named **Credit Universe**, with a **Loan Universe** filter/view inside it — not a
separately named page — so the synthetic-vs-real boundary is a filter state, not a
hidden distinction.

**Frontend**: `web/src/pages/CreditUniversePage.tsx` — the landing page after
login/demo entry.

**Backend**: `backend/app/api/routes/credit_universe.py` +
`backend/app/services/credit_universe_service.py` (assembles rows from
`security_repository`, `financial_fact_repository`, `market_data_repository`,
`capital_structure_repository`, applying `policy_check` per licensed field before
inclusion).

### 5.1 Columns

issuer · security/instrument name · instrument type · bond or loan · seniority · lien
· secured/unsecured · CUSIP · ISIN · FIGI · bid · ask · last trade · calculated VWAP ·
weekly price change · monthly price change · maturity date · amount outstanding ·
coupon · benchmark · spread · rating (when available) · sector · leverage · distress/
restructuring status · source · as-of date · freshness · synthetic-data badge.

Every calculated column (VWAP, weekly/monthly price change, leverage where derived)
carries a `calculated` badge distinct from `reported` columns, consistent with the
provenance model — this is a UI convention, not a new data-model concept, since the
underlying value already has `provenance.transformation = calculated`.

### 5.2 Filters

instrument type · price range · price movement · maturity range · sector · seniority ·
lien · rating · watchlist · distressed/restructuring status · source ·
public/licensed/synthetic classification · stale data.

### 5.3 Supported behaviors

- Sorting, pagination, column visibility.
- Saved filters (per-user, stored server-side once `user` exists — §4.12).
- URL-persisted filters (filter state round-trips through query params so a link is
  shareable/bookmarkable independent of saved-filter storage).
- CSV export — gated by `policy_check(action="export", ...)` per included field;
  licensed-provider fields that fail the check are excluded from the export with a
  visible note, never silently dropped without explanation.
- Drill-down to issuer detail (`IssuerPage`) and instrument detail.
- Every important fact in the row remains clickable/hoverable to its lineage — the
  provenance view isn't a separate destination only, it's reachable inline.

---

## 6. Dashboard (new)

**Frontend**: `web/src/pages/DashboardPage.tsx`.
**Backend**: `backend/app/api/routes/dashboard.py` +
`backend/app/services/dashboard_service.py`.

**Metrics**: issuer count, security count, real vs. synthetic instrument count, recent
TRACE activity, largest price decliners, recent SEC filings, recent bankruptcy/docket
events, maturities in the next 12 and 24 months, stale-data count, recent watchlist
changes, recent alerts.

**Charts**: security count by instrument type, maturity wall by year, price bucket
distribution, sector distribution, watchlist distribution, public vs. synthetic data
mix.

Every metric and chart series carries source + as-of metadata in its API response
(even when the UI shows it as a small "as of {date}" caption rather than a full
lineage table) — no dashboard number is a bare integer with no origin.

---

## 7. Capital Structure (new)

**Frontend**: `web/src/pages/CapitalStructurePage.tsx`.
**Backend**: `backend/app/api/routes/capital_structure.py` (issuer-level: "give me the
full stack for issuer X"), backed by `capital_structure_repository`.

Renders `capital_structure_position` rows for an issuer in priority order: revolver →
first-lien loan → first-lien notes → second-lien debt → unsecured debt → subordinated
debt → preferred equity → common equity.

**Labeling rule (hard requirement):** any `enterprise_value_coverage` or
`illustrative_recovery` value is rendered with all four of: **calculated**,
**scenario-based**, **illustrative**, **not a market fact** — every time it's shown,
not just once on a legend. `recovery_scenario` text is always shown alongside the
number so the assumption is visible, not just the output.

---

## 8. Universal Search (new)

**Frontend**: `web/src/pages/SearchPage.tsx` + a global search component in the
application header (`web/src/components/GlobalSearch.tsx`).
**Backend**: `backend/app/api/routes/search.py` +
`backend/app/repositories/search_repository.py`.

**Searches across**: issuer legal/common names, ticker, CIK, LEI, CUSIP, ISIN, FIGI,
security description, court case name, docket number, research-note text, document
title, document extracted text.

**Mechanics**: PostgreSQL full-text search (`tsvector`/`tsquery`) for text relevance,
`pg_trgm` similarity for fuzzy/typo-tolerant matching on names and free text. Query
flow: first check for an exact identifier match (CIK/CUSIP/ISIN/FIGI/ticker/docket
number) — those results always rank above fuzzy name/text matches, never interleaved
by a single blended score. **No automatic entity merging** — a fuzzy name match never
causes two `issuer` rows to be silently combined; deduping/merging, if ever needed, is
a manual administrative action with its own audit trail, out of scope for this POC.

---

## 9. AI Research Assistant (new — UI added; backend AI layer already planned)

**Frontend**: `web/src/pages/ResearchAssistantPage.tsx`.
**Backend**: `backend/app/api/routes/assistant.py`, calling `backend/app/ai/rag.py`
and the tool layer below.

**No arbitrary SQL, ever.** The assistant calls a fixed, typed tool set — each tool is
a thin wrapper over an existing repository/service call, so the assistant's access is
exactly as broad as the read APIs a human user already has, no broader:

- `search_credit_universe`
- `get_issuer`
- `get_instrument`
- `get_capital_structure`
- `get_financial_facts`
- `get_trace_history`
- `get_sec_filings`
- `get_court_dockets`
- `get_research_notes`
- `get_documents`
- `get_watchlists`
- `get_alerts`

**Example questions it must answer:** "Show first-lien loans below 80." / "Which
securities fell more than five points this month?" / "Which issuers have maturities
in the next two years?" / "Summarize the capital structure of this issuer." / "Why is
this issuer on the distressed watchlist?" / "Which credits have stale market data?" /
"Show recent bankruptcy docket activity." / "Compare this issuer with the
investment-grade benchmark group."

**Every answer must:**
- Cite the internal source records it used (linking back to the same lineage view
  used elsewhere in the app).
- Include provider and as-of date per cited fact.
- Distinguish reported facts, calculated values, synthetic data, AI-extracted facts,
  and analyst opinions (research notes) — these are never blended into one
  undifferentiated sentence.
- State plainly when requested data is unavailable, rather than guessing or
  extrapolating.
- Pass `policy_check` (action `prompt_inclusion`, then `send_to_llm`) for every
  underlying record before it's allowed into the prompt at all — a licensed record
  the assistant can't legally use is simply excluded from its context, with the
  answer noting the gap rather than silently working around it.

---

## 10. LLM provider abstraction (new)

Anthropic remains the default and only *implemented* provider for this POC, but no
application code depends on the Anthropic SDK directly — everything goes through a
`Protocol`:

```python
class LLMProvider(Protocol):
    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        ...

    async def call_tools(self, request: ToolCallRequest) -> ToolCallResponse:
        ...

    async def create_embeddings(self, texts: list[str]) -> list[list[float]]:
        ...
```

`backend/app/ai/providers/`:
- `anthropic_provider.py` — **implemented in this build.**
- `openai_provider.py` — interface/stub only, documented, not implemented.
- `azure_openai_provider.py` — interface/stub only.
- `ollama_provider.py` — interface/stub only.

`LLM_PROVIDER` selects the implementation at startup (`backend/app/ai/factory.py`
raises a clear config error if set to a provider whose class isn't implemented yet,
rather than silently falling back). Chat/tool-calling and embeddings are kept
provider-aware independently (`complete`/`call_tools` vs. `create_embeddings`) because
production may eventually source embeddings from a different vendor than chat.

---

## 11. Research Notes & Documents workspace (new)

**Frontend**: `web/src/pages/ResearchWorkspacePage.tsx`.
**Backend**: `backend/app/api/routes/research.py`, backed by
`research_repository.py` and `document_repository.py`.

Supports: creating/editing notes (each edit writes a `research_note_version` snapshot
before applying the update), note version history browsing, issuer/security
associations, tags, search (feeds into §8), access classification, source-document
links (a note can cite one or more `research_document`/`docket_document` rows), and
the bull/base/bear case fields from §4.10.

Every create/update on `research_note` writes a matching `audit_event` — this is the
first concrete audited-write path in the app and sets the pattern the other audited
actions in §4.12 follow.

---

## 12. Alerts (new)

**Frontend**: an alerts panel embedded in `DashboardPage` plus a dedicated view for
full history/management (`web/src/pages/AlertsPage.tsx` or a tab within Dashboard —
finalized during step 10 of the build order).
**Backend**: `backend/app/api/routes/alerts.py`, backed by `alert_repository.py`, and
an evaluation job (`backend/app/services/alert_engine.py`) that checks enabled
`alert_rule`s against current data and writes `alert_event` rows.

Every alert explains: the rule that fired, the prior value, the current value, the
source, the as-of date, and the trigger time — `alert_event.explanation` is a
generated human-readable sentence built from those fields, not free text a human has
to reconstruct meaning from.

---

## 13. Users, Roles, Audit (new)

Minimal domain models per §4.12: `user`, `role`, `user_role`, `audit_event`. Three
roles: `investment_professional`, `research_analyst`, `administrator`. Route
dependencies check role where an action is role-gated (e.g. admin-only manual PACER
document upload, entitlement configuration), but with `AUTH_ENABLED=false` for the
first demo, every request is treated as an implicit administrator so the full app is
explorable without standing up real auth — the dependency layer is structured so
flipping `AUTH_ENABLED=true` later and wiring Supabase Auth JWT validation doesn't
require touching route logic, only the dependency's implementation.

---

## 14. Demo watchlists (approved, unchanged — eleven named lists)

Ten curated `watchlist` rows plus one benchmark list, each with `watchlist_membership`
rows. Membership is many-to-many. A list is a curation decision, never a computed
verdict — the issuer page always derives and dates actual status from real source
records independent of which lists an issuer is on. Candidates verified in build step
3 (real CIK, real EDGAR filing history, real CourtListener docket where implied)
before being written into seed data; anything failing verification is swapped or
dropped, not faked.

| Watchlist | Candidate issuers | Rationale |
|---|---|---|
| ⭐ Distressed Watchlist | Rite Aid Corp., Lumen Technologies, Mallinckrodt plc | Public filers with well-documented, dated credit distress |
| ⭐ Recent Bankruptcies | Rite Aid Corp. (Ch11 2023), Diebold Nixdorf (Ch11 2023), Yellow Corp. (Ch11 2023) | Ch11 filings within the last ~2–3 years, real CourtListener/RECAP dockets expected |
| ⭐ Liability Management Transactions | Carvana Co., Mallinckrodt plc, Community Health Systems | Public issuers with documented exchange/uptiering-style LME activity in SEC filings |
| ⭐ Upcoming Maturity Wall | Community Health Systems, Lumen Technologies, Office Properties Income Trust | Near-term bond/loan maturities derivable from SEC filings + OpenFIGI security data |
| ⭐ Fallen Angels | Ford Motor Co., Occidental Petroleum, Kraft Heinz Co. | Lost investment-grade rating within recent history, large public filers |
| ⭐ High Yield | Community Health Systems, Lumen Technologies, DISH Network / EchoStar | Below-investment-grade public issuers with actively traded bonds (TRACE-eligible) |
| ⭐ Leveraged Loans | Mallinckrodt plc, Community Health Systems, Lumen Technologies | Loan pricing itself is not public — loan-level fields render as `SYNTHETIC_DEMO_DATA`; issuer identity/financials remain real |
| ⭐ Potential Recovery Candidates | Diebold Nixdorf, Chesapeake Energy / Expand Energy, Carvana Co. | Post-emergence/post-distress issuers with improving dated financials |
| ⭐ Healthcare Credits | Community Health Systems, Mallinckrodt plc | Public healthcare-sector issuers with credit-relevant history |
| ⭐ Consumer & Retail | Rite Aid Corp., Carvana Co., Big Lots Inc. | Public consumer/retail issuers spanning distress to turnaround |
| 🔵 Investment Grade / Comparison (`list_type = 'benchmark'`) | Johnson & Johnson, Microsoft Corp. | Clean baseline for leverage, interest coverage, liquidity, maturity profile, spread behavior, and data quality — never mixed into distressed-screening views |

---

## 15. PACER handling (revised — provenance attribution fix)

**Problem in the prior revision:** every manually uploaded court document was marked
`provider = pacer` in its provenance, which falsely implies the system retrieved it
through a real PACER integration. Fixed as follows:

- `admin_upload` is a valid `provenance.provider` value (§4.1). It is used for
  **every** manually uploaded document, regardless of what the document's original
  source actually was.
- `provenance.original_source` records what the admin attests the document actually
  came from: `pacer`, `courtlistener`, `issuer_site`, or `other`.
  `source_attested_by` / `source_attested_at` record who made that attestation and
  when — the claim is explicit and traceable, not baked silently into `provider`.
- `provider = pacer` is reserved exclusively for documents the system actually
  retrieved through a real, future PACER integration. It is never set as a stand-in
  for "this document is from a PACER-adjacent source" when the retrieval was manual.
- `PacerProvider` (`backend/app/providers/pacer/provider.py`) exists as a real
  interface + `PACER_ENABLED` flag (defaults false, enforced regardless of
  credentials present). No method performs a network call, login, or document
  purchase in this build; calling it while disabled returns a typed "not enabled"
  result.
- When a `court_docket_entry` has no RECAP-available document, `docket_document.availability`
  is set to `unavailable_admin_upload_needed`. The UI shows case + docket metadata
  (always, from CourtListener), the document marked unavailable, a "PACER retrieval
  not enabled" status badge, and an admin-only manual upload form. Uploads go to
  Supabase Storage (never Railway's ephemeral disk), recorded as a
  `raw_provider_payload` row, with a `provenance` row using
  `provider = admin_upload` + the `original_source` fields above — not `pacer`.
- `PACER_USERNAME` / `PACER_PASSWORD` stay in `.env.example` as blank/optional; the
  app boots and runs fully without them.

**Future production PACER integration** (documented, not built) still requires:
explicit business approval for per-page costs, credential management, cost controls,
download limits, audit logging (distinct from the general provenance trail, since
PACER retrieval has real monetary cost per action), and legal/compliance review.

---

## 16. Freshness (revised — computed, not persisted)

`provenance` no longer stores a `freshness` column. `freshness` (`live`/`cached`/
`stale`) is exposed as a computed API property, derived at read time from
`provenance.retrieved_at` plus a per-provider TTL policy (e.g. TRACE trades stale
after N hours, FRED series stale after their publication cadence, SEC filings stale
relative to next expected filing type). This avoids a stored value silently drifting
out of sync with "now." If a historical snapshot of freshness-at-a-point-in-time is
ever needed (e.g. for a dashboard trend of data staleness over time), it is stored
under the explicit name `freshness_at_ingestion`, never reusing the `freshness` name,
so no code path can confuse "freshness as of ingestion" with "freshness right now."

---

## 17. Module list

```
backend/
  app/
    main.py                    # FastAPI app: CORS, routers, /health
    config.py                    # pydantic-settings: DATABASE_URL, SUPABASE_*, provider keys, feature flags, AUTH_ENABLED, LLM_PROVIDER
    db/
      base.py
      session.py
    models/                       # SQLAlchemy ORM models — persistence only, never imported by providers
      provenance.py                 # Provenance, Calculation, CalculationInput
      raw_provider_payload.py
      issuer.py
      security.py
      capital_structure.py            # CapitalStructurePosition
      financial_fact.py
      trace.py
      fred.py
      court.py                          # CourtDocket, CourtDocketEntry, DocketDocument
      figi.py
      disabled_provider.py
      watchlist.py
      entitlement.py
      embedding.py
      research.py                         # ResearchNote, ResearchNoteVersion, ResearchDocument
      alert.py                              # AlertRule, AlertEvent
      user.py                                 # User, Role, UserRole
      audit.py                                  # AuditEvent
      search.py                                   # search index table(s)
    domain/                       # §3 — canonical objects, provider-facing
      issuer.py
      security.py
      capital_structure.py
      financials.py
      market_data.py
      research.py
      documents.py
      alerts.py
      provenance.py
      credit_events.py
    repositories/                 # §3 — the only layer that opens a session
      issuer_repository.py
      security_repository.py
      capital_structure_repository.py
      financial_fact_repository.py
      market_data_repository.py
      provenance_repository.py
      research_repository.py
      document_repository.py
      alert_repository.py
      watchlist_repository.py
      search_repository.py
      audit_repository.py
    schemas/                     # Pydantic 2 request/response models
    core/
      entitlement.py                # policy_check()
      types.py
      freshness.py                    # TTL policy + live freshness computation (§16)
    providers/
      base/
        http_client.py
        raw_payload_store.py
        provider_base.py
      sec_edgar/
      finra_trace/
        oauth.py
        client.py
        local_dataset_loader.py
        derive.py
        provider.py
      openfigi/
      fred/
      courtlistener/
      pacer/
        provider.py                    # §15
      disabled/
        sp_global_loan_pricing.py
        sp_global_loan_reference.py
        octus.py
        bloomberg.py
        lseg_lpc.py
    synthetic/
      leveraged_loan_generator.py
    ai/
      providers/
        base.py                        # LLMProvider Protocol (§10)
        anthropic_provider.py            # implemented
        openai_provider.py                 # stub/interface only
        azure_openai_provider.py             # stub/interface only
        ollama_provider.py                     # stub/interface only
      factory.py                       # LLM_PROVIDER -> implementation
      llm_gate.py                        # wraps policy_check for send_to_llm/create_embedding/prompt_inclusion
      rag.py                               # citation-enforcing answer generation
      embeddings.py                          # pgvector embedding creation, gated
      tools/                                   # §9 — typed tool wrappers over repositories
        search_credit_universe.py
        get_issuer.py
        get_instrument.py
        get_capital_structure.py
        get_financial_facts.py
        get_trace_history.py
        get_sec_filings.py
        get_court_dockets.py
        get_research_notes.py
        get_documents.py
        get_watchlists.py
        get_alerts.py
    services/                     # cross-repository orchestration for a page/feature
      credit_universe_service.py
      dashboard_service.py
      alert_engine.py
    api/
      routes/
        health.py
        credit_universe.py
        dashboard.py
        issuer.py
        capital_structure.py
        lineage.py
        providers_status.py
        watchlists.py
        docket_documents.py
        search.py
        assistant.py
        research.py
        alerts.py
  alembic/
    env.py                          # uses DIRECT_DATABASE_URL
    versions/
  scripts/
    verify.py
    fetch_seed_data.py
    fetch_trace_sample.py
  pyproject.toml
  alembic.ini
  Dockerfile

web/
  src/
    main.tsx
    App.tsx
    api/
      client.ts
    queries/                        # TanStack Query hooks per resource
    pages/
      CreditUniversePage.tsx           # §5 — landing page
      DashboardPage.tsx                  # §6
      CapitalStructurePage.tsx             # §7
      SearchPage.tsx                         # §8
      ResearchAssistantPage.tsx                # §9
      ResearchWorkspacePage.tsx                  # §11
      AlertsPage.tsx                                # §12
      IssuerPage.tsx
      LineageView.tsx
      ProviderStatus.tsx
      DocketView.tsx
      WatchlistsPage.tsx
    components/
      GlobalSearch.tsx                 # header search, §8
      ProvenanceBadge.tsx
      SyntheticDataBadge.tsx
      CalculatedValueBadge.tsx
      DataTable.tsx                      # TanStack Table wrapper (Credit Universe + others)
  vite.config.ts
  package.json
  .env.example

.env.example
```

---

## 18. Build order (revised — vertical slice)

1. Supabase connection, Alembic migrations skeleton, FastAPI `/health`, React shell
   (routing + layout, no real data yet).
2. Provenance, `raw_provider_payload`, `calculation` + `calculation_input`, and the
   entitlement engine — foundation every later step depends on, tested against
   synthetic cases before any real provider exists.
3. SEC adapter vertical slice: real issuer + real filing + real financial fact,
   through the full domain-layer path (Provider DTO → Normalizer → Canonical Object →
   Repository → Postgres), proven end-to-end for one issuer before moving on.
4. Credit Universe initial page, backed by seeded canonical securities (real SEC-
   sourced bonds; synthetic loan rows clearly tagged) — the primary workflow becomes
   visible early rather than last.
5. OpenFIGI and FRED adapters, feeding more Credit Universe columns.
6. Issuer detail page and Capital Structure page/model.
7. CourtListener adapter and docket view.
8. Watchlists (ten coverage + one benchmark) and the benchmark comparison view.
9. Research notes/documents and audit events (first audited-write path).
10. Alerts (rule model, evaluation engine, panel/page).
11. TRACE adapter/sample (real OAuth2 flow + legally-public sample file), feeding
    Credit Universe's bid/ask/last-trade/VWAP/price-change columns.
12. Universal Search (full-text + trigram, exact-match ranking).
13. AI Research Assistant, tool layer, and gated embeddings.
14. Disabled licensed-provider capability cards (five vendor stubs).
15. Railway/Vercel deployment validation (`/health` green, frontend reaching the API,
    Alembic migrations applied via `DIRECT_DATABASE_URL`).
16. End-to-end verification against the completion criteria (§20).

Commit at each numbered milestone.

---

## 19. Environment variables (`.env.example`, never commit real values)

```
# Supabase / database — shared project, isolated via the `nexus` Postgres schema
# (ADR-013). SUPABASE_ANON_KEY is reserved for future frontend/RLS use;
# SUPABASE_SERVICE_KEY is backend-only, never exposed via VITE_ vars or frontend code.
DATABASE_URL=
DIRECT_DATABASE_URL=
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_KEY=
SUPABASE_STORAGE_BUCKET=

# Public data providers
SEC_USER_AGENT=
FRED_API_KEY=
OPENFIGI_API_KEY=
COURTLISTENER_API_TOKEN=

# FINRA TRACE (marketplace OAuth2 — real flow, unused in demo path)
FINRA_CLIENT_ID=
FINRA_CLIENT_SECRET=

# PACER — inactive/optional, see §15. Never required to boot the app.
PACER_USERNAME=
PACER_PASSWORD=
PACER_ENABLED=false

# Disabled/licensed providers — interfaces only
SP_GLOBAL_ENABLED=false
OCTUS_ENABLED=false
BLOOMBERG_ENABLED=false
LSEG_LPC_ENABLED=false

# AI / LLM gate (Milestone 6.5, §24 — provider-specific credentials, never a
# shared generic secret; the factory validates only what LLM_PROVIDER selects
# and never silently falls back to a different provider)
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=claude-sonnet-5
OPENAI_API_KEY=
OPENAI_MODEL=
AZURE_OPENAI_API_KEY=
AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_MODEL=
# Reserved for a future milestone — chat/tool-calling and embeddings may end up
# sourced from different providers; unused until embeddings are implemented.
EMBEDDING_PROVIDER=

# Auth (disabled for first demo; architecture supports Supabase Auth JWT later)
AUTH_ENABLED=false

# Web/CORS
FRONTEND_URL=
CORS_ALLOWED_ORIGINS=

# Frontend (web/.env.example)
VITE_API_BASE_URL=
```

---

## 20. Completion Criteria

1. Application runs locally with FastAPI and Vite while connected directly to Supabase.
2. Railway backend deploy succeeds and `/health` passes.
3. Vercel frontend deploy succeeds and reaches the Railway API.
4. A real SEC issuer and filing are loaded with raw payload and provenance.
5. Real XBRL financial facts are displayed.
6. A real OpenFIGI mapping is displayed.
7. Real FRED observations are displayed.
8. A real CourtListener docket is displayed.
9. Real TRACE history is displayed if a legally reusable sample is found; otherwise
   the UI clearly marks TRACE real-data status as pending and does not fabricate it.
10. Credit Universe screen works with sorting, filtering, provenance, and
    synthetic-data labeling.
11. Issuer detail joins at least three real sources.
12. Capital Structure page works with clear scenario labeling.
13. Watchlists show ten coverage lists plus one separated benchmark list.
14. Research notes can be created and versioned.
15. At least three alert types can trigger from seeded/real data.
16. AI Research Assistant uses predefined tools and produces cited answers.
17. Licensed data cannot be displayed, exported, embedded, or sent to an LLM without a
    passing policy check.
18. Backend tests, frontend tests, linting, and production builds pass.
19. No secrets are committed.
20. No durable data depends on Railway local disk.

---

## 21. Decisions log

1. **Database**: Supabase-managed Postgres only, every environment. `pgvector` +
   `pg_trgm` enabled. No local Postgres, no Postgres in Docker Compose, no SQLite.
2. **ORM/migrations**: SQLAlchemy 2 + Alembic, `DATABASE_URL` at runtime,
   `DIRECT_DATABASE_URL` for migrations.
3. **Backend**: Python 3.12, FastAPI, Pydantic 2, on Railway; `/health` for Railway's
   health check; Railway filesystem never used for durable storage.
4. **Frontend**: React + TypeScript + Vite + Material UI + TanStack Query/Table, on
   Vercel, talking to Railway via `VITE_API_BASE_URL`.
5. **Domain layer**: providers never touch SQLAlchemy directly — Provider DTO →
   Normalizer → Canonical Domain Object → Repository → Postgres (§3).
6. **Raw/document storage**: normalized records and small raw JSON in Postgres
   (`raw_provider_payload.payload_json`); filings, court documents, TRACE extract
   files, and uploaded documents in Supabase Storage
   (`raw_provider_payload.storage_object_path`). Railway disk holds only transient
   processing files.
7. **TRACE demo dataset**: no fabricated trade data. A legally-public FINRA-published
   sample/historic extract is downloaded via `fetch_trace_sample.py` into Supabase
   Storage, source URL + retrieval date recorded. If none exists, the gap is reported,
   not papered over with synthetic data mislabeled as real (Completion Criterion 9).
8. **LLM_PROVIDER**: Anthropic implemented first; OpenAI/Azure OpenAI/Ollama planned
   as interface stubs behind the `LLMProvider` Protocol (§10).
9. **PACER**: kept in `.env.example` as optional/inactive — not required to run the
   app. CourtListener/RECAP is the primary docket source. Admin uploads are attributed
   via `provider = admin_upload` + `original_source`, never mislabeled as `pacer`
   (§15).
10. **Demo watchlists**: eleven named lists (§14).
11. **Docker**: kept only as an optional Railway packaging Dockerfile for the FastAPI
    app — never for a database, never in a Compose file.
12. **Credit Universe** is the primary landing workflow, not the issuer/lineage pages
    from the prior revision — those remain as drill-down destinations, not the front
    door.
13. **Auth**: disabled for the first demo (`AUTH_ENABLED=false`), but `user`/`role`/
    `user_role`/`audit_event` and route dependencies are built to support Supabase
    Auth JWT validation being switched on later without a route-logic rewrite.
14. **Git**: this directory has no repo yet; `git init` and commit at each milestone.
15. **Supabase project sharing** (ADR-013): Nexus reuses an existing Supabase project
    shared with another application instead of a dedicated one; isolation is by
    Postgres schema (`nexus`), never by convention alone — see §2 Stack and
    `ARCHITECTURE_DECISIONS.md` ADR-013.

---

## 22. What I will NOT do

- Invent endpoints/fields not in this brief's verified provider contracts.
- Present a single TRACE trade as an official EOD price.
- Hard-code "issuer X is distressed" — status is derived from dated records at render time.
- Fetch sealed/restricted CourtListener/PACER material.
- Perform any real PACER login, document purchase, or paid request in this build.
- Require PACER credentials for the app to boot or run.
- Mark a manually uploaded document's provenance as `provider = pacer` unless the
  system actually retrieved it through a real PACER integration.
- Let any licensed-provider content reach an LLM call, or get embedded via pgvector,
  without a passing `policy_check`.
- Let the AI Research Assistant execute arbitrary SQL or bypass the fixed tool set.
- Automatically merge issuer/security entities on fuzzy name similarity.
- Persist `freshness` as a stored fact that silently drifts from the truth — it's
  always computed at read time.
- Let a provider module call SQLAlchemy session operations directly — persistence
  goes through repositories only.
- Reduce scope back to only issuer/lineage/provider-status/docket pages — Credit
  Universe is the primary product workflow.
- Run or configure a local/Dockerized PostgreSQL instance, or a SQLite fallback, in
  any environment.
- Rely on Railway's local filesystem for anything durable.
- Commit secrets, `.env`, or cached response data that could contain PII/licensed content.
- Implement, schedule, or wire up any item from §23 (Future Architecture / Phase 2
  Extensions) in this build. Those are documented for architectural continuity only —
  no `credit_event` table, as-of query params, Portfolio module, Data Quality score,
  or background job scheduler exists in Version 1.

---

## 23. Future Architecture (Phase 2 Extensions — not in Version 1 scope)

**Version 1 is feature-complete as planned in §1–22.** Everything below is documented
now so later work builds *with* the existing architecture instead of against it — none
of it changes the Version 1 module list (§17), build order (§18), or completion
criteria (§20). No tables, routes, or jobs described here are created in this phase.

### 23.1 Canonical Credit Event model

Today, event-shaped information is scattered: SEC filings live in `financial_fact` /
raw filing metadata, docket activity in `court_docket_entry`, alerts in `alert_event`,
and future licensed-provider events (Bloomberg, Octus) would each want their own shape
again. Phase 2 introduces one canonical event stream so every consumer reads the same
model instead of each feature inventing its own.

- **Domain object**: `backend/app/domain/credit_event.py` (future).
- **Persistence model**: `credit_event` — id, issuer_id, security_id (nullable),
  event_type, event_date, headline, summary, severity, status, source_provider,
  provenance_id, created_at.
- **Example `event_type`s**: `bankruptcy_filed`, `bankruptcy_emerged`,
  `missed_interest_payment`, `debt_exchange`, `liability_management_transaction`,
  `covenant_breach`, `maturity_extension`, `refinancing`, `new_financing`,
  `rating_upgrade`, `rating_downgrade`, `dividend_suspension`, `earnings_release`,
  `sec_filing`, `court_docket`, `management_change`, `asset_sale`.
- **Intended consumers**: Dashboard, AI Research Assistant, Alerts, an Issuer Timeline
  view, and the future Portfolio module (§23.3) — all reading one event stream instead
  of each querying provider-specific tables directly.
- **How it fits the existing architecture**: `credit_event` rows would be populated by
  normalizers as a *secondary* output alongside the existing canonical objects (a
  bankruptcy-filing docket entry produces both a `court_docket_entry` row and a
  `credit_event` row), through the same Provider DTO → Normalizer → Canonical Domain
  Object → Repository pipeline (§3) — never a separate ingestion path, and never
  without its own `provenance_id`.
- **Not implemented now**: no `credit_event` table, no normalizer changes, no
  consumer wiring. Dashboard/Alerts/Assistant continue reading provider-specific
  tables directly in Version 1.

### 23.2 Time Machine / As-Of architecture ("Historical Research Mode")

**Target capability**: an analyst asks "What did we know on January 15, 2025?" or
"Show Credit Universe exactly as it appeared six months ago," and the app answers
using only information that was actually known at that time — not today's restated
values.

**Concepts**: `effective_date` (when a fact was true in the world), `known_at` (when
we learned it — already captured today as `provenance.retrieved_at`), `valid_from` /
`valid_to` (the window during which a given version of a mutable record was the
current one).

**Why the existing provenance model already supports most of this**: `provenance`
already separates `as_of_date` (world-true date) from `retrieved_at` (when we learned
it) — the bitemporal split this feature needs is already in the schema, not something
retrofitted. `raw_provider_payload` is immutable/append-only, so the original evidence
for any past state is always retrievable. `calculation` + `calculation_input` (§4.2,
§4.3) give a queryable dependency graph, so a past calculated value (e.g. an old VWAP)
can be reconstructed from exactly the inputs available at that time.

**The actual gap**: today, mutable canonical entity tables (`security`,
`capital_structure_position`, etc.) are updated in place as new provenance supersedes
old — there's no `valid_from`/`valid_to` on those rows yet, so "what did this
security's fields look like on date X" beyond fact-level provenance isn't answerable
without that addition. Phase 2 would add `valid_from`/`valid_to` to mutable canonical
tables and an `as_of_date` parameter to every repository read method, defaulting to
"now" so Version 1 behavior is unchanged when the parameter isn't passed.

**Not implemented in Version 1.** No `valid_from`/`valid_to` columns, no `as_of_date`
repository parameter, no Historical Research Mode UI.

### 23.3 Portfolio module (future phase)

The current platform is deliberately **research-focused** — Credit Universe,
Dashboard, Capital Structure, Research Notes, Alerts — not a book-of-record for
holdings. A future **Portfolio** module is documented here so today's schema doesn't
have to be reworked to support it later:

- **Submodules**: Positions, Exposure, Risk, PnL, Sector Exposure, Issuer Exposure,
  Capital Structure Exposure, Watchlist Comparison.
- **Why the current model is ready for it**: `issuer`, `security`, and
  `capital_structure_position` are already the reference data any position/exposure
  table would key off of. A future `position` table (holdings, quantity, cost basis,
  account) would FK into `security`/`issuer` without requiring changes to the
  existing reference-data schema. `watchlist_membership` already gives a "which
  issuers am I tracking" join that a Watchlist Comparison view could reuse directly.
- **Not implemented now**: no `position`, `exposure`, or `risk` tables, no PnL
  calculation, no Portfolio pages or routes.

### 23.4 Data Quality scoring

**Target capability**: every issuer and security exposes a confidence/completeness
score — informational only, and it **never replaces provenance**: a user can always
click through the score to the underlying source records it's built from, the same way
every other fact in the app works.

**Possible contributors**: SEC, OpenFIGI, TRACE, FRED, CourtListener, Ratings, Capital
Structure, Financial Statements, Document Completeness, Freshness.

**Display example**:
```
95%  Supported By
     ✓ SEC        ✓ TRACE        ✓ OpenFIGI        ✓ CourtListener
     Missing: Ratings
```

**How it fits the existing architecture**: this is a computed value in the same sense
`freshness` is (§16) — derived at read time (or via a scheduled recalculation job,
§23.5) from which `provenance` rows exist and are fresh for a given issuer/security,
not a new data source and not a hand-maintained field. It's a read over existing
provenance, never a substitute for it.

**Not implemented now**: no score calculation, no storage, no UI badge.

### 23.5 Background Job architecture

Phase 2 introduces scheduled background processing for jobs that today would only run
via manual script invocation (`scripts/fetch_seed_data.py` etc.).

**Possible future runners** (undecided — options only, not a commitment): Railway
Cron, GitHub Actions, Celery, RQ, Temporal.

**Documented scheduled jobs**: SEC synchronization, FRED refresh, TRACE refresh,
CourtListener refresh, Data Quality recalculation (§23.4), stale-data detection, alert
evaluation, embedding generation, document extraction, synthetic demo data refresh.

**Hard constraint, carried forward from §3**: background jobs are not a bypass. Every
job writes through the same Provider DTO → Normalizer → Canonical Domain Object →
Repository pipeline as an interactive request — no job may write directly to a
SQLAlchemy model or create a fact without a `provenance` row. A scheduler is an
alternate trigger for existing pipelines, not a different pipeline.

**Not implemented now**: no scheduler is wired up, no job runner is chosen, no cron
configuration exists in Version 1. `scripts/*.py` remain manually invoked.

### 23.6 Issuer Health / composite research score

**Target capability**: every issuer eventually exposes one composite health/risk
score combining several independent signal families — `research_evidence`
severity/volume (§24.3), capital structure stress (leverage, coverage, upcoming
maturities), liquidity indicators, court docket activity (once Milestone 7 exists),
ratings (once a ratings source exists), and macro factors (FRED series) — with an
AI-generated synthesis layer on top, the same way §23.4's Data Quality score is a
read over which sources exist, not a new source of truth itself.

**How it fits the existing architecture**: exactly like §23.4, this is a computed
value derived at read time (or via a future scheduled recalculation job, §23.5)
from already-provenanced records — never a hand-maintained field, never a
substitute for clicking through to the underlying evidence. Milestone 6.5's
`research_evidence`/`alert_event` model (§24) is deliberately provider-agnostic
specifically so a future score calculation can read across every evidence source
without a schema change.

**Not implemented now**: no `issuer_health_score` column, table, or calculation.
Documented here only so Milestone 6.5's evidence model is built with this future
consumer in mind, per ADR-018.

---

# 24. Milestone 6.5 — Research Universes + Overnight Distress Filing Monitor

**Status: complete (2026-08-06).** Inserted before Milestone 7 (CourtListener) by
explicit approved direction — not a silent architecture change. See ADR-016,
ADR-017, ADR-018 in `ARCHITECTURE_DECISIONS.md` for the material design
decisions, and `BUILD_LOG.md` for the chronological build entry with real counts.

## 24.1 Research Universes vs. Watchlists

Two coexisting, distinct concepts:
- **Research Universes** — organization-wide, curated, shared, evidence-backed
  coverage groups. `collection_type = research_universe` (or `benchmark` for the
  one investment-grade comparison group). Built and seeded with real issuers this
  milestone.
- **Watchlists** (§4.7, §14, Milestone 8) — personal/team-managed collections.
  `collection_type = watchlist`. **Not implemented or expanded this milestone** —
  the schema accommodates them (same `collection`/`collection_membership` tables),
  but no watchlist rows are created and no watchlist CRUD UI exists yet; that
  remains Milestone 8's scope.

Both live in one generalized `collection`/`collection_membership` table pair
(ADR-016) rather than a dedicated `watchlist` table, distinguished by
`collection_type`. `collection_membership` is a curated coverage decision, never a
current-status assertion — it never states an issuer *is* currently distressed,
in Chapter 11, high yield, rated, or facing refinancing risk on its own; that
comes only from dated `research_evidence`/`alert_event` records.

**`collection`**: id, slug, name, description, `collection_type`
(`research_universe`\|`watchlist`\|`benchmark`), `scope` (`organization`\|
`personal`\|`team`), `owner_user_id` (nullable — no `user` table exists yet),
`visibility`, `curation_method` (`manual_curated`\|`system_seeded`\|
`user_created`), `verification_status`, `last_verified_at`, `priority` (nullable
`critical`\|`high`\|`medium`\|`low`, reserved for future Morning Research Brief
prioritization — not used for sorting logic this milestone), `verification_count`
(reserved future-facing metadata), `last_refresh_source` (reserved future-facing
metadata), `created_at`, `updated_at`.

**`collection_membership`**: id, collection_id, issuer_id, `rationale` (text),
`rationale_as_of_date`, `verification_status`, `supporting_provenance_ids` (jsonb),
`added_at`, `added_by` (nullable), `system_seeded`. Unique `(collection_id,
issuer_id)`.

## 24.2 Real SEC issuer requirement

Every issuer in a Research Universe is live-verified against real SEC EDGAR data
before ingestion: CIK resolved via SEC's public `company_tickers.json` (never
hand-typed), confirmed via a live `fetch_submissions` call, ingested through the
same Provider DTO → Normalizer → Canonical Domain Object → Repository path every
other adapter uses (`ingest_issuer_identity_only`, extending
`providers/sec_edgar/provider.py`). Unresolved/ambiguous candidates are excluded
or replaced, never fabricated or fuzzy-merged (no automatic entity merging, same
rule as §8's Universal Search). Real issuer/universe counts recorded on completion.

## 24.3 Evidence and alert model (provider-agnostic — ADR-018)

`research_evidence` (**not** `distress_evidence` — see ADR-018) represents any
research signal, not only SEC-filing-derived distress signals. SEC EDGAR is the
first `evidence_provider`, not the only one intended. Columns: id, issuer_id,
`evidence_provider`, `source_type`, `filing_id` (nullable FK → the new `sec_filing`
table — this milestone's one concrete source pointer; future providers add their
own nullable source-specific FK the same way, per the TD-007/ADR-015 precedent),
`evidence_type` (CHECK enum — bankruptcy_or_receivership, chapter_11, chapter_7,
default_or_missed_payment, covenant_breach, debt_acceleration, going_concern,
substantial_doubt, liquidity_warning, restructuring_advisor,
restructuring_support_agreement, exchange_offer, liability_management_transaction,
debt_amendment, maturity_extension, refinancing, dip_financing,
emergency_financing, material_asset_sale, delisting_notice, workforce_reduction,
facility_closure, material_impairment, auditor_resignation,
adverse_audit_development, strategic_alternatives), severity, source_section,
source_item, matched_rule, evidence_excerpt (+offsets), confidence,
detection_method (`deterministic`\|`ai_assisted`), provenance_id, review_status.

Evidence from the same source event is grouped into an internal **Evidence
Bundle** (`app/domain/evidence_bundle.py`, not a persisted table) before becoming
one `alert_event` — so evidence from multiple providers about the same issuer can
eventually feed one alert without redesigning the alert engine.

`alert_event` (first real implementation of §4.11's approved shape): id,
issuer_id, category, severity, headline, explanation, `evidence_ids` (jsonb array
— the real source of truth for what caused the alert), `bundle_key`,
`primary_evidence_provider`, `primary_source_label`, `primary_source_url`,
detection_method, ai_assisted, confidence, as_of_date, provenance_id,
triggered_at, `status` (text+CHECK, only `new`\|`acknowledged`\|`dismissed`
implemented/populated this milestone — deliberately extensible via an ordinary
future migration to `new → acknowledged → investigating → resolved →
false_positive`), acknowledged_at/by, dismissed_at/by/reason, `is_backfill`. No
`filing_id` column — the UI resolves source filings by joining through
`evidence_ids`. `alert_rule` (§4.11) is **not** created this milestone — no real
caller yet (Milestone 10).

Alert provenance uses the existing `calculation`/`calculation_input` lineage
machinery (the same pattern Milestone 6 established for `illustrative_recovery`):
`alert_event.provenance_id` → a `provenance` row with `transformation =
calculated`, `calculation_id` → `calculation(method="research_alert_synthesis")`,
with one `calculation_input` row per contributing evidence item's provenance.

## 24.4 Detection pipeline

**Layer 1 (deterministic)** — `app/core/distress_rules.py`: explainable phrase/
item-code rules (8-K Item 1.03, "chapter 11"/"chapter 7", "substantial doubt
about its ability to continue as a going concern", "restructuring support
agreement", "exchange offer", "amend and extend", "debtor-in-possession"/DIP
financing, "strategic alternatives", delisting, workforce reduction, facility
closure, material impairment, auditor resignation, liquidity shortfall, debt
acceleration, and one rule per remaining `evidence_type`), deliberately
conservative around ambiguous phrases (e.g. a bare "chapter 11" mention without
Item 1.03 or stronger context gets low confidence, not excluded).

**Layer 2 (governed AI)** — only Layer 1 candidates are ever submitted to the
LLM. `app/ai/evidence_review.py` builds a constrained prompt restricted to the
supplied excerpts, and **fails closed** to deterministic templated wording on any
parse failure or unsupported claim. The AI classifies/summarizes/suggests
severity and must cite the underlying evidence; it never asserts distress from a
bare keyword and never bypasses `policy_check`/provenance rules. The original
filing remains authoritative.

Alert wording is deliberately cautious — "Potential liquidity warning detected in
a new 10-Q," "8-K Item 1.03 bankruptcy filing detected," never "this company is
distressed" or "will liquidate."

## 24.5 Watermark / baseline / delta / backfill

`filing_monitor_run`: id, started_at, completed_at, status (`running`\|
`success`\|`completed_with_errors`\|`failed`\|`baseline_established`), mode
(`baseline`\|`delta`\|`backfill`), previous_watermark, resulting_watermark,
issuers_checked, filings_discovered, filings_processed, alerts_created,
errors_count, error_summary, backfill_lookback_days, is_backfill.

- **Baseline** (first run): establishes `resulting_watermark = now`, ingests no
  filings, creates no alerts — avoids flooding the UI with an issuer's entire
  history.
- **Delta**: processes only filings with `filing_date` after the previous
  successful watermark. Idempotent by construction — `sec_filing.accession_no` is
  unique, so a re-processed filing is a no-op, not a duplicate.
- **Backfill**: explicit `--backfill-days N`, real filings within that lookback
  window, results labeled **"Historical Backfill Demo"** in the UI, never
  presented as newly filed overnight.
- **Watermark only advances when a run completes with zero errors.** A partial or
  failed run leaves the watermark untouched — already-ingested filings/evidence/
  alerts are retained (never lost), and the next run safely re-checks the same
  window (idempotent, not duplicative).

`sec_filing` (new canonical entity — `financial_fact` is XBRL-datapoint-level,
nothing previously represented "this filing exists"): id, issuer_id,
accession_no (unique), form_type (free text, monitored set filtered in the
service layer via `MONITORED_FORM_TYPES` — 8-K, 10-Q, 10-K, 6-K, 20-F, and their
amendments), filing_date, period_of_report, is_amendment, primary_document(_url),
provenance_id.

## 24.6 Scheduling

`python -m app.scripts.run_overnight_filing_monitor --mode {baseline|delta|backfill}
[--backfill-days N]` — a standalone script, not the FastAPI `get_db` dependency,
writing through the same Provider DTO → Normalizer → Canonical Domain Object →
Repository → Evidence Evaluation → Alert Synthesis pipeline as every interactive
request (§3's "no job bypasses the pipeline" rule, §23.5).

**Target production schedule (documented, not activated)**: Railway Cron,
`0 9 * * *` (09:00 UTC, ≈ 5:00 AM Eastern), command
`python -m app.scripts.run_overnight_filing_monitor --mode delta`. Not wired into
`railway.toml` or deployed this milestone — no production Railway environment is
configured yet (Milestone 15 territory) — documented here and in `README.md` so
activation is a one-line config change once deployment is real.

## 24.7 AI provider configuration (ADR-017)

`LLMProvider` Protocol (§10) and `AnthropicProvider` pulled forward from
Milestone 13, scoped narrowly to backend evidence classification — no chat, no
RAG, no user-facing assistant, no embeddings. Provider-specific env vars replace
the originally-planned generic `LLM_API_KEY` (§19): `ANTHROPIC_API_KEY`/
`ANTHROPIC_MODEL`, `OPENAI_API_KEY`/`OPENAI_MODEL` (unimplemented provider),
`AZURE_OPENAI_API_KEY`/`AZURE_OPENAI_ENDPOINT`/`AZURE_OPENAI_MODEL` (unimplemented
provider), plus a separate `EMBEDDING_PROVIDER` (reserved, unused — chat and
embeddings may end up on different vendors later). `app/ai/factory.py` reads
`LLM_PROVIDER`, validates only that provider's required credentials, raises a
clear configuration error otherwise, and never silently falls back to a different
provider. When no key is configured, the monitor runs in deterministic-only mode
rather than failing — AI assistance is additive, never required for the app to
function.

## 24.8 API surface

`GET /api/research-universes`, `GET /api/research-universes/{id}`,
`GET /api/research-universes/{id}/issuers`, `GET /api/filing-monitor/runs`,
`GET /api/filing-monitor/runs/latest-successful`,
`GET /api/filing-monitor/filings`, `POST /api/filing-monitor/runs/trigger`
(non-production-gated — interim stand-in for admin/demo-only until real auth
exists, TD-002), `GET /api/research-evidence`, `GET /api/alerts`,
`POST /api/alerts/{id}/acknowledge`, `POST /api/alerts/{id}/dismiss`,
`GET /api/morning-brief`. Plus a `universe` filter on the existing
`GET /api/credit-universe` and `universe_memberships` on `GET /api/issuers/{id}`.

## 24.9 Frontend

`ResearchUniversesPage.tsx` (`/research-universes`), `MorningResearchBriefPage.tsx`
(`/research-brief`, heading "New Research Alerts — Since Last Successful Run" —
deliberately not "New Distress *Filings*," so future non-SEC alerts fit without a
copy change). Both are new, enabled nav entries; the existing disabled "Soon"
placeholders (Watchlists, Search, Research, Alerts, Assistant) are untouched.
`CreditUniversePage` gains a `universe` URL filter; `IssuerPage` gains a Research
Universe Memberships section, clearly separated from factual-status sections.

## 24.10 Completion record

**Issuers / universes**: 30 real candidate tickers evaluated against SEC's
live `company_tickers.json`; 23 accepted (live-verified via `fetch_submissions`,
each with at least one filing on record) and 7 rejected — RAD (Rite Aid),
MNK (Mallinckrodt), YELL (Yellow Corp), BIG (Big Lots), FYBR (Frontier
Communications), SAVE (Spirit Airlines), COMM (CommScope) — none resolvable
in the live ticker file (delisted/reorganized/acquired since the candidate
list was drafted), documented and excluded rather than guessed at. 23 unique
issuers span 15 Research Universes (14 distress-oriented, one Investment
Grade Benchmark of 5 large-cap issuers kept structurally and visually
separate — never mixed into distress-screening views).

**Monitor runs**: a baseline run established a clean watermark
(`issuers_checked=23`, zero filings ingested, per the baseline-mode
contract), followed by a real, explicitly-labeled 60-day Historical Backfill
Demo (`--mode backfill --backfill-days 60`) against live SEC EDGAR data:
`filings_discovered=85`, `filings_processed=85`, `alerts_created=28`,
`errors_count=0`, watermark advanced (advances only on zero-error runs,
per §24.5).

**Evidence / alerts**: 85 real `sec_filing` rows, 83 `research_evidence`
rows, 28 `alert_event` rows — 4 high / 5 medium / 19 low severity; 0
deterministic-only / 28 AI-reviewed (every bundle went through live
Anthropic evidence review, since a real `ANTHROPIC_API_KEY` was configured).
Spot-verified evidence quality against the live filings: EchoStar Corp's
real 8-K (accession `0001415404-26-000038`, filed 2026-08-03) disclosing
subsidiary Chapter 11 petitions and automatic note acceleration was
correctly matched by three independent deterministic rules (8-K Item 1.03,
Item 2.04, "chapter 11 petition" phrase) and reviewed by Anthropic with a
97% confidence, cautiously-worded headline citing the specific default/
acceleration mechanism — not a bare "bankruptcy" assertion. The two-layer
design's false-positive guard was demonstrably proven, not just tested:
routine "chapter 11" mentions in Ford's, Johnson & Johnson's, JPMorgan
Chase's, and Microsoft's real 10-Ks/10-Ks (tax-code references, a
subsidiary's historical, already-dismissed case, boilerplate risk-factor
language) were all correctly downgraded to low severity with explicit
"no distress language found"/"not current distress" wording by the AI
review layer, rather than surfacing as false alarms.

**Tests**: 274 backend tests pass (204→274, +70 — unit + integration,
including two new genuinely-live-marked suites gated on a configured
`ANTHROPIC_API_KEY`/SEC connectivity), 61 frontend tests pass (38→61, +23)
across 11 files. Backend ruff/black/mypy clean; frontend eslint/prettier/tsc
clean; both production builds succeed.

**Live verification**: migration `0007` applied and round-tripped
(`upgrade head` → `downgrade 0006` → `upgrade head`) against the live,
shared `nexus` schema at creation time, before real data existed — not
re-run after seeding, since a downgrade would have dropped the real,
permanently-committed Research Universe/evidence/alert data this milestone
exists to demonstrate. Backend and frontend both boot and were exercised
together in a live browser walkthrough: Research Universes page (benchmark
section visually and structurally separated), Morning Research Brief (real
summary counts, severity/universe/detection/status filters all
URL-persisted, evidence expansion showing real matched-rule excerpts),
drill-down from an alert into Issuer Detail (Research Universe Memberships
section correctly listing e.g. EchoStar's High Yield + Telecom & Media
memberships), and Credit Universe filtered by a Research Universe (real
Apple securities returned when filtered to Investment Grade Benchmarks;
correctly empty for universes whose issuers were ingested identity-only
with no `security` rows yet — an honest empty state, not a bug).

**Two genuine defects found and fixed during this milestone** (not
introduced by nor masked in this record): (1) `seed_research_universes.py`'s
CIK resolver used substring matching, which matched "Yellow" (a failed
ticker lookup for delisted Yellow Corp) against the unrelated "Yellowstone
Group Ltd." — fixed with word-boundary regex matching, the bad
`collection_membership` row removed live, and a regression test suite added
(`test_seed_research_universes.py`). (2) `test_filing_monitor_service.py`'s
integration tests used fake `fetch_filings_fn` test doubles that ignored the
`cik` parameter — harmless while no real Research Universe issuers existed,
but once the seed script permanently committed 23 real issuers, `run_monitor`
correctly began iterating all of them (by design — it targets every issuer
in scope, not just one test's issuer), causing the fakes to produce/fail
data for all 24 issuers instead of one. Fixed by making every fake
CIK-aware.
