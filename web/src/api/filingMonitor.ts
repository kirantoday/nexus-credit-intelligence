import { apiFetch } from "./client";
import type { ProviderName } from "./creditUniverse";

// Mirrors backend/app/core/types.py exactly (PLAN.md section 24.3, 24.5).
export type EvidenceSeverity = "low" | "medium" | "high";
export type DetectionMethod = "deterministic" | "ai_assisted";
export type ReviewStatus = "unreviewed" | "confirmed" | "rejected";
export type AlertStatus = "new" | "acknowledged" | "dismissed";
export type FilingMonitorRunStatus =
  "running" | "success" | "completed_with_errors" | "failed" | "baseline_established";
export type FilingMonitorRunMode = "baseline" | "delta" | "backfill";

export type EvidenceType =
  | "bankruptcy_or_receivership"
  | "chapter_11"
  | "chapter_7"
  | "default_or_missed_payment"
  | "covenant_breach"
  | "debt_acceleration"
  | "going_concern"
  | "substantial_doubt"
  | "liquidity_warning"
  | "restructuring_advisor"
  | "restructuring_support_agreement"
  | "exchange_offer"
  | "liability_management_transaction"
  | "debt_amendment"
  | "maturity_extension"
  | "refinancing"
  | "dip_financing"
  | "emergency_financing"
  | "material_asset_sale"
  | "delisting_notice"
  | "workforce_reduction"
  | "facility_closure"
  | "material_impairment"
  | "auditor_resignation"
  | "adverse_audit_development"
  | "strategic_alternatives";

export interface FilingMonitorRunRow {
  id: string;
  started_at: string;
  completed_at: string | null;
  status: FilingMonitorRunStatus;
  mode: FilingMonitorRunMode;
  previous_watermark: string | null;
  resulting_watermark: string | null;
  issuers_checked: number;
  filings_discovered: number;
  filings_processed: number;
  alerts_created: number;
  errors_count: number;
  error_summary: string | null;
  backfill_lookback_days: number | null;
  is_backfill: boolean;
}

export interface FilingMonitorRunsPage {
  runs: FilingMonitorRunRow[];
}

export interface SecFilingRow {
  id: string;
  issuer_id: string;
  issuer_legal_name: string;
  accession_no: string;
  form_type: string;
  filing_date: string;
  period_of_report: string | null;
  is_amendment: boolean;
  primary_document_url: string | null;
}

export interface SecFilingsResponse {
  filings: SecFilingRow[];
  since_run_id: string | null;
}

export interface ResearchEvidenceRow {
  id: string;
  issuer_id: string;
  issuer_legal_name: string;
  evidence_provider: string;
  source_type: string;
  filing_id: string | null;
  evidence_type: EvidenceType;
  severity: EvidenceSeverity;
  source_section: string | null;
  source_item: string | null;
  matched_rule: string;
  evidence_excerpt: string;
  confidence: number | null;
  detection_method: DetectionMethod;
  review_status: ReviewStatus;
  created_at: string;
}

export interface ResearchEvidencePage {
  evidence: ResearchEvidenceRow[];
}

/**
 * One evidence-backed alert. `universe_names` is display-only context —
 * filtering by universe is a separate query parameter (`universe_id`), not
 * client-side filtering of this field.
 */
export interface AlertRow {
  id: string;
  issuer_id: string;
  issuer_legal_name: string;
  issuer_ticker: string | null;
  universe_names: string[];
  watchlist_names: string[];
  category: string;
  severity: EvidenceSeverity;
  headline: string;
  explanation: string;
  evidence_ids: string[];
  detection_method: DetectionMethod;
  ai_assisted: boolean;
  confidence: number | null;
  primary_evidence_provider: string;
  primary_source_label: string;
  primary_source_url: string | null;
  as_of_date: string;
  triggered_at: string;
  status: AlertStatus;
  acknowledged_at: string | null;
  acknowledged_by: string | null;
  dismissed_at: string | null;
  dismissed_by: string | null;
  dismissal_reason: string | null;
  is_backfill: boolean;
}

