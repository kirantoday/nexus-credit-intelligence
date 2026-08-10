import { apiFetch } from "./client";

/**
 * One collapsed narrative milestone (backend/app/schemas/issuer_timeline.py).
 * `event_type` is the underlying evidence/alert category (e.g. "chapter_11")
 * — free text, since the allowed set grows via an ordinary migration
 * (ADR-018), never a fixed frontend union.
 */
export interface TimelineSource {
  provider: string;
  label: string;
  url: string | null;
}

export type TimelineSeverity = "low" | "medium" | "high";

export interface TimelineEvent {
  event_date: string;
  event_type: string;
  title: string;
  short_summary: string;
  why_it_matters: string;
  severity: TimelineSeverity;
  confidence: number | null;
  primary_source: TimelineSource;
  supporting_sources: TimelineSource[];
  is_historical_discovery: boolean;
  evidence_count: number;
}

export interface IssuerTimeline {
  issuer_id: string;
  events: TimelineEvent[];
  total_events: number;
  date_range_start: string | null;
  date_range_end: string | null;
  current_status: string[];
  most_recent_event_title: string | null;
}

export async function fetchIssuerTimeline(issuerId: string): Promise<IssuerTimeline> {
  return apiFetch<IssuerTimeline>(`/api/issuers/${issuerId}/timeline`);
}
