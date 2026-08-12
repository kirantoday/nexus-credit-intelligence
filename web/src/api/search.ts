import { apiFetch } from "./client";

/**
 * Universal Search (PLAN.md 4.13, 8; Milestone 12A). Deliberately excludes
 * research_evidence, research_note_version, audit_event, docket_document,
 * and all of 10B — see backend/app/repositories/search_repository.py's
 * module docstring for the full rationale.
 */
export type SearchEntityType =
  | "issuer"
  | "security"
  | "alert_event"
  | "court_docket"
  | "court_docket_entry"
  | "collection"
  | "research_note"
  | "sec_filing";

export interface SearchResultItem {
  entity_type: SearchEntityType;
  entity_id: string;
  title: string;
  snippet: string | null;
  issuer_id: string | null;
  collection_type: string | null;
  context_date: string | null;
  matched_field: string | null;
}

export interface SearchResultGroup {
  entity_type: SearchEntityType;
  results: SearchResultItem[];
}

export interface SearchResponse {
  query: string;
  exact_matches: SearchResultItem[];
  groups: SearchResultGroup[];
}

export async function fetchSearch(q: string, limit = 5): Promise<SearchResponse> {
  const params = new URLSearchParams({ q, limit: String(limit) });
  return apiFetch<SearchResponse>(`/api/search?${params.toString()}`);
}
