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
| **Overall Progress** | ~61% — Milestones 1–8, 6.5, 7.5, 7.5.1, 7.5.2, 7.5.3, 9 (Alerts), 10A (Research Notes + Audit Trail), 12 (Universal Search), 15 complete; Milestone 9/row 9 (Research Notes/Documents) split — 10B (Documents/Storage) not started, awaiting separate approval; row 11 (TRACE) not started |
| **Current Milestone** | Milestone 12 (Universal Search) — complete (both 12A backend and 12B frontend). 10B (Research Documents + Supabase Storage) and row 11 (TRACE) remain not started |
| **Current Status** | Universal Search implements PLAN.md §4.13/§8, built in two staged sub-phases (12A backend, 12B frontend) per explicit user direction, with a full architecture-and-product-design review completed and approved before any code was written. Per-table generated `tsvector` columns (`GENERATED ALWAYS AS ... STORED`) + GIN indexes added to `issuer`/`security`/`alert_event`/`court_docket`/`court_docket_entry`/`collection`/`research_note` (migration `0016`), resolving TD-003 in favor of no new synced table. `pg_trgm` GIN indexes added narrowly on `issuer.legal_name`/`security.description` for typo tolerance. Deterministic ranking preserved exactly as specified: Tier 0 exact identifiers (CIK/ticker/LEI/CUSIP/ISIN/FIGI/docket number/accession number) never blended with fuzzy results; Tier 1 issuer/security prefix match; Tier 2 `websearch_to_tsquery`/`ts_rank_cd` full-text search; Tier 3 `pg_trgm` similarity fallback. `sec_filing` is a deliberately thin metadata-only search (`form_type` substring, `accession_no` exact via Tier 0 only — never implies filing-content search, since none is stored). `research_evidence`, `research_note_version`, `audit_event`, and `docket_document` are all deliberately excluded, and 10B is untouched. `GlobalSearch` (AppBar typeahead, 300ms debounce, grouped results, full keyboard navigation, "See all results") and `/search` (larger per-group results, reusing Credit Universe's own filter for issuer/security "see all" rather than building a second pagination system) ship in 12B. A real bug was live-caught and fixed before the first commit: `concat_ws` (STABLE, not IMMUTABLE) broke `research_note`'s generated column; fixed with plain `||` concatenation, migration corrected and re-verified with zero drift. Zero Anthropic calls anywhere in this milestone. 537/537 backend tests pass (24 new), 181/181 frontend tests pass (17 new). Full live-browser walkthrough completed, including cross-entity queries ("going concern," "confirmation hearing") and exact-identifier lookup (CIK). Full detail in §24.13 and `BUILD_LOG.md`. |
| **Last Updated** | 2026-08-12 |
| **Current Git Branch** | main |
| **Latest Commit** | `b0c14eb` — Milestone 12: Universal Search (12A backend + 12B frontend) |
| **Next Milestone** | 10B (Research Documents + Supabase Storage) and row 11 (TRACE adapter) both remain not-yet-authorized — neither begins until explicitly approved |

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
| 7.5 | SEC Market Discovery & Automatic Issuer Enrichment (inserted, approved — see below) | Complete | 2026-08-07 | `cd73c5b` | Reusable SEC full-text-search discovery pipeline (`efts.sec.gov`) + CIK-first shared issuer resolver + provider-agnostic enrichment orchestrator (`issuer_enrichment_status`) covering SEC/CourtListener/OpenFIGI for both newly-discovered and already-known issuers. ADR-020 supersedes ADR-019 to allow strict, signal-hierarchy-based automatic CourtListener docket linking — jurisdiction/HQ correspondence explicitly excluded as a required signal (0 auto-links produced, by design — conservative policy held at scale). Hard human-approval gate honored: July 2026 pilot (89 candidates, 1 error) reviewed and approved before the January–August 2026 backfill (603 candidates, 11 errors) ran with the identical pipeline. Final state: 541 issuers, 6,036 SEC filings, 5,417 evidence records, 1,856 alerts, all real-provider-sourced. See `BUILD_LOG.md` Parts 1–2 for full metrics and quality review. |
| 7.5.1 | Signal Quality & Research Universe Calibration (inserted, approved — see below) | Complete | 2026-08-08 | `f11ef00` | Audit-driven precision fix for Milestone 7.5's evidence-driven Research Universe classification. Root cause: raw Layer-1 severity has no entity attribution, so a bare "chapter 11"/"event of default" phrase match scored identically for the issuer's own event vs. a director's former employer's, a customer's, or SEC boilerplate. Fixed by gating on the AI-reviewed alert's severity + a new `issuer_is_subject` field (migration `0011`); a second, live-proven SEC full-text-search `forms`-parameter bug (amendment-suffix forms silently corrupting the filter, ~96% coverage loss) also fixed. `app.scripts.reclassify_system_universes` reconciled all 8 evidence-driven universes idempotently — Chapter 11 54→20, Distressed Core 398→299, Default/Covenant Stress 281→173, Liability Management 68→33, Refinancing Risk 130→115; Going Concern 210→244 and Post-Emergence 0→14 (a previously-dead category) increased, correctly capturing real signal the old raw-severity gate structurally could not reach. Zero canonical data deleted. |
| 7.5.2 | Daily Delta Run & Morning Research Brief Semantics (inserted, approved — see below) | Complete | 2026-08-09 | `ca41b13` (initial), `427b535` (2nd pass), `eafb77e` (3rd pass — see below) | Root-caused the stale "Last successful run: Aug 6" display: `get_latest_successful_run` on both run tables treated *any* successful mode — including `backfill` — as the watermark/display source. Fixed with new `get_latest_successful_daily_run`/`get_latest_daily_run` (mode `delta`/`baseline` only) driving `get_morning_brief`, plus a second real bug found live during the Aug 7 run: `since` was originally set to the latest run's `completed_at`, which excludes that very run's own output (everything a run creates is written before it finishes) — corrected to `started_at`. A real 2026-08-07→08 delta via the unmodified `market_discovery_service` (TD-014 active) discovered 246 new issuers, 39 already-known, 1207 new SEC filings, 822 new evidence rows, 356 new alerts (49 high / 65 medium / 242 low; 351 AI-assisted / 5 deterministic), 0 errors, elapsed 3509s (~58.5 min). Re-run over the identical window (as `backfill` mode, since `delta` mode self-advances its window from the watermark) produced zero new rows across every table — full idempotency proven, 38.7s. `new_court_events=0` root-caused as genuinely correct, not a bug: CourtListener enrichment only attempts a search once an issuer has docket-relevant evidence on file, and only 3 of 285 processed candidates did, all returning no matching docket. Two new Technical Debt items recorded (TD-016, TD-017) rather than expanding this milestone's scope. **Same-day correction**: the brief's definition was further corrected from "what did the last pipeline run do" to "what materially changed since this user last reviewed the brief" — see the Next Immediate Goal narrative below for the full change (new user-relative `period_start` via `morning_brief_view`, mode/pipeline counters demoted to a secondary `RunDetails` block, issuer-grouped/severity-ranked `new_developments`/`historical_intelligence` split by `is_backfill`, Research Universe membership-change surfacing, TD-018 recorded for the no-per-user-auth interim posture). A genuine performance regression was found and fixed during this correction (see Problems Encountered in `BUILD_LOG.md`): the naive per-alert-query implementation timed out entirely (>50s, no response) against real production volume; batched issuer/universe lookups brought a real request down to ~1.7s. **Third pass (same day, explicit follow-up direction)**: even the user-relative `period_start` was still the wrong business definition — a page view is not a research boundary. Corrected to "what materially changed during the latest completed business-day research cycle, compared with the preceding one," derived purely from canonical successful daily-run data (`research_day`, a new field on `DailyRunSummary`) plus calendar business-day arithmetic — never from when the page was opened, refreshed, or revisited. `morning_brief_view` and `POST /api/morning-brief/view` were removed entirely (migration `0013`) since nothing else read the view log; TD-018/TD-019 closed by this removal, not by building the deferred per-user version. See the Next Immediate Goal narrative below for the full design. |
| 7.5.3 | Historical Discovery Coverage Repair (inserted) | Zero-AI historical ingestion Complete; AI review of deferred bundles intentionally still deferred/not authorized | `bc7afd0` (AI cost control), — (zero-AI re-run itself, see `BUILD_LOG.md`) | — | Re-runs the 2026-01-01→2026-08-06 historical discovery window with TD-014's corrected SEC full-text-search `forms` behavior active. Two early live attempts (Aug 9) hit a CourtListener `Retry-After` defect that stalled the batch for 4+ hours on an uncapped `time.sleep()` — root-caused via `py-spy`, fixed (RFC 7231-correct parsing + a hard wait ceiling, TD-020). The user then paused the milestone to require AI cost control, observability, and Haiku/Sonnet model routing before any further backfill; that control layer (`app.ai.model_router`, `ai_call_log` table/migration `0014`, hard per-run budgets, zero-AI mode, pre-run cost estimation) was built and tested (35 new tests, 418/418 backend tests passing), with live quality validation fixing a Haiku markdown-fence parsing bug and confirming definitive/high-impact categories (Chapter 11, bankruptcy, plan-confirmed) always route straight to Sonnet. With that control layer in place, the user separately authorized a **zero-AI** (`--ai-mode zero`, $0 Anthropic spend) re-run of the historical window purely to measure real coverage before any paid AI review. Across 5 live attempts (2026-08-09→10), 4 crashed on genuine infrastructure issues (two more SEC-side transient `500`s hitting the same undefended top-level query-loop gap as the original Retry-After incident's sibling bug, plus two previously-undocumented stall types — a DB idle-in-transaction hang and an SEC-document-fetch hang, both killed and safely resumed via existing `(cik, accession_no)`/`rule_version` idempotency — see TD-022); the 5th attempt completed with 0 errors. Final state: 2,652 issuers (from 787), 28,170 SEC filings (from 7,243), 22,252 research evidence rows (from 6,239), 3,123 alerts (from 2,212), confirmed $0 Anthropic spend throughout (`ai_call_log` unchanged at 8 rows across all 5 attempts). AI review of the resulting deferred bundles remains separate, still-deferred work — not run by this pass, not auto-triggered by anything. Full detail in `BUILD_LOG.md`. |
| 7.5.3-daily | Resumption of normal daily production research cycle (inserted) | Complete | — | — | See the 2026-08-10 daily-cycle `BUILD_LOG.md` entry. A side effect of the historical re-run above was discovered and corrected: `market_discovery_repository.get_latest_successful_run` (used by `delta` mode to compute its own resume watermark) does not exclude `mode=backfill` runs by design (unlike `get_latest_successful_daily_run`, which does, for Morning Brief display purposes only) — so the backfill's own completion timestamp became the resume point for the next `delta` run, which would have silently skipped Sunday 2026-08-09's SEC activity entirely (Saturday 2026-08-08 was already covered by the prior real delta). Corrected with one explicit `--mode backfill --start 2026-08-09 --end 2026-08-10` catch-up run (same pipeline, same idempotency, not counted as a Morning Brief research day since backfill mode is excluded from the daily-run boundary) followed by a normal self-computing `--mode delta` run, which idempotently found the catch-up's work already done and correctly recorded itself as the `2026-08-10` daily research day. See TD-023 for the underlying watermark-computation note (not fixed — a one-time manual correction was sufficient and lower-risk than changing shared watermark logic mid-task). A second, more consequential bug was found and fixed the same day: Morning Research Brief's `new_developments`/`historical_intelligence` split (and `RunDetails`' `new_sec_filings`/`new_court_events`/`new_research_evidence` counters) relied solely on `alert_event.is_backfill` (an ingestion-mode flag) rather than each record's real-world event/source date — so the catch-up run's 225 genuinely-current alerts were mechanically mislabeled historical. Fixed by classifying purely on `as_of_date`/`filing_date`/`entry_date` relative to the `(preceding_research_day, latest_research_day]` research-cycle boundary; `is_backfill` itself is untouched, still exposed as ingestion provenance. Verified against real production data: `issuers_with_developments` 0→191, `no_material_changes` true→false. 9 new regression tests. Full detail in `BUILD_LOG.md`. |
| 8 | Watchlists (personal tracking lists, `collection_type=watchlist`) | Complete | 2026-08-11 | `9899007` | Reused the existing `collection`/`collection_membership` schema per ADR-016 — zero migration needed. New `watchlist_service.py` (create/rename/delete Watchlist, add/remove issuer) + `GET/POST /api/watchlists`, `GET/PATCH/DELETE /api/watchlists/{id}`, `POST/DELETE .../issuers[/{issuer_id}]`. "New developments" reuses `morning_brief_service.resolve_research_cycle`/`is_new_development` verbatim — no second definition of "new." Batched repository functions (`list_alerts_by_issuers`, `count_securities_by_issuers`, `list_collections_with_membership_for_issuers`) avoid N+1 across a Watchlist's issuers. Frontend: Watchlists landing page, Watchlist detail (desktop table / mobile cards via the existing `DataTable` pattern), and one reusable `AddToWatchlistButton` wired into Issuer Detail. A real "CFO Demo Watchlist" was created via the application's own service (not a fixture) with 6 real, currently-tracked issuers spanning active Chapter 11 (Trinseo, EchoStar), post-emergence (Diebold Nixdorf), covenant/default pressure (Community Health Systems), refinancing risk (Lumen Technologies), and liability management (iHeartMedia). §14's original "ten coverage + one benchmark Watchlists" vision predates ADR-016's Research-Universes/Watchlists split and is superseded by it — see §14 and §24.1. No per-user auth exists yet (TD-002); every Watchlist is `scope=personal`/`owner_user_id=NULL` in a single shared analyst workspace, by explicit design, documented as a known limitation. 481 backend tests pass (21 new, covering Watchlist CRUD, duplicate/idempotent membership, deletion isolation, latest-development/research-cycle/severity aggregation, and the Watchlist-vs-Research-Universe "current status" boundary), 130 frontend tests pass (17 new, covering the landing page, detail page incl. mobile cards, and the reusable Add to Watchlist component). Zero Anthropic calls — Watchlists never construct AI prompts. |
| 9 | Research notes/documents + audit events | 10A (Research Notes + Audit Trail) Complete; 10B (Documents/Storage) Not Started, awaiting separate approval | 2026-08-12 | `fbf5da4` | Split into two approved sub-phases by explicit user direction — see §24.12 for the full 10A design record. `research_note`/`research_note_version` (full-snapshot-per-edit versioning) + `audit_event` (first audited-write path in the app) live-migrated (`0015`) and verified against the shared `nexus` schema. No `user`/`role`/`user_role` tables built — genuinely no 10A functional need, `AUTH_ENABLED=false` unchanged, identity fields nullable text mirroring `collection.owner_user_id`'s Milestone 8 precedent. A real Demo Research Note (Trinseo PLC, 3 real dated versions: covenant stress → going concern → Chapter 11, all citing real `alert_event` evidence) seeded idempotently via the app's own service. 511/511 backend tests pass (16 new), 164/164 frontend tests pass (17 new). Zero Anthropic calls. 10B (Documents, Supabase Storage, `research_document`) explicitly deferred, not started. |
| 10 | Alerts (Alerts Center — analyst inbox over existing `alert_event`, not a new rule engine) | Complete | 2026-08-11 | `7c43e3d` | Completed ahead of Milestone 9 (Research notes/documents) by explicit user direction — the incoming brief was explicitly numbered "Milestone 9" by the user even though this row is PLAN.md's original §18 build-order slot for Alerts; row numbers are left as originally assigned rather than renumbered, to avoid invalidating other cross-references in this document. See §24.11 for the full design: reused `alert_event`/`alerts.py`/`alert_repository.py` (already canonical since Milestone 6.5's ADR-018 pipeline, not the `alert_rule`/`alert_engine.py` design originally sketched in §12), zero migration, new `watchlist_id` filter + `/api/alerts/summary` + `/api/alerts/issuers` search, a new `AlertsPage.tsx` analyst-inbox UI, and two live-caught regressions fixed (`universe_names` leaking Watchlist names; incorrect pagination `total` for multi-issuer collection filters — both existed before this milestone but were only reachable once real Watchlists existed). Zero Anthropic calls. 23 new backend tests, 25 new/extended frontend tests. |
| 11 | TRACE adapter/sample | Not Started | — | — | |
| 12 | Universal Search | Complete (12A backend + 12B frontend) | 2026-08-12 | `b0c14eb` | Built as two staged sub-phases per explicit user direction — see §24.13 for the full design record. 12A: per-table generated `tsvector` columns + GIN indexes on `issuer`/`security`/`alert_event`/`court_docket`/`court_docket_entry`/`collection`/`research_note` (migration `0016`, resolving TD-003), `pg_trgm` GIN on `issuer.legal_name`/`security.description`, deterministic exact-match/prefix/FTS/trigram ranking tiers, thin `sec_filing` metadata search. 12B: `GlobalSearch` header typeahead (debounced, grouped, keyboard-navigable) and `/search` results page. Deliberately excludes `research_evidence`, `research_note_version`, `audit_event`, `docket_document`, and all of 10B. Zero Anthropic calls. 537/537 backend tests pass (24 new), 181/181 frontend tests pass (17 new). |
| 13 | AI Research Assistant + gated embeddings | Not Started | — | — | |
| 14 | Disabled licensed-provider capability cards | Not Started | — | — | |
| 15 | Railway/Vercel deployment validation | Completed Early | 2026-08-09 | (verified during Milestone 7.5.2, no dedicated deployment commit — deploy already existed) | Discovered already satisfied while implementing Milestone 7.5.2, not newly deployed by this milestone. Live-verified: `GET https://nexus-credit-intelligence-production.up.railway.app/health` → `200 {"status":"healthy","environment":"production"}`; `GET https://nexus-credit-intelligence.vercel.app/` → `200`; a real `OPTIONS` preflight from the Vercel origin to the Railway API returns `access-control-allow-origin: https://nexus-credit-intelligence.vercel.app` (CORS correctly configured, not just "not blocked"); Alembic migrations applied live via `DIRECT_DATABASE_URL` per KI-001 (closed 2026-08-05). This is roadmap bookkeeping only — no deployment action was taken by this milestone. |
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
| TD-003 | ~~Search index storage shape (single `search_document` table vs. per-table `tsvector` columns, §4.13) not yet decided~~ **Resolved in Milestone 12A.** Per-table generated `tsvector` columns (`GENERATED ALWAYS AS ... STORED`) chosen over a synced `search_document` table — Postgres auto-maintains a generated column on every INSERT/UPDATE, so no writer (SEC ingestion, CourtListener sync, `research_note_service`, ...) needs to remember to also write to a second table, and this project has zero triggers anywhere to keep one in sync automatically. See §24.13. | — | `backend/app/repositories/search_repository.py` | **Resolved** (`backend/alembic/versions/0016_universal_search_vectors_and_indexes.py`) |
| TD-004 | `backend/app/db/session.py` uses synchronous SQLAlchemy (`create_engine`/`sessionmaker`), not an async engine, even though FastAPI/provider adapters are async-capable | Low | Revisit if a provider-heavy milestone (SEC/FRED/CourtListener concurrency) shows the sync DB layer is a real bottleneck; async SQLAlchemy is a drop-in-ish swap behind the repository layer (§3) | Open (pragmatic choice, not a gap) |
| TD-005 | `data_entitlement.derived_data_permission` exists on the model/domain object (PLAN.md §4.8) but `policy_check` doesn't yet use it — deciding whether a *calculated* value derived from licensed inputs may be treated less restrictively than the raw input requires walking `calculation_input` lineage back to the strictest governing entitlement, which has no real licensed provider to test against yet | Low | Implement once Milestone 14 (disabled licensed-provider capability cards) or a real licensed adapter makes this testable against actual data | Open (deferred by design, ADR-014) |
| TD-006 | SEC EDGAR company-facts responses (hundreds of us-gaap concepts, several MB for a large filer) are stored inline in `raw_provider_payload.payload_json` (JSONB) rather than Supabase Storage — PLAN.md §4.4 names "SEC JSON" as an example of a *small* inline-appropriate response, but company-facts specifically is not small. `SUPABASE_STORAGE_BUCKET` isn't configured yet (deferred per Milestone 2), so storing large payloads there wasn't an option this milestone; skipping raw-payload persistence entirely was rejected as a correctness violation (breaks "every raw payload must be recoverable") | Medium | Move large provider responses (company-facts JSON, filings, court documents) to Supabase Storage via `storage_object_path` once the bucket is configured (Milestone 9/document milestone, or whenever Storage is first genuinely needed) | Open (deferred by design) |
| TD-007 | `security` (PLAN.md §4.5) carries a single `provenance_id` for the whole row, not per-field provenance — a real security often blends fields sourced/verified at different times (e.g. CUSIP from OpenFIGI, coupon from the issuer's indenture) that a single provenance row can't distinguish | Low | Milestone 5's OpenFIGI adapter — the scenario this TD anticipated — deliberately did NOT resolve it: OpenFIGI-identified bonds became new `security` rows (purely OpenFIGI-sourced, so a single `provenance_id` is already correct), not enrichments of the existing SEC-sourced aggregate row (which would have misattributed a specific bond's FIGI to a balance-sheet-total row). Still revisit once a milestone actually needs to blend two providers on one existing row | Open (deferred by design, `backend/app/domain/security.py`) |
| TD-008 | SEC EDGAR's XBRL company-facts API (the only SEC EDGAR endpoint this codebase uses) exposes only issuer-level aggregate concepts (e.g. `LongTermDebtNoncurrent`), not per-instrument dimensional data — real, per-instrument bond data (CUSIP, specific maturity/coupon) is not obtainable from this endpoint at all. `normalize_bond_security` honestly represents this by leaving `cusip`/`isin`/`figi`/`maturity_date`/`coupon` as `None` rather than fabricating instrument-level detail | Medium | Milestone 5's OpenFIGI adapter now supplies real FIGI/maturity/coupon for specific bond issues (a different data source, as this TD anticipated) — partially resolved for the issuers OpenFIGI covers. SEC EDGAR itself still can't provide this; CUSIP/ISIN remain unavailable from either provider | Open (real external API limitation, not a design shortcut) |
| TD-009 | `providers/fred/provider.py`'s `sync_series` pulls only the most recent `limit` observations (default 10), not a full historical backfill to a series' `observation_start` — a deliberate first-vertical-slice scope choice, not an oversight | Low | Add a bulk/historical sync path once a feature actually needs trend history (e.g. a rate chart) rather than just the latest value | Open (deferred by design, `backend/app/providers/fred/provider.py`) |
| TD-010 | Real issuers (Apple Inc.) have no `capital_structure_position` rows — neither SEC EDGAR's company-facts API nor OpenFIGI's search endpoint reports seniority/lien position/ranking for a specific instrument (same underlying gap as TD-008), so this milestone deliberately did not force real securities into a stack layer it can't honestly support. The Issuer Detail page falls back to a flat Securities table for any issuer with no capital structure layers on file, so nothing is hidden — it just isn't organized into a priority stack yet | Medium | Populate real capital structure layers once a provider that actually reports lien/seniority/ranking data exists (a licensed provider, Milestone 14, or a future SEC dimensional-XBRL parse) | Open (real external data limitation, not a design shortcut, `backend/app/synthetic/capital_structure_generator.py`) |
| TD-011 | Issuer Detail's pre-existing "What filings support this?" and "What changed recently?" sections (`issuer_service.py`, Milestone 3) are driven solely by `financial_fact`-linked provenance — they were never extended to also surface the new `sec_filing`/`research_evidence`/`alert_event` rows Milestone 6.5 introduces. Live-verified during the Milestone 6.5 browser walkthrough: EchoStar Corp has 2 real `sec_filing` rows and 2 real `alert_event` rows (visible on the Morning Research Brief, with a working drill-down link into this same Issuer Detail page), yet its own "What filings support this?" section reads "No filings on file for this issuer yet" — correct for the financial-fact-evidentiary question that section actually answers (EchoStar was seeded identity-only, no XBRL pull), but easy to misread as "this issuer has no SEC filings at all." Not a scope violation — PLAN.md §24.9 committed only to a new, separate "Research Universe Memberships" section (present and correct) — but a real UX gap worth closing | Low | Extend `issuer_service.get_issuer_detail` to include `sec_filing`/`alert_event` activity in "What filings support this?"/"What changed recently?", or re-label the existing sections to make their financial-fact scope explicit, once Issuer Detail has a real design pass for it | Open (discovered during Milestone 6.5 browser walkthrough, not a regression) |
| TD-012 | ~~`app.providers.courtlistener.provider.sync_docket_entries` always re-walks a docket's full pagination~~ **Resolved in Milestone 7.5.** Live-verified via a real `OPTIONS` request against `docket-entries/` (confirming `id` supports `gt`/`gte` filters and `order_by=id`) that CourtListener's own `id` field is a globally monotonic identifier — `sync_docket_entries` now uses `docket_entries_incremental_url` (`id__gt=<max already-synced courtlistener_entry_id>`) for any docket that already has entries on file, falling back to the original full-pagination walk only for a docket's first-ever sync. No overlap margin needed (unlike a timestamp-based cursor) since `id__gt` can never re-fetch or skip an entry. | — | `court_docket_entry_repository.get_max_courtlistener_entry_id` + `CourtListenerClient.docket_entries_incremental_url` | **Resolved** (`backend/app/providers/courtlistener/provider.py`, `backend/app/providers/courtlistener/client.py`) |
| TD-013 | A single, very long-running (~1.5–5.8 hour) `market_discovery_service.run_discovery` process against the live shared Supabase connection pool hit a handful of transient `psycopg.OperationalError: server closed the connection unexpectedly` / SEC read-timeout / SEC 503 errors during Milestone 7.5's July pilot (1 of ~92 candidates) and January–August historical backfill (11 of ~603 candidates, ~2%) — all isolated to the one issuer being processed at the time (per-issuer commit/rollback boundaries, verified live: zero orphaned `sec_filing`/`research_evidence`/`alert_event` rows for every affected issuer), never corrupting another issuer's already-committed work, and correctly keeping the run's watermark from advancing. Explicitly *not* redesigned into automatic per-issuer retry-with-backoff this milestone, per direct instruction: a single-digit-percentage transient error rate across a many-hours run against a shared connection pool is a real but non-repeatable-in-the-logic-bug sense operational characteristic, not a design flaw to react to on one observation | Low | If a future milestone's live runs show a *repeatable* (not just occasional) failure pattern, add bounded automatic retry-with-backoff at the per-issuer level in `market_discovery_service`/`enrichment_orchestrator` (both already have the per-issuer isolation boundary such a retry would slot into) | Open (deferred by explicit direction — recovery is manual/targeted today, proven safe and idempotent via the Milestone 7.5 Baird Medical Investment Holdings recovery) |
| TD-014 | ~~SEC full-text-search `forms` parameter silently corrupted when amendment-suffix forms (e.g. `"8-K/A"`) were mixed into the same comma-separated list as base forms~~ **Resolved in Milestone 7.5.1.** Live-verified directly against `efts.sec.gov`: `forms=8-K` alone returned 577 real "chapter 11" hits over a fixed window, `forms=8-K,10-K` returned 1002, but `forms=8-K,10-K/A` (one amendment suffix mixed in) returned 0 — the real 10-form `MONITORED_FORM_TYPES` list this milestone's Layer-0 discovery sends returned just 50 instead of the ~1460 confirmed to genuinely exist, a >96% real coverage loss silently affecting every one of Milestone 7.5's 18 Layer-0 queries. Root-caused via a benchmark check against known 2026 bankruptcy filers (FAT Brands, Bitcoin Depot, Inotiv, GoHealth — all real, all missed) required by this milestone's own audit process. | — | `market_discovery_service._split_forms_for_full_text_search` | **Resolved** (`backend/app/services/market_discovery_service.py`) — not yet re-run against historical data; a future discovery run will pick up the fix, this milestone did not re-run the full backfill to avoid scope creep beyond signal-quality calibration |
| TD-015 | 19 existing alerts covering definitive-category evidence (Chapter 11/bankruptcy-or-receivership/plan-confirmed) still have `alert_event.issuer_is_subject = NULL` after 5 reconciliation passes (`app.scripts.reclassify_system_universes`) — each pass's AI re-review call failed for a persistent (not obviously transient) subset, converging from 32 failures to 19 with diminishing returns per additional pass. Safe by construction: `NULL` is treated the same as a confirmed third party for the `verified` gate (never silently promotes), so these 19 issuers' affected memberships sit at `partial` (system-suggested, correctly not overclaiming) rather than being wrongly excluded or wrongly verified | Low | Investigate why these specific 19 re-review calls fail consistently (possibly a specific excerpt/prompt-length edge case) if a future pass over this data is warranted; re-running the script again is always safe (idempotent) and may resolve more on its own | Open (safe residual, not a correctness issue — `backend/app/scripts/reclassify_system_universes.py`) |
| TD-016 | ~~No AI call/token/cost observability exists anywhere in this codebase~~ **Resolved in Milestone 7.5.3's AI cost-control correction.** `CompletionResponse` now carries `input_tokens`/`output_tokens` (captured from the real Anthropic SDK response `usage`); every real API request is logged to a new `ai_call_log` table (migration `0014`) with model, route, routing reason, tokens, estimated cost, latency, success/failure, retry count — aggregated per-run via `ai_call_log_repository.aggregate_for_discovery_run`. | — | `app/ai/model_router.py`, `app/repositories/ai_call_log_repository.py`, `alembic/versions/0014_ai_call_log.py` | **Resolved** (`backend/app/ai/model_router.py`) |
| TD-017 | `market_discovery_run.evidence_created`/`alerts_created` (and the CLI's printed run summary) undercount real activity — they only tally evidence/alerts created directly inside `market_discovery_service.run_discovery`'s own per-candidate loop, not evidence/alerts the enrichment orchestrator's `_enrich_sec` creates for the same issuer in the same run (a separate `process_issuer_filings_fn` call with its own, often much wider, lookback window — up to `SEC_FIRST_CHECK_LOOKBACK_DAYS`=90 days for a never-before-seen issuer). Live-confirmed during the real 2026-08-07 delta run: the run's own printed summary reported `evidence_created: 0, alerts_created: 0` while the database genuinely gained 822 evidence rows and 356 alerts in that same run. The Morning Brief itself is unaffected (it queries `created_at`/`triggered_at` directly, never these run-row counters), but an operator reading the run's own CLI output or the persisted `market_discovery_run` row for capacity/cost planning would be misled | Medium | Have `enrich_issuer_fn`'s return value (or `_enrich_sec`/`_enrich_courtlistener` directly) report evidence/alert counts back to `run_discovery`'s local counters, so `market_discovery_run.evidence_created`/`alerts_created` reflect true total activity, not just the discovery loop's own direct contribution | Open (discovered during Milestone 7.5.2's real-run verification, root-caused via live DB row counts, not guessed) |
| TD-018 | ~~The Morning Research Brief's "since you last looked" boundary (`morning_brief_view`) was a single shared, append-only timeline, not a per-user one.~~ **Resolved by architecture change, not by adding auth.** Milestone 7.5.2's third correction removed the page-view-based boundary entirely: the comparison window (`latest_research_day`/`preceding_research_day`) is now derived purely from canonical successful daily-run data plus calendar business-day arithmetic — a research cycle is inherently a shared, system-wide concept, not a per-user preference, so the original "needs per-user scoping once auth exists" framing no longer applies. `morning_brief_view` itself was dropped (migration `0013`) since nothing else in the codebase ever read it. The real, still-open per-user requirement (TD-002 — real user identity/sessions) is unaffected by this closure; it just no longer has this specific dependency on it | — | — | **Resolved** (closed by removing the mechanism, not by building the deferred per-user version — `backend/app/services/morning_brief_service.py`, `alembic/versions/0013_drop_morning_brief_view.py`) |
| TD-019 | ~~`POST /api/morning-brief/view` intermittently returned `503` from Railway's edge when triggered by a real, fresh browser page load.~~ **Resolved by removing the endpoint**, not by root-causing the `503` — the underlying cause was never conclusively identified despite extensive live investigation across two rounds (response-size hypothesis disproved by direct re-test; TanStack Query's mutation retry verified to not actually re-attempt the call; a direct manual retry shipped but its real-world effectiveness couldn't be confirmed from this environment either). Milestone 7.5.2's third correction made the entire page-view-recording mechanism unnecessary (the comparison window no longer depends on any view state at all), so `POST /api/morning-brief/view` was deleted along with `morning_brief_view` — the specific endpoint that exhibited the `503` no longer exists, so it cannot recur, but the *mystery itself* (why a fresh page load's request failed when every scripted/manual reproduction of the identical request succeeded) was never explained. Recorded here as a permanent, honest historical note per explicit instruction not to silently drop it from the record | — | — | **Resolved by removal** — root cause remains permanently unexplained, not silently hidden (`backend/app/api/routes/morning_brief.py`, `alembic/versions/0013_drop_morning_brief_view.py`) |
| TD-020 | `ThrottledHttpClient` had no ceiling on how long a single `Retry-After`-driven wait could block a caller — live-caught during Milestone 7.5.3: a CourtListener `429` retry stalled an entire live discovery batch for 4+ hours (`py-spy`-confirmed: the process sat inside `time.sleep()` the whole time, not a network hang), and `_retry_after_seconds` used a bare `float(header_value)` that would trust an arbitrarily large or malformed value verbatim (RFC 7231 also permits an HTTP-date form, which the old code didn't parse at all). **Resolved**: RFC 7231-correct parsing (delta-seconds and HTTP-date, via `email.utils.parsedate_to_datetime`) plus a hard, configurable `max_retry_after_seconds` ceiling — beyond it, `get()` raises `RetryAfterTooLongError` instead of sleeping, which this codebase's existing per-issuer/per-provider isolation already converts into a `FAILED_RETRYABLE` status rather than stalling unrelated work. 9 regression tests added (normal/malformed/huge/HTTP-date/repeated-429). The *exact* Retry-After value CourtListener actually sent during the live incident was never captured (the process was killed via `py-spy`+`Stop-Process`, not instrumented mid-flight) — plausible but unconfirmed explanation is a misinterpreted timestamp rather than a delta-seconds count | — | `app/providers/base/http_client.py` | **Resolved** (`backend/app/providers/base/http_client.py`, `backend/tests/unit/test_http_client_retry_after.py`) |
| TD-022 | `market_discovery_service.run_discovery`'s top-level SEC full-text-search query loop has no per-query `try`/`except` (only per-candidate/per-issuer processing inside it is isolated) — a single transient SEC-side `500` on any one query kills the entire process, leaving its `market_discovery_run` row permanently stuck at `status='running'` (never reaches error handling, so `errors_count` stays `0` and the row must be recognized as abandoned by inspection, not by its own recorded status). Observed 4 times total: twice during the January–August 2026 zero-AI historical re-run (2026-08-09/10, ~3h09m into each of two multi-hour runs) and once more during the smaller 2026-08-09→10 daily catch-up window (crashed almost immediately, 8 candidates in). A second, previously-undocumented stall pattern was also observed twice during the historical re-run: a child worker going idle-in-transaction on Postgres with dead `CloseWait` TCP sockets to a remote HTTPS endpoint for 30+ minutes with zero progress (not the already-fixed CourtListener Retry-After defect, TD-020 — no `Retry-After` sleep was in progress either time) — killed and safely resumed both times via existing `(cik, accession_no)`/`rule_version` idempotency, zero duplicate rows or corruption confirmed via direct query each time. Explicitly not redesigned into automatic per-query retry/circuit-breaking this pass, per direct instruction to leave the historical-backfill pipeline's reliability design alone; low real risk for the normal single-day `delta` window (~40 queries, as observed in the real Aug 7→8 run) vs. the much larger historical backfill (87+ queries against much larger result sets) where all 4 occurrences happened | Medium | Add a per-query `try`/`except` in `run_discovery`'s top-level query loop (log and continue to the next query, matching the per-candidate isolation pattern already used one level down) if a future pass needs the historical/large-window path to be more resilient; investigate the idle-in-transaction stall's root cause (possibly a missing read-timeout on one of the SEC document-fetch/OpenFIGI/CourtListener HTTP calls) if it recurs on the much-lower-volume daily path | Open (deferred by explicit direction, `backend/app/services/market_discovery_service.py`) |
| TD-023 | `market_discovery_repository.get_latest_successful_run` (which `delta` mode uses to compute its own resume watermark) does not exclude `mode=backfill` runs — by design, since a backfill genuinely does perform real SEC full-text-search queries as of its actual execution time and the next `delta` run should not blindly re-examine what was just examined. This is a different function from `get_latest_successful_daily_run` (which *does* exclude `backfill`, for Morning Brief display purposes only, per Milestone 7.5.2) and was left unchanged by that fix intentionally. The gap: a `backfill` run's `resulting_watermark` is stamped with its own real completion time (`datetime.now(UTC)`), not derived from its declared `window_end_date` — so if a backfill's declared window ends well in the past (e.g. `2026-08-06`) but the run doesn't actually *complete* until days later, the next `delta` run's self-computed `resolved_start` silently jumps to the backfill's completion date, skipping any calendar days between the backfill's declared window end and its real completion. Live-observed 2026-08-10: the Jan–Aug historical re-run's declared window ended `2026-08-06`, but it didn't finish until `2026-08-10`, which would have caused a bare `--mode delta` invocation to skip Sunday `2026-08-09` entirely. Worked around this time with one explicit `--mode backfill --start 2026-08-09 --end 2026-08-10` catch-up run rather than changing the shared watermark-resolution function under time pressure; not expected to recur under normal nightly operation (a `backfill`-mode run stamping `resulting_watermark` with its own completion time is *usually* correct — the gap only appears when a backfill's declared window and its real completion time diverge, which is specific to how long-running historical work happens to be) | Low | If a future long-running `backfill` (declared window far in the past, real completion much later) precedes a `delta` run again, either recompute the gap manually (as done here) or consider having `run_discovery` derive `resulting_watermark` for `backfill` mode from `window_end_date` instead of `datetime.now(UTC)` — a genuine design tradeoff (declared-window-end is more conservative/correct for `delta`'s resume point, but `datetime.now(UTC)` is more conservative for "don't re-examine what a backfill just, in real wall-clock time, actually checked") that deserves its own explicit decision, not a reflexive change | Open (discovered 2026-08-10, `backend/app/services/market_discovery_service.py`, `backend/app/repositories/market_discovery_repository.py`) |
| TD-024 | ~~Market Context's SOFR/HY OAS values had gone stale (SOFR showing `2026-08-05`, HY OAS `2026-08-04`, on `2026-08-11`).~~ **Resolved 2026-08-11.** Root cause: `app.providers.fred.provider.sync_series` — the only function that fetches new FRED observations — had never been invoked by any recurring job, route, or script since its one-time Milestone 5 seed (`fred_series_registry.last_synced_at` was `2026-08-06 14:20 UTC` for both series, unchanged since). Not a provider error, not a caching/TTL bug (`compute_freshness` correctly showed `cached`, derived from `retrieved_at` as designed — it was never lying), and not a wrong-row-selection bug (`get_latest_observation`'s `ORDER BY obs_date DESC LIMIT 1` was already correct) — purely a missing recurring trigger. Live FRED confirmed the real latest observations were `SOFR=3.63` (`2026-08-10`) and `BAMLH0A0HYM2=2.70` (`2026-08-07`). Fixed in two parts: (1) an immediate one-time manual refresh via the existing, unmodified `sync_series`, verified live in production; (2) `app.scripts.run_nightly_scheduled_discovery` now also refreshes exactly these two series on every correct-hour (10 PM ET) trigger, independent of the market-discovery research-cycle duplicate-check (a different cadence, a different data source) and isolated per-series (one series' failure never blocks the other or the research cycle). No historical discovery, SEC backfill, CourtListener sync, or Anthropic call involved in this fix. 4 new tests (skip-without-key, per-series failure isolation, correct-hour triggers refresh, wrong-hour trigger does not) | — | `backend/app/scripts/run_nightly_scheduled_discovery.py` | **Resolved** — still pending KI-002 (Railway cron trigger creation itself) to run automatically in production; the code path is proven and tested |
| TD-025 | `research_note.access_classification` (`standard`/`restricted`, Milestone 10A) is captured on every note and shown in the UI but not enforced by any route dependency — deliberately distinct from `DataClassification`/`policy_check`, which governs licensed *external* data, not an analyst-authored note's internal visibility | Low | Wire real enforcement once TD-002 (Supabase Auth JWT validation, `user`/`role`/`user_role`) exists — enforcement without real identity would be theater, not a control | Open (deferred by design, `backend/app/schemas/research.py`, `backend/app/api/routes/research_notes.py`) |
| TD-021 | Model non-determinism on nested-subsidiary issuer attribution: live quality-validation during Milestone 7.5.3 re-reviewed a real production alert (EchoStar Corporation 8-K disclosing Chapter 11 filings by subsidiaries HSSC/HNS Americas) through both a fresh Haiku call and a fresh Sonnet call — both independently returned `issuer_is_subject=true`, disagreeing with the original stored value (`false`, from an earlier Sonnet review of the identical excerpt). This is *not* a Haiku-specific reliability gap (a fresh Sonnet call reproduced the same disagreement) — it appears to be genuine model non-determinism on a hard, legitimately ambiguous judgment call (a subsidiary filing vs. "the issuer and its consolidated subsidiaries acting together") of exactly the kind Milestone 7.5.1's audit was built around. The routing policy correction this milestone made (high-impact categories always go to Sonnet, never Haiku) is still the right conservative default, but does not fully close this — the underlying instability exists in Sonnet's own judgment on repeated fresh calls too | Medium | Consider a stricter human-review gate specifically for subsidiary/nested-entity Chapter 11 attribution (e.g. never auto-upgrade `verified` membership on this evidence type without an explicit second confirmation), or accept the existing `partial`/upgrade-only design as sufficient mitigation — a product decision, not purely an engineering one | Open (discovered during Milestone 7.5.3's live quality validation, not guessed) |

---

# Known Issues

| ID | Description | Impact | Status |
|---|---|---|---|
| KI-003 | ~~Milestones 10A and 12 were committed locally (`fbf5da4`/`707f4b0`, `b0c14eb`/`4840634`) but never pushed to `origin/main` — Vercel/Railway both deploy from that branch via GitHub integration, so production stayed frozen at Milestone 9 (`111477e`) while both milestones were reported complete.~~ **Resolved 2026-08-12.** User caught the gap by inspecting production directly (Search nav item and Research Notes missing). Investigated and confirmed via `git ls-tree origin/main`, live `404`s on `/api/search`/`/api/research-notes`, and a byte-for-byte match between `origin/main`'s `Layout.tsx` nav list and what the user reported seeing. A related finding: the shared production Supabase database was *not* stale — migrations `0015`/`0016` were applied live from local dev per this project's one-shared-database convention — so for a window, the database briefly carried schema no deployed code referenced (additive-only, not a live risk, but a real asymmetry). Fixed with one authorized `git push origin main`; both Railway and Vercel auto-deployed within minutes; re-verified live (`/api/search`, `/api/research-notes` returning real data on Railway; `Search` nav item, header search box, and a working grouped search on Vercel). See `BUILD_LOG.md` 2026-08-12 entry. | Both milestones were invisible in production despite being reported complete — now resolved, and both are confirmed live. | **Resolved** |
| KI-002 | ~~The DST-safe nightly scheduler wrapper's two Railway Cron triggers had not been created.~~ **Resolved 2026-08-11.** Railway CLI installed (npm, v5.37.3), authenticated via the official browser OAuth flow, and used to provision two new sibling services in `wonderful-dream` → `production`: `nexus-nightly-10pm-edt` (`0 2 * * *` UTC) and `nexus-nightly-10pm-est` (`0 3 * * *` UTC), both running `python -m app.scripts.run_nightly_scheduled_discovery`, both built successfully from the same repo/Dockerfile as `nexus-credit-intelligence` (root directory `/backend`). A real deploy-time discrepancy was found and fixed during provisioning: Railway's config-as-code always overrides dashboard/API-set values, so the two cron services could not share the existing `backend/railway.toml` (its `[deploy] startCommand` is the web service's `uvicorn` command, which would have silently overridden the cron services' start command on every deploy) — fixed with two new dedicated config files, `backend/railway.nightly-edt.toml`/`railway.nightly-est.toml`, each declaring the same Dockerfile build plus the correct `startCommand`/`cronSchedule`, leaving the web service's own `railway.toml` completely untouched. Secrets were never read/printed during setup — all required variables (`DATABASE_URL`, `DIRECT_DATABASE_URL`, `SEC_USER_AGENT`, `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, `LLM_PROVIDER`, `COURTLISTENER_API_TOKEN`, `FRED_API_KEY`, `ENVIRONMENT`, `LOG_LEVEL`) were set as Railway reference variables (`${{nexus-credit-intelligence.VAR}}`) pointing at the existing service's own values, plus `TZ=America/New_York` and explicit `NIGHTLY_MAX_AI_COST_USD=2.00`/`NIGHTLY_MAX_AI_CALLS=300`/`NIGHTLY_MAX_SONNET_CALLS=75` (matching the wrapper's own code defaults, set explicitly for dashboard-visible auditability). Both cron services confirmed `● Online` by Railway itself, correctly categorized as "Cron jobs" (not services) with `0/1 running` and correct next-run countdowns; the existing web service confirmed unchanged and healthy (`GET /health` → 200) throughout. | — | **Resolved** — nightly automation is active; first real execution expected the next 10 PM America/New_York |
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

**Milestone 7.5 (SEC Market Discovery & Automatic Issuer Enrichment) is
complete**, inserted before Milestone 8 by explicit approved direction
(2026-08-07). Nexus moves from monitoring only its 23 hand-curated issuers
to discovering distress-relevant issuers directly from live SEC filing
activity via SEC's full-text-search API (`efts.sec.gov/LATEST/
search-index`, shape live-verified before implementation, not guessed), a
CIK-first shared issuer identity resolver (extracted from the existing seed
script's word-boundary-matching discipline, with full-text-search hits
already carrying an authoritative CIK from SEC itself — a strictly lower
false-positive-risk design than the original ticker/name resolver), and a
reusable per-issuer/per-provider enrichment orchestrator
(`issuer_enrichment_status`) that runs SEC/CourtListener/OpenFIGI
enrichment automatically for both newly-discovered and already-known
issuers, driven by staleness/never-checked/retry-due policy rather than a
one-time "new issuer" trigger. ADR-020 supersedes ADR-019 to allow
algorithmic CourtListener docket auto-linking on a hierarchy of
independent strong identity signals (legal name, case number and court
*referenced in the triggering SEC evidence*, filing-date correlation,
named-debtor match) with case-type consistency required and jurisdiction/
HQ correspondence explicitly excluded as a required signal (debtors
routinely file outside their home jurisdiction) — anything short of a
unique, uncontradicted strong-signal match routes to
`ambiguous_manual_review`, never a guess. Synthetic/demo data
(Cobalt Ridge Energy Corp, the 8 synthetic loan issuers) is isolated from
default real-data views by filter, not a separate UI mode.

Execution ran through the planned **hard human-approval gate**: the full
pipeline was implemented and run live for the 2026-07-01→2026-08-06 pilot
window only (89 candidates, 1 transient error), manually quality-reviewed,
and reported in full (queries executed, filings examined, Layer-0/Layer-1
candidate counts, issuers resolved existing/new/ambiguous/rejected,
evidence/alerts by severity, CourtListener auto-link/no-match counts,
OpenFIGI results, provider errors, elapsed time) — then execution stopped
completely pending review. Only after the user reviewed that report and
explicitly approved continuing did the 2026-01-01→2026-08-06 historical
backfill run, using the identical production pipeline (603 candidates, 11
transient errors, ~1.8%, each isolated to its own issuer with zero
orphaned rows). CourtListener's conservative auto-link policy produced
zero verified auto-links across both runs — an accepted, expected result,
not a defect. A real bug found during the post-backfill browser
walkthrough (`get_morning_brief`'s severity breakdown undercounting past
500 alerts due to a page-limited summation) was fixed and regression-
tested. Full metrics, quality-review findings, and problems/solutions for
both the pilot and the backfill are recorded separately in `BUILD_LOG.md`
(Parts 1 and 2) so the actual history is preserved, not merged.

**Milestone 7.5.1 (Signal Quality & Research Universe Calibration) is
complete**, inserted before Milestone 8 by explicit direction after
production inspection showed individual alerts were well-calibrated but
some Research Universe memberships were broader than their evidence
justified. An audit-before-changing-logic pass (never assuming the alert
engine was wrong, tracing every sampled membership through
`collection_membership` → `research_evidence` → the matched rule → the AI
review → provenance) root-caused the real bug: `classify_issuer` gated
automatic membership on `research_evidence`'s raw Layer-1 deterministic
severity, which has no concept of *whose* event a matched phrase
describes. Live-verified: the majority of "verified" System-Detected:
Chapter 11 memberships (BlackSky Technology, Ameresco, Skyworks
Solutions, Collegium Pharmaceutical, and ~35 others of the original 54)
were actually about a director's former employer, a customer, a peer
company, or SEC boilerplate — not the issuer's own bankruptcy — while the
AI-reviewed *alert* for the exact same evidence had already correctly
said so in its own wording (e.g. "relates to a director's prior company,
not BlackSky"), a judgment classification never consulted. Fixed by
gating on the AI-reviewed alert's severity plus a new
`issuer_is_subject` field (migration `0011`, `EvidenceReviewResult`
extended) instead of raw Layer-1 severity — requiring an *explicit* `true`
for automatic `verified` status, since Chapter 11 is this system's one
objective, highest-precision-required category. A second, independently
live-proven bug was found via this milestone's required benchmark check
against known 2026 bankruptcy filers (Sangamo Therapeutics, Cumulus Media,
QVC Group, and Trinseo were correctly found and classified; FAT Brands,
Bitcoin Depot, Inotiv, and GoHealth were real, confirmable misses): SEC's
own full-text-search `forms` parameter silently drops ~96% of real hits
when amendment-suffix forms are mixed into one request (`forms=8-K,10-K/A`
returns 0 hits; `forms=8-K,10-K` returns 1002) — fixed by splitting into a
base-forms request and an amendment-forms request per query. A controlled,
auditable, idempotent reconciliation script
(`app.scripts.reclassify_system_universes`) — which never deletes an
issuer/filing/evidence/alert/provenance row and never touches an
analyst-curated membership — recomputed every evidence-driven Research
Universe membership from the corrected rules against the live shared
Supabase project: System-Detected Chapter 11 54→20, Distressed Core
398→299, Default/Covenant Stress 281→173, Liability Management 68→33,
Refinancing Risk 130→115; Going Concern 210→244 and Post-Emergence 0→14
*increased* — Post-Emergence had been structurally unreachable before this
fix (its only rule scores `medium`, below the old raw-severity `high`
gate), not a regression. Full findings, the complete before/after count
table, representative quality-review examples per category, and test
results are recorded in `BUILD_LOG.md`.

**Milestone 7.5.2 (Daily Delta Run & Morning Research Brief Semantics) is
complete**, inserted before Milestone 8 by explicit direction to prove
the real day-to-day operating loop before building anything further on
top of it. Root cause of production's stale "Last successful run: Aug 6"
display, found by code inspection before any change: `get_latest_
successful_run` on both `filing_monitor_run` and `market_discovery_run`
treats *any* successful mode — including `backfill` — as the watermark/
display source, so a historical backfill's completion silently stood in
for "the last normal daily check-in," and no genuine `delta`-mode run of
either pipeline had ever actually completed. The fix establishes one
authoritative "latest successful daily run" concept — mode `delta`/
`baseline` only, `backfill` explicitly excluded, whichever of the two
Milestone 7.5 pipelines is more recent — driving both the Morning Brief's
summary metrics and its displayed alert rows through the identical
boundary, so the page can never show a small "actionable alerts" count
above a list of hundreds of unrelated historical alerts below it.
Historical backfill data is untouched and remains fully queryable in
Issuer Detail, Research Universes, and evidence drill-down — only the
Morning Brief's *default* view is daily-scoped (a "Show historical
alerts" toggle remains available as the one explicit escape hatch).

A second real bug was found live, not guessed, running the actual
2026-08-07 delta: `since` (the boundary every "new_*" count is computed
against) was originally set to the latest successful run's `completed_at`
— but everything that run itself discovers is necessarily written
*before* its own completion timestamp, so a `completed_at` boundary
silently excluded the run's own output entirely (the run's first pass
showed `evidence_created: 0`/`alerts_created: 0` in the brief despite 822
real evidence rows and 356 real alerts having just been created).
Corrected to `started_at`, which is safe and non-overlapping across
consecutive daily runs by construction (a run's `started_at` always
follows the previous run's `completed_at` in this pipeline's sequential
operating model).

A real 2026-08-07→08 delta ran through the existing, unmodified
market-discovery pipeline (TD-014's SEC `forms` fix active): 38 SEC
full-text-search queries, 519 filings examined, 285 candidate filings, 246
new issuers discovered, 39 already-known issuers touched, 0 ambiguous/
rejected, 1207 new SEC filings, 822 new research evidence rows, 356 new
alerts (49 high / 65 medium / 242 low; 351 AI-assisted, 5 deterministic),
0 CourtListener docket entries (root-caused as genuinely correct — only 3
of 285 processed issuers had docket-relevant evidence on file to even
trigger a CourtListener search, and all 3 returned no matching docket), 0
errors, elapsed 3509s (~58.5 minutes) — the first realistic nightly
operating-time estimate for this pipeline. A same-window re-run (as
`backfill` mode with explicit `--start`/`--end`, since `delta` mode
self-advances its window from the watermark and can't literally repeat a
past window) proved full idempotency: identical row counts across
`issuer`/`sec_filing`/`research_evidence`/`alert_event`/
`market_discovery_candidate`/`security`/`court_docket_entry` before and
after, 38.7s elapsed. No exact AI token/cost figure is reported — the
codebase captures no token usage or per-call count today (see TD-016);
351 AI-assisted alerts is a verified lower bound on successful AI review
calls, not a call count. TD-017 records a related, separately-discovered
gap: the run's own printed/persisted `evidence_created`/`alerts_created`
counters don't include the enrichment orchestrator's own evidence/alert
creation, undercounting real activity — the Morning Brief itself is
unaffected, since it queries `created_at`/`triggered_at` directly, never
these run-row counters. Railway Cron remains deliberately unactivated —
this milestone proved the daily run manually; scheduling is a separate,
explicitly-approved follow-up. Milestone 15 (Railway/Vercel deployment
validation) was found already satisfied while verifying this milestone's
production behavior and marked "Completed Early," not newly deployed by
this milestone. Full metrics, the idempotency-rerun result, and
production verification are recorded in `BUILD_LOG.md`.

**Milestone 7.5.2 correction (same day, explicit follow-up direction):
Morning Research Brief user-relative semantics.** The daily-run-boundary
fix above was still, at bottom, "what did the last pipeline run do" —
correct, but not the product question an analyst actually asks
("what changed since I last looked"). Corrected the brief's definition
end to end:

- **User-relative `period_start`**, not a pipeline-run watermark: a new
  `morning_brief_view` table (migration `0012`) records each genuine brief
  viewing occasion; `GET /api/morning-brief` is a pure read computing
  `period_start` from the most recent recorded view, and a separate
  `POST /api/morning-brief/view` (called by the frontend only after the
  brief has already been read, so a visit never reads its own not-yet-
  recorded view) advances it — but only if the prior view is more than a
  documented `MIN_VIEW_GAP` (4 hours) old, which is what keeps rapid
  refresh/reopen idempotent within one working session while still
  advancing naturally across lunch breaks, overnight gaps, weekends, or
  any multi-day absence, with zero day-of-week logic needed once a real
  view exists. A genuinely first-ever view (no prior row) falls back to
  the previous business-day morning, 06:00 America/New_York — documented,
  never an arbitrary run timestamp.
- **No per-user state was faked.** Direct inspection confirmed Nexus has
  no authentication/session infrastructure (TD-002, open):
  `Settings.auth_enabled = False`, no `user` table, no session/cookie
  middleware, no `Depends(get_current_user)` anywhere in `app/api`, zero
  frontend `localStorage`/`sessionStorage` usage. `morning_brief_view` is
  therefore a single shared timeline, not a per-user one — the cleanest
  honest interim boundary given that reality, with the real per-user
  requirement recorded as new Technical Debt (TD-018) rather than
  papered over.
- **Pipeline/run counters demoted, not deleted.** Universes/issuers
  monitored, raw filing/evidence counts, and the daily-run-boundary logic
  from the first pass (unchanged) all moved into a secondary
  `RunDetails` block (`GET /api/morning-brief`'s `run_details` field,
  rendered behind a collapsed "Show run/data details" panel) — still
  fully preserved, no longer the primary view.
- **Developments, not alerts, are the display unit.** New
  `IssuerDevelopment` grouping: every alert in the current period is
  grouped by issuer, ranked severity-first then most-recent-second, and
  partitioned into `new_developments` (`is_backfill=False` — genuinely
  new events) vs. `historical_intelligence` (`is_backfill=True` — an
  older event Nexus happened to discover this period) — reusing the
  already-correct `is_backfill` signal rather than inventing a new one.
  The primary summary bar now reports issuers-with-developments and
  high/medium/low counts (scoped to `new_developments` only), not raw
  pipeline statistics.
- **Research Universe membership changes surface only when they
  themselves are the development** — a new `collection_membership.
  updated_at` column (same migration `0012`, backfilled to `added_at` for
  every pre-existing row so the correction couldn't manufacture 540+ false
  "just changed" memberships on its first real run) lets a `partial` ->
  `verified` upgrade be distinguished from a brand-new membership;
  membership *removal* isn't detected here, since the live daily path
  never removes one (only the separate, manual Milestone 7.5.1
  reconciliation script does).
- **A real performance regression was caught and fixed before this
  shipped**, not after: the first implementation issued two extra
  database queries per alert (an issuer lookup and a universe-membership
  lookup), which is fine at the existing `/api/alerts` endpoint's
  page-capped scale (≤200) but, applied to a whole period's worth of
  alerts (~350 in the real Aug 7-8 data), meant 700+ sequential round
  trips to the shared Supabase instance — a live test against real
  production data confirmed the endpoint never completed within 50
  seconds. Fixed with two new batch-lookup repository functions
  (`issuer_repository.list_issuers_by_ids`,
  `collection_repository.list_collections_for_issuers`) replacing the
  per-alert queries with two queries total; the same real request then
  completed in ~1.7 seconds.
- Regression tests cover the explicitly required scenario set: previous-
  day return, a multi-day (Friday-to-Monday-shaped) gap, a longer skip,
  a first-ever view, an old filing discovered today (historical
  intelligence) vs. a genuinely new event today (new development), a
  Research Universe membership change, no material changes, and
  idempotent refresh/reopen — 9 integration tests plus 7 pure-logic unit
  tests for the boundary/fallback math, all passing against the live
  shared Supabase project. Full metrics, the real production-latency
  before/after, and browser verification are recorded in `BUILD_LOG.md`.
- Production browser verification of this pass then found a genuinely
  unresolved intermittent `503` on the new `POST /api/morning-brief/view`
  endpoint (TD-019) — extensively investigated across two rounds (a
  disproved response-size hypothesis, a TanStack Query mutation `retry`
  live-verified to never actually fire, a direct manual retry whose
  real-world effectiveness couldn't be confirmed either) without a
  conclusive root cause. Honestly recorded as open, not claimed fixed,
  since it never blocked the primary `GET /api/morning-brief` read.

**Milestone 7.5.2 correction, third pass (same day, explicit follow-up
direction): business-day research-cycle semantics, not page views.**
Direct instruction: "opening, refreshing, closing, or revisiting Morning
Research Brief must NEVER alter the comparison window" — the second
pass's `morning_brief_view` boundary violated this in spirit even though
it was technically idempotent within a session (`MIN_VIEW_GAP`): a page
view is not a research boundary at all, business-day research cycles
are. Corrected end to end:

- **`latest_research_day`/`preceding_research_day` replace `period_start`
  entirely** — both derived purely from canonical successful daily-run
  data (`DailyRunSummary.research_day`, a new field: `window_start_date`
  for `market_discovery_run`, `previous_watermark`'s date for
  `filing_monitor_run`, both in America/New_York) plus calendar
  business-day arithmetic (`_previous_business_day`: Mon-Fri only,
  weekends skipped — Friday's preceding day is Thursday, Monday's is the
  prior Friday, never Saturday/Sunday). `preceding_research_day` is
  computed by date arithmetic, never by requiring a second real run to
  exist, so even the very first daily run ever completed already has a
  well-defined comparison. A genuinely first-ever research cycle (no
  successful daily run has ever completed) falls back to the most recent
  business day on/before today and the day before that — reachable only
  once per fresh deployment.
- **`morning_brief_view` and `POST /api/morning-brief/view` removed
  entirely** (migration `0013`) — per explicit instruction to reassess
  rather than carry unused architecture: nothing else in the codebase
  ever read the view log (no "unread" badge, no read-state UI), so once
  period calculation stopped depending on it, it served no purpose.
  TD-018 (per-user scoping deferred) and TD-019 (the unresolved `503` on
  that specific endpoint) are both closed by this removal — TD-018
  because a research cycle is inherently shared, not per-user, so the
  concern it described no longer applies; TD-019 because the endpoint
  that exhibited the bug no longer exists, though the `503`'s root cause
  itself was never explained and is recorded as such, not silently
  dropped from the record.
- **The product-focused UI is unchanged**: issuer-grouped material
  developments, severity ranking, `new_developments` vs.
  `historical_intelligence` (still the `is_backfill` split, untouched),
  and operational pipeline metrics still live behind "Show run/data
  details." Only the top summary's framing changed, to "Latest research
  day: Aug 7, 2026 · Compared with: Aug 6, 2026."
- New tests: 6 pure-logic unit tests (`_previous_business_day`/
  `_most_recent_business_day` — including the explicit Friday→Thursday
  and Monday→Friday-skipping-the-weekend cases) plus 9 integration tests
  (Friday/Monday research-day comparisons, a first-ever-cycle fallback,
  old-filing-vs-new-event partitioning, a universe membership change, no
  material changes, and two idempotency proofs: repeated calls to
  `get_morning_brief` return byte-identical windows, and only a genuinely
  new, later-completing daily run ever advances it) — replacing the prior
  pass's now-obsolete view-based test suite, not adding alongside it.
- Production-verified: `GET /api/morning-brief` against the live shared
  database returns `latest_research_day: "2026-08-07"`,
  `preceding_research_day: "2026-08-06"`, `research_cycle_is_fallback:
  false` — matching the real completed Aug 7 delta run exactly, and
  confirmed unchanged across repeated requests.

**Milestone 7.5.3 (Historical Discovery Coverage Repair)'s zero-AI
ingestion is complete; AI review of the resulting deferred bundles
remains separate and not yet authorized.** After the AI cost-control
layer described above (`app.ai.model_router`, `ai_call_log`, hard
per-run budgets) was built and tested, the user authorized a **zero-AI**
(`--ai-mode zero`, $0 Anthropic spend) re-run of the 2026-01-01→
2026-08-06 historical window, using TD-014's corrected `forms` behavior,
purely to measure real coverage before approving any paid AI review.
Five live attempts ran 2026-08-09→10; four crashed on genuine
infrastructure issues (two SEC-side transient `500`s hitting the
top-level query loop's missing per-query error handling — TD-022 — and
two previously-undocumented stall types, a DB idle-in-transaction hang
and an SEC-document-fetch hang, both safely killed and resumed via
existing idempotency); the fifth completed with 0 errors. Final state:
2,652 issuers (from 787), 28,170 SEC filings (from 7,243), 22,252
research evidence rows (from 6,239), 3,123 alerts (from 2,212) — all
confirmed real, zero duplicate `(cik, accession_no)` pairs or issuer
CIKs, and confirmed $0 Anthropic spend throughout (`ai_call_log`
unchanged at 8 rows across all 5 attempts). Deferred bundles (evidence
that needed AI judgment but received none, per zero-AI mode's design)
remain reachable by a future AI-enabled run via the same `bundle_key`
idempotency check — that review pass is intentionally **not** run by
this milestone and is not auto-triggered by anything; it stays a
separate, explicitly-approved-only effort, same as the historical
backfill itself was.

**Milestone 8 (Watchlists) is complete.** Per Phase 0's required
architecture check against ADR-016/PLAN.md before implementing: this
milestone's original brief proposed new dedicated `watchlist`/
`watchlist_member` tables, which would have silently contradicted
ADR-016's already-accepted, already-partially-built decision that
Research Universes and Watchlists share one `collection`/
`collection_membership` table pair, discriminated by `collection_type`.
That conflict was reported before any implementation code was written;
the user's explicit direction was to reuse the existing schema exactly
(`collection_type=watchlist`, `scope=personal`, `curation_method=
user_created`, membership through the existing `collection_membership`
table) and add only what was genuinely missing — so, as ADR-016 itself
anticipated, **no migration was needed**. New: `update_collection`/
`delete_collection` on `collection_repository`, three N+1-avoiding batch
repository functions, `watchlist_service.py` (built on the same
`resolve_research_cycle`/`is_new_development` Morning Brief already uses,
so "new development" means the same thing everywhere), the Watchlists
API, and the frontend (landing page, detail page, one reusable Add to
Watchlist component wired into Issuer Detail). Issuer Detail's existing
"Which Research Universes is this issuer in?" section was explicitly
hardened to exclude `collection_type=watchlist` memberships, so a
personal Watchlist never leaks into that organization-coverage section.
A real "CFO Demo Watchlist" (6 real issuers, real alerts, real
provenance — no synthetic data, no fixture) was created through the
application's own `watchlist_service`, not a script bypassing it. No
per-user authentication exists yet (TD-002) — every Watchlist is
`scope=personal`/`owner_user_id=NULL` in a single shared analyst
workspace; the schema already supports per-user `owner_user_id` cleanly
once real authentication exists, requiring no further schema change.

**The Alerts Center (§18 build-order row 10) is complete**, built ahead
of Milestone 9 (Research notes/documents + audit events) by explicit user
direction. Per Phase 0's required architecture check: `alert_event` was
already the canonical research-alert record (ADR-018, Milestone 6.5) with
a working API (list/filter/paginate/acknowledge/dismiss) before this work
began — PLAN.md's original §12 sketch of a separate `alert_rule`/
`alert_engine.py` rule-evaluation system was never built and is
superseded by this section, since building it would have been exactly
the "second competing alert system" the incoming brief explicitly
prohibited. This was additive UI/workflow over already-approved
architecture, not a new architectural decision, so no ADR was written.
`AlertsPage.tsx` (`/alerts`) is a new analyst-inbox view — summary tiles,
URL-persisted filters (including a new `watchlist_id` filter), and the
existing `AlertCard` component in a paginated list — answering "what
research alerts need my review, especially for issuers I care about,"
deliberately distinct from the Morning Research Brief's "what changed in
the latest research cycle." Building it surfaced and fixed two real,
live-caught regressions that predated this milestone but only became
reachable once real Watchlists existed: `AlertRow.universe_names` was
leaking Watchlist names (fixed by splitting into `universe_names`/
`watchlist_names`), and filtering alerts by a multi-issuer collection
(Research Universe or Watchlist) mis-paginated (an already-paginated,
unfiltered page was being post-filtered in Python, under-reporting
`total` and silently dropping rows). Both fixed at the SQL level. Zero
migration, zero Anthropic calls. See §24.11 for the full design record.

**Milestone 10A (Research Notes + Audit Trail — PLAN.md row 9's Research
Notes half) is complete**, built as the first of two explicitly approved
sub-phases of row 9 — 10B (Research Documents + Supabase Storage) remains
deferred and not started. `research_note`/`research_note_version` (full-
snapshot-per-edit versioning) and `audit_event` (the app's first audited-
write path) are live, migrated (`0015`), and integrated into Issuer Detail
beneath the Distress Timeline, per the requested `Issuer → Distress
Timeline → Analyst Research Notes` hierarchy. No `user`/`role`/`user_role`
tables were built — a pre-implementation schema-design check found no
genuine 10A functional need for them, and `collection.owner_user_id`
(Milestone 8/ADR-016) had already established the nullable-identity
pattern this milestone reuses. A real Demo Research Note on Trinseo PLC
(3 versions, dated to Trinseo's real covenant-stress → going-concern →
Chapter 11 timeline, citing real `alert_event` evidence by reference) was
seeded idempotently through the app's own `research_note_service`. A real
ordering bug (`now()` vs. `clock_timestamp()` for audit/version
timestamps, live-caught by an integration test before the first commit)
was found and fixed, with the migration corrected and re-verified with
zero drift. This was additive implementation of already-approved
architecture (§4.10/§4.12), not a new architectural decision, so no ADR
was written. See §24.12 for the full design record.

**Milestone 12 (Universal Search) is complete**, built in two staged
sub-phases (12A backend, 12B frontend) after a full architecture-and-
product-design review that the user explicitly reviewed and approved
before any code was written — no ADR/schema conflict was found. Per-table
generated `tsvector` columns (not a new synced `search_document` table)
resolve TD-003, covering `issuer`/`security`/`alert_event`/`court_docket`/
`court_docket_entry`/`collection`/`research_note`; `research_evidence`,
`research_note_version`, `audit_event`, `docket_document`, and all of 10B
are deliberately excluded. Deterministic ranking only — exact identifiers
(Tier 0) never blended with prefix/full-text/trigram fuzzy tiers, zero
Anthropic calls anywhere. A live-caught bug (`concat_ws` is `STABLE`, not
`IMMUTABLE` — Postgres rejected the original `research_note` generated
column) was fixed before the first commit, migration re-verified with
zero drift. `GlobalSearch` (debounced AppBar typeahead, grouped, full
keyboard navigation) and `/search` ship in 12B, reusing Credit Universe's
own filter for "see all" rather than building a second pagination system.
See §24.13 for the full design record.

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

### 4.7 Watchlists (superseded by ADR-016 — see §24.1; Milestone 8 complete)

This section's original dedicated-table design (`watchlist`/
`watchlist_membership`, seeded with the eleven named lists in §14) was
**never built**. It was superseded before Milestone 8 implementation began
by ADR-016's generalized `collection`/`collection_membership` tables
(§24.1), which Research Universes already used — Watchlists reuse that
same schema (`collection_type=watchlist`) rather than introducing a
parallel one. See §24.1 for the actual, implemented design and §14 for why
the eleven-list seed plan was not carried forward.

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

## 14. Demo watchlists (superseded — see below; not seeded)

**This section's eleven-named-list plan was not carried forward into
Milestone 8.** It predates ADR-016's Research-Universes/Watchlists split
(§24.1): by the time Watchlists was actually implemented, the 23 real,
SEC-verified issuers this section's candidates were drawn from (Rite Aid,
Lumen Technologies, Diebold Nixdorf, Carvana, Community Health Systems,
Ford, Occidental, Kraft Heinz, DISH/EchoStar, etc.) were already organized
into 23 real Research Universes covering the same functional groupings
this table proposed (Distressed Core, Chapter 11, High Yield, Fallen
Angels, Refinancing Risk, Healthcare, Consumer & Retail, and more) —
seeding a second, parallel set of eleven curated lists as Watchlists would
have duplicated that existing coverage under a different product concept,
not added anything new. Milestone 8 instead created **one** real,
non-seeded Watchlist (the "CFO Demo Watchlist," §8 in the Milestone Status
table) built through the application's own Watchlist-creation workflow —
consistent with Watchlists being personal, analyst-created tracking lists
rather than a second organization-curated coverage taxonomy. The original
table below is kept for historical record only; none of its rows were
seeded.

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
8. Watchlists — implemented as `collection_type=watchlist` rows on the
   existing `collection`/`collection_membership` tables (ADR-016), not the
   dedicated tables or the ten-coverage/one-benchmark/comparison-view
   design originally sketched here — see §14 and §24.1.
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
13. Watchlists let an analyst create/rename/delete a personal tracking
    list and add/remove real issuers, showing real latest-development
    context per watched issuer (§24.1) — not the ten-coverage/one-benchmark
    seed originally sketched here, superseded by ADR-016 (see §14).
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
- **Watchlists** (§4.7, §14, Milestone 8 — **complete, 2026-08-11**) —
  personal-workspace tracking collections. `collection_type = watchlist`,
  `scope = personal`, `curation_method = user_created`. Built exactly as
  this section anticipated: no migration, reusing `collection`/
  `collection_membership` and the existing repository, with only the
  genuinely-missing rename/delete/CRUD/API/frontend pieces added
  (`watchlist_service.py`, `app/api/routes/watchlists.py`, the Watchlists
  landing/detail pages, and the reusable `AddToWatchlistButton`).
  `owner_user_id` stays `NULL` for every Watchlist under the current
  no-per-user-auth posture (TD-002) — a single shared analyst workspace,
  not per-user data; the column is already in place for real per-user
  ownership once authentication exists, requiring no schema change then.
  "New developments" per watched issuer reuses `morning_brief_service
  .resolve_research_cycle`/`is_new_development` directly — the exact same
  research-cycle boundary the Morning Research Brief uses, not a second
  definition.

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

The canonical daily/delta production entry point is
`python -m app.scripts.run_market_discovery --mode delta` (Milestone 7.5/7.5.2 —
supersedes `run_overnight_filing_monitor` for market-wide daily discovery; that
older known-issuer-only script remains available but has never been the
production daily driver). It self-computes its processing window from the last
successful run's watermark — never given an explicit `--start`/`--end` in normal
operation — writing through the same Provider DTO → Normalizer → Canonical
Domain Object → Repository → Evidence Evaluation → Alert Synthesis pipeline as
every interactive request (§3's "no job bypasses the pipeline" rule, §23.5).

**Production schedule (wrapper implemented and tested 2026-08-10; Railway
cron trigger creation itself requires dashboard/CLI access not available in
this environment — see PLAN.md's Known Issues and the operator instructions
recorded there for the exact steps to activate it)**: Railway Cron Jobs
evaluate schedules in UTC only
schedules in UTC only — no timezone parameter (verified against Railway's own
docs, not assumed) — so a single static UTC cron expression cannot correctly
represent "10:00 PM America/New_York" across a DST transition. Implemented
instead: `app.scripts.run_nightly_scheduled_discovery`, a thin wrapper invoked
by **two** Railway Cron triggers every night —

- `0 2 * * *` UTC (02:00 UTC — 10:00 PM Eastern *Daylight* Time)
- `0 3 * * *` UTC (03:00 UTC — 10:00 PM Eastern *Standard* Time)

— both pointed at the same command (`python -m
app.scripts.run_nightly_scheduled_discovery`). The wrapper computes the actual
current `America/New_York` wall-clock hour via Python's `zoneinfo` (the real
IANA timezone database — the correct 2026 US DST transition dates, 2026-03-08
and 2026-11-01, are never hardcoded anywhere in this codebase) and only
launches the real `run_market_discovery --mode delta` subprocess when that hour
is 22 (10 PM); the other trigger, landing on 21:00 or 23:00 ET depending on the
season, exits immediately as a no-op. Before launching, it also checks
`market_discovery_repository.get_latest_successful_daily_run` — the same
function the Morning Brief itself uses — and no-ops if a daily research cycle
has already completed for the current Eastern calendar date, layered on top of
(not instead of) Railway's own overlapping-execution skip. `TZ=America/New_York`
is set on the Railway cron service's environment as well, so the underlying
`run_market_discovery.py`'s naive `date.today()` call also resolves to the
correct Eastern business date rather than the container's default UTC (see
TD-023's note on why this matters). Recurring nightly AI budget defaults to the
2026-08-10 run's authorized limits ($2.00 / 300 calls / 75 Sonnet calls),
overridable via `NIGHTLY_MAX_AI_COST_USD`/`NIGHTLY_MAX_AI_CALLS`/
`NIGHTLY_MAX_SONNET_CALLS` Railway env vars without a code deploy.

Verifying a night's run succeeded requires no new dashboard — inspect the
newest `market_discovery_run` row (`mode='delta'`, `status`, window dates,
`completed_at`, `errors_count`), `ai_call_log` aggregated for that run, and
`GET /api/morning-brief`'s `latest_research_day`, all via existing
tooling/endpoints.

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

## 24.11 Alerts Center (Milestone 9 — complete, 2026-08-11)

**Phase 0 finding**: PLAN.md's original §12 "Alerts (new)" sketched a
rule-evaluation engine (`alert_rule`/`alert_engine.py`) that would check
enabled rules against "current data" and write new `alert_event` rows —
that engine was never built, because `alert_event` has been the real,
canonical research-alert record since Milestone 6.5's evidence→bundle→
alert pipeline (ADR-018), and `backend/app/api/routes/alerts.py` +
`alert_repository.py` (list/filter/paginate, acknowledge, dismiss) already
existed before this milestone started. Milestone 9 did not build a second
alert-generation system — it built an analyst-inbox UI/workflow layer over
the alerts that already exist, exactly as the incoming brief for this
milestone explicitly required ("Do NOT create a second competing alert
system"). §12 is accordingly superseded by this section for the actual,
implemented Alerts design; no ADR was needed since this is a UI/workflow
addition over already-approved architecture (ADR-018), not a new
architectural decision.

**"New alert" vs. "new development" — two distinct, deliberately
non-merged axes**:
- **"New development"** (Morning Research Brief, Watchlist detail's
  `issuers_with_new_developments`/`high_severity_count`, Milestone 8) —
  whether an alert's real-world `as_of_date` falls within the latest
  completed business-day research cycle
  (`morning_brief_service.resolve_research_cycle`/`is_new_development`).
  Never changes because someone reviewed the alert.
- **"New alert"** (Alerts Center's `new_count` tile, Watchlist detail's
  `new_alert_count`, the `status` filter) — `alert_event.status = new`,
  i.e. not yet acknowledged or dismissed. Never changes because a research
  cycle advanced; only an analyst action changes it.

An alert can be "new" on one axis and not the other in either direction —
e.g. an unacknowledged alert from three research cycles ago is a "new
alert" (needs review) but not a "new development" (not from the latest
cycle); a same-cycle alert an analyst already acknowledged is a "new
development" but not a "new alert." Both concepts read the same
`alert_event` rows; neither is computed from the other.

**Zero migration** — `alert_event` already had every field the Alerts
Center needed (`status`, `severity`, `detection_method`, `issuer_id`,
`evidence_ids`, `triggered_at`, `acknowledged_at`/`dismissed_at`,
`bundle_key`). Two genuine, narrow gaps were filled additively:
- `alert_repository.list_alerts` gained an `issuer_ids: list[UUID] | None`
  filter (alongside the existing single `issuer_id`) and a new
  `count_alerts`/`search_issuers_with_alerts` pair — no new table.
- `AlertRow` gained `watchlist_names: list[str]`, split out from
  `universe_names` (see the regression below); `WatchlistSummary` gained
  `new_alert_count`/`high_severity_alert_count`, additive fields alongside
  Milestone 8's existing `issuers_with_new_developments`/
  `high_severity_count`.

**API**: `GET /api/alerts` gained a `watchlist_id` filter (alongside the
existing `issuer_id`/`universe_id`/`severity`/`category`/
`evidence_provider`/`status`/`detection_method`/`date_from`/`date_to`/
`triggered_since`/pagination). New `GET /api/alerts/summary`
(`AlertsSummary`: `new_count`, `high_severity_count`,
`watchlist_alert_count`, `acknowledged_count` — four COUNT queries) and
`GET /api/alerts/issuers?q=` (issuer-name search scoped to issuers that
actually have at least one alert, backing the Alerts Center's issuer
filter — not a general issuer-search feature).

**Two live-caught regressions fixed as part of this milestone** (both
pre-dated Milestone 9 but only became reachable once real Watchlists
existed):
1. **`universe_names` leaked Watchlist names.** `AlertRow.universe_names`
   (and Morning Brief's identically-sourced per-alert universe badges) was
   built from every collection an issuer belonged to, unfiltered by
   `collection_type` — so an issuer on a Watchlist would show that
   Watchlist's name mislabeled as a "Research Universe" badge. Fixed in
   `filing_monitor_api_service._split_collection_names` and
   `morning_brief_service`'s per-cycle batch fetch: `universe_names` now
   always excludes `collection_type=watchlist`; the new `watchlist_names`
   field carries those instead.
2. **Multi-issuer collection filters mispaginated.** `list_alerts`'s
   `universe_id` filter (and the codebase before this fix had no
   `watchlist_id` equivalent) resolved a collection to its issuer set,
   then — when more than one issuer matched — fetched an already-paginated
   page unfiltered by issuer and post-filtered it in Python. This silently
   under-reported `total` and could drop alerts off a page for any
   Research Universe or Watchlist with more than one issuer. Fixed by
   resolving the issuer set before querying and passing it to
   `alert_repository.list_alerts`'s new `issuer_ids` filter, so filtering
   happens in SQL with correct pagination — applied uniformly to both
   `universe_id` and the new `watchlist_id`, not left inconsistent between
   the two.

**A third, more severe pre-existing bug was caught during production
verification** (not during code review — only a real browser click
surfaced it): `POST /api/alerts/{id}/acknowledge` rejected every real
request with `422`. Its single un-embedded `Body()` parameter made
FastAPI expect the raw body to *be* the `acted_by` string, but the
frontend has always sent `{"acted_by": ...}` (matching `dismiss_alert`'s
two-`Body()`-parameter shape, which auto-embeds and was unaffected) — so
the Acknowledge button had likely never worked in production. Fixed with
`Body(embed=True)`; a new route-level `TestClient` test suite
(`tests/test_alerts_routes.py`) was added specifically because the
existing service-layer integration tests call `filing_monitor_api_service`
directly and structurally cannot catch a FastAPI request-parsing mismatch
— only a real HTTP request through the route reproduces it.

**Performance**: `filing_monitor_api_service.alert_to_row` (looped, two
queries per alert — a real, previously-live N+1) was split into a
single-alert `alert_to_row` (used only by the evidence-detail/
acknowledge/dismiss endpoints, which operate on one alert) and a new
batched `_alerts_to_rows_batch` (used by the paginated list endpoint) —
one query for every alert's issuer, one for every alert's collections,
regardless of page size (up to 200 alerts/page).

**Frontend**: `AlertsPage.tsx` (`/alerts`, new nav item after Watchlists)
— four summary tiles (New/High Severity/Watchlist Alerts/Acknowledged,
informational, not clickable pseudo-filters), a URL-persisted filter bar
(Status/Severity/Watchlist/Research Universe/Detection/Issuer search
Autocomplete backed by `GET /api/alerts/issuers`), and the existing,
reused `AlertCard` (unchanged acknowledge/dismiss wiring) in a paginated
list (`TablePagination`, matching Credit Universe's existing convention).
`AlertCard` gained a category chip and Watchlist-membership chips
(bookmark icon, filled `primary` color — visually distinct from the
existing outlined Research Universe chips). Watchlist detail gained one
additional stat tile ("new alerts") and a "View Alerts" button
(`/alerts?watchlist={id}`); Issuer Detail gained a compact "View Alerts"
button (`/alerts?issuer={id}`) next to the existing Add to Watchlist
button — Issuer Detail does not duplicate alert cards; the Distress
Timeline remains its research-context view, Alerts Center is the
workflow inbox.

**AI/cost**: zero Anthropic calls anywhere in this milestone's code —
confirmed by inspection (no `app.ai` imports anywhere in the new/changed
files) and by design (every Alerts Center value is read from already-
persisted `alert_event`/`collection_membership` rows).

**Tests**: 23 new backend tests
(`test_filing_monitor_api_service.py`: watchlist filter, `universe_names`/
`watchlist_names` split, multi-issuer pagination correctness, issuer
search incl. exclusion of alert-less issuers, alerts summary counts,
invalid-alert acknowledge/dismiss, dismissed-alert-retained-with-evidence-
intact; `test_watchlist_service.py`: `new_alert_count` distinct from
research-cycle counts, exclusion of acknowledged/dismissed, empty-
Watchlist zero counts). 25 new/extended frontend tests (`AlertsPage.tsx`:
summary tiles, alert rendering, empty state, status/watchlist filter
re-fetch, acknowledge, dismiss, issuer link, source link, watchlist chip
rendering, pagination; `AlertCard.tsx`: category chip, Watchlist chip
distinction; `WatchlistDetailPage.tsx`/`IssuerPage.tsx`: View Alerts link
targets; `Layout.tsx`: nav position).

---

## 24.12 Milestone 10A — Research Notes + Audit Trail (Milestone 9/row 9 slice — complete, 2026-08-12)

**Scope**: PLAN.md row 9 ("Research notes/documents + audit events") split
into two approved sub-phases by explicit user direction. This section
covers **10A only** — `research_note`/`research_note_version` +
`audit_event`. Documents/Supabase Storage (10B) are explicitly deferred and
not started; `research_document` does not exist yet.

**Pre-implementation schema-design check**: no material architectural
conflict found with deferring real auth, deferring 10B, or building these
three concepts now — `collection.owner_user_id` (Milestone 8/ADR-016) had
already established the precedent this milestone reuses: a plain nullable
`text` identity column, no FK to a `user` table that doesn't exist, no
fabricated per-user ownership. `user`/`role`/`user_role` (§4.12) are **not
built** — genuinely no 10A functional requirement needs them, and building
them now would be exactly the "unused schema" the user asked to avoid; they
remain scaffolded only as a documented future dependency of TD-002.

**Schema (migration `0015`)**: `research_note` (id, issuer_id, security_id
nullable, title, thesis_status, conviction nullable, bull_case/base_case/
bear_case/catalysts/risks/invalidation_conditions all nullable text,
`evidence_refs` JSONB, access_classification, author_user_id nullable text,
`is_demo`, `current_version_number`, `is_archived`/`archived_at`/
`archived_by`, timestamps); `research_note_version` (full snapshot of the
same content fields plus `version_number`, `edited_by`, `edited_at`,
unique on `(research_note_id, version_number)`); `audit_event` (id,
`user_id` nullable text, `event_type`, `entity_table`, `entity_id`,
`before_state`/`after_state` JSONB, `occurred_at`). One deliberate
refinement of §4.10's original sketch: no generic `body_markdown` field —
the structured sections the user explicitly asked for (bull/base/bear
case, catalysts, risks, invalidation conditions) **are** the note's
content, so a parallel free-text body would just duplicate it. Live-applied
against the shared `nexus` schema; `alembic check` confirms zero drift
both before and after a mid-implementation correction (see below).

**`audit_event.event_type`/`entity_table` are plain, unconstrained `text`**
— every other new enum-shaped column in this milestone (`thesis_status`,
`conviction`, `access_classification`) uses the project's standard
text+CHECK pattern, but `audit_event` is deliberately the one exception:
§4.12 already scopes future audited actions across many unrelated
milestones (watchlist changes, alert-rule changes, entitlement changes,
admin actions, AI queries touching restricted data) that don't exist yet,
and a CHECK constraint listing only the three values 10A emits
(`research_note_created`/`updated`/`archived`) would force a migration
every time a later milestone adds a new audited action — the same
reasoning already applied to `sec_filing.form_type`.

**Note/version architecture**: every save — the initial create and every
material edit — produces one immutable, standalone `research_note_version`
snapshot of the *resulting* state, numbered sequentially from 1, so
"Version 1 → Version 2 → Version 3" always means three real, independently
-renderable states, the last of which is also the note's current live
content (never a diff-only or pre-image-only scheme). An edit is
"material" — and thus version-worthy — exactly when it changes any content
field; a save that changes nothing is a no-op (no new version, no audit
event), verified by both a unit test suite for the pure `_merge_fields`
comparison and an integration test. Within one edit's transaction, the
version row is written before the live `research_note` row is updated —
literal execution-order compliance with §4.10/§11's "snapshot before
applying the update," even though the snapshot's *content* is the
resulting state, not the pre-image (a deliberate choice favoring the more
intuitive Notion/Google-Docs-style "every version is a real, viewable
state" model the user's demo narrative explicitly calls for, over a
pre-image scheme that would leave the current live state un-numbered until
its next edit).

**A real bug was found and fixed during test-writing, before the first
commit**: `occurred_at`/`edited_at` initially used Postgres `now()` as
their `server_default`, which is frozen at *transaction* start, not
per-statement — two audit events (or two version snapshots) written inside
one transaction got an identical timestamp and an unstable relative
`ORDER BY occurred_at DESC` order. Live-caught by an integration test
reusing one savepoint-scoped session across a create-then-update sequence
(the same pattern this codebase's other integration tests use). Fixed by
switching both columns to `clock_timestamp()` (real per-statement wall-clock
time) — required downgrading migration `0015`, correcting the two `server_
default` values, and re-upgrading against the live schema before the
migration was considered final; `alembic check` re-confirmed zero drift
after the fix. This has no effect on normal production usage (each real
API request is its own transaction with its own start time), but makes the
audit trail's ordering guarantee correct even under a single multi-write
transaction, which is the more defensible property for an audit log to
have unconditionally.

**Audit-event architecture**: deliberately a separate concept from
versioning per the user's explicit instruction — a version reconstructs
*what the note said*; an audit event records *that a write happened, by
whom, when, and its before/after state* (as two named JSONB columns, not
one opaque `detail` blob, so "what changed" is inspectable without agreeing
on an internal shape first). `research_note_service` writes one audit event
per create/update/archive, always via the same service functions a real
UI action calls — never a bypassing script. No hard delete exists: archive
is the only "removal" path, so a note's own version/audit history can never
be destroyed along with it; archiving is idempotent (re-archiving an
already-archived note is a no-op, confirmed by a dedicated test asserting
exactly one `research_note_archived` audit event survives two calls).

**Shared-workspace/auth posture**: `AUTH_ENABLED` stays `false`;
`author_user_id`/`edited_by`/`archived_by`/`audit_event.user_id` are all
plain nullable `text` — a free-text "Your name (optional)" field in the UI,
attributed honestly to the audit trail, never a fabricated per-user
identity. `access_classification` (`standard`/`restricted`) is captured on
every note but **not enforced** by any route dependency this milestone —
deliberately distinct from `DataClassification`/`policy_check` (which
governs licensed *external* data, a different concept from an
analyst-authored note's internal visibility). Recorded as new TD-025 below
rather than silently left unexplained.

**APIs** (`backend/app/api/routes/research_notes.py`, prefix
`/api/research-notes`): `GET ?issuer_id=&include_archived=` (list),
`POST` (create), `GET /{id}` , `PATCH /{id}` (update — 409 if archived),
`POST /{id}/archive`, `GET /{id}/versions`, `GET /{id}/versions/{n}`,
`GET /{id}/audit-events`. Thin per §3 — all logic lives in
`research_note_service`.

**Frontend**: `ResearchNotesSection` (compact card list — title, thesis-
status/conviction badges, Demo badge, "Write Research Note" button)
embedded directly beneath the Distress Timeline on Issuer Detail, per the
requested `Issuer → Distress Timeline → Analyst Research Notes` hierarchy
— never overwhelming the timeline, a deliberate click-through to
`ResearchNotePage` for full content. `ResearchNoteEditorPage` (one
component, two routes — `/issuers/:issuerId/research-notes/new` and
`/research-notes/:noteId/edit`) renders the full structured form (Base/
Bull/Bear Case, Catalysts, Key Risks, Invalidation Conditions, an
add-by-reference Sources/Evidence list); an archived note routed to `/edit`
shows a read-only message instead of the form, matching the backend's 409.

**Version-history behavior**: `ResearchNotePage`'s right-rail Version
History list shows every version's number/timestamp/thesis-status/
conviction; clicking a non-current version loads its full standalone
content into the main panel behind a persistent "Viewing historical
Version N — read-only" banner with a one-click "Back to current," verified
live in the browser (Version 1's original `monitoring`/`low conviction`
content rendered correctly, distinct from the current `invalidated`/`high
conviction` state).

**Access-classification behavior**: stored and displayed (a Standard/
Restricted selector in the editor) but not gated — see TD-025. Consistent
with "keep identity nullable and honest," this milestone does not fabricate
enforcement it can't actually back with real identity/roles.

**Demo example**: `app.scripts.seed_demo_research_note` (idempotent, safe
to re-run) creates one real, permanently-committed Demo Research Note on
Trinseo PLC (`is_demo=true`, titled "Demo Research Note: ..." so the UI
always renders it as clearly synthetic provenance) with three real, dated
versions built through `research_note_service.create_note`/`update_note` —
the same service path a real analyst's UI action uses, not raw SQL. Every
evidence reference (`evidence_refs`, pointing at real `alert_event` rows by
id, never copying their content) and every underlying fact (covenant
stress 2026-02-17, explicit going-concern doubt 2026-03-13, the exchange-
offer/NYSE-delisting restructuring stretch through 2026-04-27, the
prepackaged Chapter 11 petition 2026-05-26, DIP financing 2026-06-01) is a
real, already-ingested row, live-queried against the `nexus` schema before
being written into the script — the analyst *conclusions* (thesis status,
conviction, bull/base/bear case, catalysts, risks, invalidation conditions)
are this script's own construction, written the way a real analyst
plausibly would given that evidence, never fabricated as though a real
Stonehill analyst wrote them. Version 1 (`monitoring`/`low`) → Version 2
(`active`/`medium`, going-concern doubt now explicit) → Version 3
(`invalidated`/`high`, Chapter 11 filed — the v2 invalidation condition was
met) reproduces exactly the demo narrative requested.

**Tests**: 6 new unit tests (`test_research_note_service.py`:
`_merge_fields` — `None`-means-unchanged, `""`/`[]` explicit-clear,
thesis-status transition, no-op-detection equality). 10 new integration
tests against the live `nexus` schema (create writes version 1 + audit
event; material update creates version 2 + before/after-state audit event;
no-op update writes neither; update of nonexistent/archived note; archive
idempotency and exactly-one audit event; archive of nonexistent note;
issuer listing respects `include_archived`; specific-version fetch;
`is_demo` persistence). 17 new frontend tests (`ResearchNotesSection`:
empty state, badges, Demo badge, create/detail link targets;
`ResearchNotePage`: structured-section rendering, 404, version-history
list/current-marker, historical-version switch, audit-trail rendering,
archive action, archived-note action-hiding; `ResearchNoteEditorPage`:
scoped create, disabled-until-titled, edit-mode hydration, update
submission, archived-note read-only message). Full existing suites
re-verified green: 511/511 backend (2 pre-existing, unrelated live-FRED
`502`s confirmed transient on immediate retry — 3/3 passed), 164/164
frontend.

**Migration verification**: `alembic upgrade head` applied live against the
shared Supabase project; `alembic check` confirms zero drift (twice — once
before, once after the `clock_timestamp()` correction above). No other
schema touched; no cross-contamination of the other application's objects.

**Production walkthrough**: real backend (`uvicorn`) + frontend (`vite
dev`) boot verified, then a full live-browser pass — Issuer Detail's new
Analyst Research Notes section renders beneath the Distress Timeline;
clicking into the Demo Research Note shows full structured content,
correct Version History (3 entries) and Audit Trail (3 entries); clicking
Version 1 correctly swaps in its historical, read-only content; a fresh
note was created end-to-end via "Write Research Note," then archived via
the Archive button (audit trail updated to "Note archived," Edit/Archive
buttons correctly hidden thereafter, note correctly excluded from the
issuer's active-notes list) — this test note was the only non-idempotent
write made during verification and was left archived (not deleted) so its
own audit trail stands as a real, honest artifact rather than being
scrubbed.

**Regression verification**: none found — this milestone is purely
additive (two new tables, one new route file, one new frontend section/two
new pages); nothing in the nightly scheduler, SEC/CourtListener/OpenFIGI/
FRED ingestion, AI routing, Morning Research Brief, Watchlists, Alerts
Center, Research Universes, Credit Universe, or Distress Timeline was
touched.

**Anthropic application calls**: **0**, confirmed by design (no `app.ai`
import anywhere in the new/changed files) and by inspection of
`ai_call_log` (unchanged row count before/after). AI-generated thesis
content was explicitly out of scope for this milestone.

**Technical debt**: new **TD-025** — `research_note.access_classification`
is captured and displayed but not enforced by any route dependency;
correctly deferred until TD-002 (real auth/roles) makes enforcement
meaningful, not a 10A gap. Minor, undocumented-as-TD limitation (judged too
small to warrant its own row): `ResearchNoteUpdate.conviction` cannot be
explicitly reset to unset once set — a `None` in a PATCH always means "no
change," not "clear it," since no 10A workflow needs to unset conviction
once assigned.

No ADR was written — this is additive implementation of already-approved
architecture (§4.10/§4.12, and the row-9 slicing this document's own build
order anticipated), not a new architectural decision, matching the
precedent set by Milestone 9/Alerts (§24.11) and Milestone 8/Watchlists.

---

## 24.13 Milestone 12 — Universal Search (12A backend + 12B frontend — complete, 2026-08-12)

**Scope**: PLAN.md §4.13 ("Search infrastructure") and §8 ("Universal
Search"), built as two staged sub-phases (12A backend, 12B frontend) per
explicit user direction, mirroring the 10A/10B staging pattern. A full
architecture-and-product-design review was completed and explicitly
approved *before* any code was written — no ADR/schema conflict was found;
this section documents the approved design as actually implemented.

**Searchable entity types**: `issuer`, `security`, `alert_event`,
`court_docket`, `court_docket_entry`, `collection` (Research Universes/
Watchlists/Benchmarks alike), `research_note` (current content only), and a
deliberately thin `sec_filing` metadata search. **Excluded**:
`research_evidence` (`alert_event` is already the canonical, human-facing
"distress development" unit — `issuer_timeline_service.get_issuer_timeline`
reads exclusively from `alert_event`, never `research_evidence`, confirming
this live), `research_note_version` (only the live note is indexed — no
`search_vector` column exists on that table at all, so a note's edit
history can never produce duplicate/near-duplicate search hits),
`audit_event` (operational log, not research content), `docket_document`
(no real extracted text exists anywhere in this schema yet), and all of
10B.

**Database/index strategy — resolves TD-003**: per-table generated
`tsvector` columns (`GENERATED ALWAYS AS ... STORED`) + GIN indexes,
**not** a separate synced `search_document` table. A generated column is
maintained automatically by Postgres on every INSERT/UPDATE — no new write
path for any of the many existing writers (SEC ingestion, CourtListener
sync, `research_note_service`, `watchlist_service`, `alert_synthesis_
service`, ...) to remember, and no drift risk. This project has zero
triggers anywhere — every side effect is explicit application code — and a
synced `search_document` table would have been the first exception.
Migration `0016` (live-applied, `alembic check` zero drift before and
after) adds `search_vector` to `issuer`, `security`, `alert_event`,
`court_docket`, `court_docket_entry`, `collection`, `research_note`; a
plain btree index on `court_docket.docket_number` (a human-readable
exact-match identifier that had no index before); and `pg_trgm` GIN
indexes narrowly on `issuer.legal_name`/`security.description` — not
indiscriminately on every text field, since only those two are
proper-noun/typo-prone lookups.

**A real bug was found and fixed before the first commit**: the original
`research_note` generation expression used `concat_ws` to join its six
case fields — Postgres declares `concat_ws` `STABLE`, not `IMMUTABLE` (it
accepts variadic `any` arguments, so its output could in principle depend
on session settings for non-text types), which `GENERATED ALWAYS AS ...
STORED` rejects even though every argument here was already `text`. The
live migration attempt failed with `generation expression is not
immutable`; Postgres DDL is transactional, so the failed `ALTER TABLE`
rolled back cleanly with zero partial state (`alembic current` stayed at
`0015`, confirmed live before retrying). Fixed with plain `||`
concatenation, which is immutable for `text`.

**Exact-match implementation (Tier 0)**: `search_exact_matches` runs
direct case-insensitive equality checks against `issuer.cik`/`ticker`/
`lei`, `security.cusip`/`isin`/`figi`, `court_docket.docket_number`, and
`sec_filing.accession_no` — all against already-existing (or, for
`docket_number`, newly-added) indexes. Always queried and returned
separately from the fuzzy tiers below; the API response keeps
`exact_matches` as its own top-level list, never blended into a single
score with `groups`.

**FTS implementation (Tier 2)**: `websearch_to_tsquery('english', q)` +
`ts_rank_cd` against each table's `search_vector`, with `setweight` tiers
per field (`issuer.legal_name`/`ticker` = A; `security.description` = A;
`alert_event.headline` = A, `.explanation` = B, `.category` = C;
`court_docket.case_name` = A, `.nature_of_suit` = C;
`court_docket_entry.description` = B; `collection.name` = A, `.description`
= C; `research_note.title` = A, case fields = C). `alert_event.category`
is stored snake_case (e.g. `"covenant_breach"`) — underscores are replaced
with spaces before tokenizing so a query for "covenant" matches it as a
separate word, live-verified with a dedicated test.

**Trigram/fuzzy implementation (Tier 3)**: `pg_trgm` `similarity()` against
`issuer.legal_name`/`security.description` only, and only invoked when
Tier 1 (prefix) + Tier 2 (FTS) together don't fill the requested limit —
never the primary ranking signal, purely typo tolerance.

**Ranking behavior**: group order is fixed and issuer-first
(`issuer, security, alert_event, court_docket, court_docket_entry,
collection, research_note, sec_filing`) — structural, not score-driven, so
`ts_rank_cd` values (which aren't meaningfully comparable across tables
with different `tsvector` configurations) are only ever compared *within*
one entity type's own results, never across types. Within `alert_event`
results, ties break on `as_of_date` descending; within `research_note`,
on `updated_at` descending — no new severity scale invented, and no
existing "new alert"/"new development" semantics touched or reinterpreted.

**API**: one endpoint, `GET /api/search?q=&limit=`, reused by both the
header typeahead (`limit=5`) and `/search` (`limit=10`) — deliberately no
pagination inside the endpoint itself; "see all results" reuses existing,
already-paginated destination pages (Credit Universe's own `q` filter for
issuer/security) where a real one exists, and simply shows nothing beyond
the bounded per-group limit where it doesn't (no dedicated free-text-
filterable list page exists for alerts/dockets/notes/collections today).

**`GlobalSearch`/header UX**: a debounced (300ms, matching the existing
`useDebouncedValue` convention) `TextField` in the `AppBar` on desktop,
opening a grouped dropdown (`Popper`) as the analyst types. Full keyboard
support: ArrowUp/ArrowDown move a highlighted index across a flattened
list of every visible result plus a trailing "See all results" entry,
Enter selects the highlighted item (or, with nothing highlighted, jumps to
`/search`), Escape closes the dropdown. `ClickAwayListener` closes on an
outside click. Selecting a result clears the input and navigates directly
to the entity's existing page — Universal Search adds no new detail pages
of its own.

**`/search` UX**: a full page (`SearchPage.tsx`) with its own search box
(URL-synced via `?q=`), an "Exact Matches" section when present, then one
`Paper` per entity-type group (larger, `limit=10`, results), each result
rendered as a clickable card (title, type-labeled exact-match chip where
relevant, snippet, context date). Loading/empty/error states match the
rest of the app's established pattern.

**Mobile behavior**: below the `useIsMobile` breakpoint, the header
renders a compact search icon button instead of an inline text field
(the AppBar has no room for a desktop-sized dropdown on a phone) — tapping
it opens a full-screen `Dialog` with the same debounced input and grouped
results list, plus an explicit close button. Verified via the same
`mockMobileViewport()` test convention already established in
`WatchlistDetailPage.test.tsx`/`Layout.test.tsx` (a live-browser window
resize did not reliably reflect in this environment's screenshot capture,
so mobile behavior was verified through the automated test suite, not a
live resized window).

**Court docket-entry behavior**: matches on `description` (the only real
free text a docket entry has — "DIP financing," "automatic stay,"
"confirmation hearing," etc., per the explicit requirement), always joined
back to its parent `court_docket` so the result carries the case name,
docket number, and `issuer_id` — clicking it navigates straight to that
issuer's Distress Timeline/"What happened in court?" section, never a
disconnected result. Live-verified: searching "confirmation hearing"
surfaced a real Diebold Nixdorf docket entry and correctly navigated to
the Diebold Nixdorf issuer page.

**SEC filing search limitations**: deliberately thin and stated as such in
code, not just this document — `sec_filing` has no stored content
anywhere in this schema (only accession number, form type, dates, a URL),
so the grouped/fuzzy tier matches only `form_type` (e.g. "10-K", "8-K").
It does **not** substring-match `accession_no` in that tier (a real,
live-caught precision issue: a bare numeric query like a 4-digit year was
incidentally matching inside unrelated 20-digit accession numbers before
this was tightened) — exact `accession_no` matching is Tier 0 only.

**Research Note behavior**: only the live `research_note` row is
searchable; `research_note_version` carries no `search_vector` column at
all. Live-verified with a dedicated test: editing a note's title makes the
*new* title searchable and the *old* title stop matching, proving search
reflects current content only, never a stale version snapshot. Historical
versions remain reachable exactly where Milestone 10A already built that
UI — the note's own Version History rail.

**Tests**: 24 new backend tests (5 unit for pure helpers; 14 integration
against the live `nexus` schema using deliberately distinctive
"Zylospan"-style fixture data rather than real production terms like
"Chapter 11," so assertions stay hermetic against tens of thousands of
real rows; 5 route-level `TestClient` tests, including one that locks in
the full excluded-entity-type set through a real HTTP response, not just
code inspection). 17 new frontend tests (8 `GlobalSearch`: debounce,
grouping, keyboard nav, Escape, no-results, mobile icon/dialog; 7
`SearchPage`: prompt/loading/error/empty states, exact-match rendering,
navigation targets, "see all" scoping; 2 `Layout` — updated for the now-
enabled Search nav item and to wrap in `QueryClientProvider`, which
`GlobalSearch`'s `useQuery` call now requires). 537/537 backend tests pass
total, 181/181 frontend tests pass total.

**Migration verification**: `alembic upgrade head` applied live against
the shared Supabase project (outside the 10 PM ET nightly-ingestion
window, per explicit instruction); `alembic check` confirms zero drift,
both immediately after the fixed migration and again after full 12A/12B
completion.

**Production walkthrough**: real backend + frontend booted; live-browser
verification of the desktop typeahead (grouped dropdown, ArrowDown +
Enter navigation), the full `/search` page (exact matches, multiple real
groups including "Research Universe" and "Research Note" for a "going
concern" query), exact-identifier lookup (CIK `0001519061` → Trinseo PLC,
tagged "Exact Matches"), and a court-docket-entry query ("confirmation
hearing") correctly navigating to the linked issuer. Regression spot-check
across Watchlists and Alerts confirmed both render unchanged.

**Regression verification**: none found — purely additive (one migration
adding nullable generated columns/indexes to seven existing tables, one
new repository/service/schema/route file, one new frontend component/page
plus `Layout.tsx`'s header). Nothing in the nightly scheduler, SEC/
CourtListener/OpenFIGI/FRED ingestion, AI routing, Morning Research Brief,
Watchlists, Alerts Center, Research Universes, Distress Timeline, or
Research Notes/versioning/audit behavior was touched.

**Anthropic application calls**: **0** — confirmed by design (no `app.ai`
import anywhere in the new/changed files) and by inspection of
`ai_call_log` (unchanged row count before/after). Universal Search
requires no LLM for normal queries, per the explicit constraint.

**Technical debt**: TD-003 resolved by this milestone (see Technical Debt
table). No new technical debt recorded — the two real bugs found during
implementation (`concat_ws` immutability, `accession_no` substring noise)
were fixed before commit, not deferred.

No ADR was written — PLAN.md §4.13 already explicitly deferred exactly
this implementation decision ("Decision deferred to implementation... §16
build order step 12") to this milestone; this is that decision being made,
not a new architectural decision.
