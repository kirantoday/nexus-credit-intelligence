import { apiFetch } from "./client";
import type { EvidenceSeverity } from "./filingMonitor";

/**
 * One Watchlist — a `collection` row with `collection_type=watchlist`
 * (ADR-016; backend/app/schemas/watchlist.py). Shares its underlying table
 * with Research Universes but is a distinct product concept: an analyst's
 * personal "which issuers do I care about" list.
 */
export interface WatchlistSummary {
  id: string;
  slug: string;
  name: string;
  description: string;
  issuer_count: number;
  issuers_with_new_developments: number;
  high_severity_count: number;
  last_activity_at: string | null;
  created_at: string;
  updated_at: string;
  /** Only populated when the request supplied `issuerId` (see `fetchWatchlists`). */
  contains_issuer: boolean | null;
}

export interface WatchlistListResponse {
  watchlists: WatchlistSummary[];
}

/** One watched issuer, with latest-development context — entirely assembled
 * from already-persisted alerts/memberships/securities, never new
 * intelligence the Watchlist itself creates. */
export interface WatchlistIssuerRow {
  issuer_id: string;
  issuer_legal_name: string;
  issuer_ticker: string | null;
  current_status: string[];
  latest_development_headline: string | null;
  latest_development_date: string | null;
  severity: EvidenceSeverity | null;
  new_developments_count: number;
  securities_count: number;
  rationale: string;
  added_at: string;
}

export interface WatchlistDetailResponse {
  watchlist: WatchlistSummary;
  issuers: WatchlistIssuerRow[];
}

export async function fetchWatchlists(issuerId?: string): Promise<WatchlistListResponse> {
  const params = new URLSearchParams();
  if (issuerId) params.set("issuer_id", issuerId);
  const query = params.toString();
  return apiFetch<WatchlistListResponse>(`/api/watchlists${query ? `?${query}` : ""}`);
}

export async function fetchWatchlist(watchlistId: string): Promise<WatchlistDetailResponse> {
  return apiFetch<WatchlistDetailResponse>(`/api/watchlists/${watchlistId}`);
}

export async function createWatchlist(input: {
  name: string;
  description?: string;
}): Promise<WatchlistSummary> {
  return apiFetch<WatchlistSummary>("/api/watchlists", {
    method: "POST",
    body: JSON.stringify({ name: input.name, description: input.description ?? "" }),
  });
}

export async function updateWatchlist(
  watchlistId: string,
  input: { name?: string; description?: string },
): Promise<WatchlistSummary> {
  return apiFetch<WatchlistSummary>(`/api/watchlists/${watchlistId}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}

export async function deleteWatchlist(watchlistId: string): Promise<void> {
  await apiFetch<void>(`/api/watchlists/${watchlistId}`, { method: "DELETE" });
}

export async function addIssuerToWatchlist(
  watchlistId: string,
  input: { issuer_id: string; rationale?: string },
): Promise<WatchlistSummary> {
  return apiFetch<WatchlistSummary>(`/api/watchlists/${watchlistId}/issuers`, {
    method: "POST",
    body: JSON.stringify({
      issuer_id: input.issuer_id,
      rationale: input.rationale ?? "Added to watchlist",
    }),
  });
}

export async function removeIssuerFromWatchlist(
  watchlistId: string,
  issuerId: string,
): Promise<void> {
  await apiFetch<void>(`/api/watchlists/${watchlistId}/issuers/${issuerId}`, {
    method: "DELETE",
  });
}