export interface AlertsPage {
  alerts: AlertRow[];
  total: number;
  page: number;
  page_size: number;
}

export interface AlertEvidenceDetail {
  alert: AlertRow;
  evidence: ResearchEvidenceRow[];
}

export interface SeverityCounts {
  high: number;
  medium: number;
  low: number;
}

/**
 * One "daily run" (PLAN.md Milestone 7.5.2) — pipeline-agnostic on purpose:
 * `pipeline` is operator/debugging context only, never a distinction the UI
 * asks the analyst to understand. Never represents a `mode=backfill` run —
 * those are structurally excluded server-side. `research_day` is the
 * real-world business day this run's data represents (business-day-cycle
 * correction) — never the wall-clock date the job happened to execute on.
 */
export interface DailyRunSummary {
  id: string;
  pipeline: string;
  mode: FilingMonitorRunMode;
  status: FilingMonitorRunStatus;
  started_at: string;
  completed_at: string | null;
  window_start_date: string | null;
  window_end_date: string | null;
  research_day: string;
  errors_count: number;
}

/** One Research Universe membership change for an issuer this period —
 * surfaced only because it is itself a material development (Milestone
 * 7.5.2 correction), never routine universe bookkeeping. */
export interface UniverseMembershipChange {
  universe_name: string;
  change_type: "added" | "upgraded";
  verification_status: "verified" | "partial" | "unverified";
}

/** One issuer's material developments this period — the brief's
 * fundamental display unit, not an individual alert. `alerts` is ranked
 * severity-first, most-recent-second. */
export interface IssuerDevelopment {
  issuer_id: string;
  issuer_legal_name: string;
  issuer_ticker: string | null;
  max_severity: EvidenceSeverity;
  alerts: AlertRow[];
  universe_changes: UniverseMembershipChange[];
}

/** Secondary, diagnostics-only pipeline-run detail (Milestone 7.5.2
 * correction) — everything the original 7.5.2 daily-run-boundary fix
 * computed, unchanged, just moved out of the analyst's primary view.
 * `since` is the pipeline run's own `started_at` boundary — raw
 * operational detail, distinct from the brief's primary
 * `latest_research_day` framing. */
export interface RunDetails {
  last_successful_run: DailyRunSummary | null;
  latest_run: DailyRunSummary | null;
  since: string | null;
  universes_monitored: number;
  issuers_monitored: number;
  new_sec_filings: number;
  new_court_events: number;
  new_research_evidence: number;
  failures_count: number;
}

/**
 * The Morning Research Brief (Milestone 7.5.2's business-day-cycle
 * correction): "What materially changed during the latest completed
 * business-day research cycle, compared with the preceding one?"
 * `latest_research_day`/`preceding_research_day` are derived purely from
 * canonical successful daily-run data plus calendar business-day
 * arithmetic — never from a page view, a request timestamp, or "now."
 * Opening, refreshing, or revisiting the brief can never change these
 * values; only a new successful daily/delta run completing can.
 * `research_cycle_is_fallback` is true only when no successful daily run
 * has ever completed at all.
 *
 * `new_developments`/`historical_intelligence` are a strict partition of
 * this cycle's alerts (triggered on or after the start of
 * `latest_research_day`, America/New_York) by `is_backfill` on each
 * underlying `AlertRow`: `new_developments` are genuinely new events (the
 * discovery run's own narrow window), `historical_intelligence` is an
 * older event Nexus just happened to discover this cycle (the enrichment
 * orchestrator's wider lookback). The same issuer can appear in both.
 * `severity_counts` covers `new_developments` only.
 */
export interface MorningBriefSummary {
  latest_research_day: string;
  preceding_research_day: string;
  research_cycle_is_fallback: boolean;
  as_of: string;
  issuers_with_developments: number;
  severity_counts: SeverityCounts;
  new_developments: IssuerDevelopment[];
  historical_intelligence: IssuerDevelopment[];
  historical_intelligence_issuer_count: number;
  no_material_changes: boolean;
  run_details: RunDetails;
}

