import { apiFetch } from "./client";

/**
 * Universal Search (PLAN.md 4.13, 8; Milestone 12A, extended by Milestone
 * 10B-5 for research_document). Deliberately excludes research_evidence,
 * research_note_version, audit_event, and docket_document — see
 * backend/app/repositories/search_repository.py's module docstring for the
 * full rationale. `research_document` search is title/metadata only — no
 * PDF content search exists.
 */
export type SearchEntityType =
  | "issuer"
  | "security"
  | "alert_event"
  | "court_docket"
  | "court_docket_entry"
  | "collection"
  | "research_note"
  | "research_document"
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
