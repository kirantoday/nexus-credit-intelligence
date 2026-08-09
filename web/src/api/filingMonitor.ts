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
 * those are structurally excluded server-side.
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
  errors_count: number;
}

/** Backs the Morning Research Brief page's summary bar — provider-aware
 * (Milestone 7.5): "new filings discovered" alone was SEC-specific and
 * insufficient once CourtListener (and market-wide SEC discovery) exist as
 * independent evidence sources, so it's broken out per provider/category.
 * `since` (Milestone 7.5.2) is the exact boundary every "new_*"/actionable
 * count below was computed against — pass it as `triggeredSince` to
 * `fetchAlerts` so the alert list below the summary bar is scoped to the
 * identical boundary, never a broader, all-time one. */
export interface MorningBriefSummary {
  last_successful_run: DailyRunSummary | null;
  latest_run: DailyRunSummary | null;
  since: string | null;
  universes_monitored: number;
  issuers_monitored: number;
  new_sec_filings: number;
  new_court_events: number;
  new_research_evidence: number;
  actionable_alerts_total: number;
  alerts_by_severity: SeverityCounts;
  deterministic_alert_count: number;
  ai_assisted_alert_count: number;
  failures_count: number;
  no_new_alerts: boolean;
}

export interface AlertsQuery {
  issuerId?: string;
  universeId?: string;
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