/**
 * Alerts Center landing-page tiles (Milestone 9) — `alert.status` workflow
 * counts, deliberately distinct from the Morning Brief's research-cycle
 * counts (`SeverityCounts`, `issuers_with_developments`). "New" here means
 * "not yet acknowledged/dismissed," never "new in the latest research
 * cycle" — see `AlertsPage.tsx`'s explanatory copy for why both concepts
 * coexist without being merged.
 */
export interface AlertsSummary {
  new_count: number;
  high_severity_count: number;
  watchlist_alert_count: number;
  acknowledged_count: number;
}

/** One issuer-search match for the Alerts Center's issuer filter —
 * scoped server-side to issuers that actually have at least one alert. */
export interface AlertIssuerSearchResult {
  issuer_id: string;
  issuer_legal_name: string;
  issuer_ticker: string | null;
}

export interface AlertIssuerSearchResponse {
  issuers: AlertIssuerSearchResult[];
}

export interface AlertsQuery {
  issuerId?: string;
  universeId?: string;
  watchlistId?: string;
  severity?: EvidenceSeverity;
  category?: string;
  evidenceProvider?: ProviderName | string;
  status?: AlertStatus;
  detectionMethod?: DetectionMethod;
  dateFrom?: string;
  dateTo?: string;
  triggeredSince?: string;
  page?: number;
  pageSize?: number;
}

export async function fetchMorningBrief(): Promise<MorningBriefSummary> {
  return apiFetch<MorningBriefSummary>("/api/morning-brief");
}

export async function fetchAlerts(query: AlertsQuery): Promise<AlertsPage> {
  const params = new URLSearchParams();
  if (query.issuerId) params.set("issuer_id", query.issuerId);
  if (query.universeId) params.set("universe_id", query.universeId);
  if (query.watchlistId) params.set("watchlist_id", query.watchlistId);
  if (query.severity) params.set("severity", query.severity);
  if (query.category) params.set("category", query.category);
  if (query.evidenceProvider) params.set("evidence_provider", query.evidenceProvider);
  if (query.status) params.set("status", query.status);
  if (query.detectionMethod) params.set("detection_method", query.detectionMethod);
  if (query.dateFrom) params.set("date_from", query.dateFrom);
  if (query.dateTo) params.set("date_to", query.dateTo);
  if (query.triggeredSince) params.set("triggered_since", query.triggeredSince);
  params.set("page", String(query.page ?? 1));
  params.set("page_size", String(query.pageSize ?? 50));
  return apiFetch<AlertsPage>(`/api/alerts?${params.toString()}`);
}

export async function fetchAlertsSummary(): Promise<AlertsSummary> {
  return apiFetch<AlertsSummary>("/api/alerts/summary");
}

export async function searchAlertIssuers(q: string): Promise<AlertIssuerSearchResponse> {
  return apiFetch<AlertIssuerSearchResponse>(`/api/alerts/issuers?q=${encodeURIComponent(q)}`);
}

export async function fetchAlertEvidence(alertId: string): Promise<AlertEvidenceDetail> {
  return apiFetch<AlertEvidenceDetail>(`/api/alerts/${alertId}/evidence`);
}

export async function acknowledgeAlert(alertId: string, actedBy?: string): Promise<AlertRow> {
  return apiFetch<AlertRow>(`/api/alerts/${alertId}/acknowledge`, {
    method: "POST",
    body: JSON.stringify({ acted_by: actedBy ?? null }),
  });
}

export async function dismissAlert(
  alertId: string,
  reason?: string,
  actedBy?: string,
): Promise<AlertRow> {
  return apiFetch<AlertRow>(`/api/alerts/${alertId}/dismiss`, {
    method: "POST",
    body: JSON.stringify({ acted_by: actedBy ?? null, reason: reason ?? null }),
  });
}

export async function fetchFilingMonitorRuns(): Promise<FilingMonitorRunsPage> {
  return apiFetch<FilingMonitorRunsPage>("/api/filing-monitor/runs");
}
