import { apiFetch } from "./client";

// Mirrors backend/app/core/types.py exactly (PLAN.md section 24.1).
export type CollectionType = "research_universe" | "watchlist" | "benchmark";
export type CollectionScope = "organization" | "personal" | "team";
export type CollectionVisibility = "public" | "private" | "team";
export type CurationMethod = "manual_curated" | "system_seeded" | "user_created";
export type VerificationStatus = "verified" | "partial" | "unverified";
export type CollectionPriority = "critical" | "high" | "medium" | "low";

/**
 * One Research Universe / Watchlist / Benchmark collection
 * (backend/app/schemas/research_universe.py).
 */
export interface ResearchUniverseSummary {
  id: string;
  slug: string;
  name: string;
  description: string;
  collection_type: CollectionType;
  scope: CollectionScope;
  visibility: CollectionVisibility;
  curation_method: CurationMethod;
  verification_status: VerificationStatus;
  last_verified_at: string | null;
  priority: CollectionPriority | null;
  issuer_count: number;
}

export interface ResearchUniverseListResponse {
  universes: ResearchUniverseSummary[];
}

/**
 * One issuer's membership in one collection. Never asserts current status
 * — `rationale` + `rationale_as_of_date` are dated text a human wrote/
 * verified (PLAN.md 24.1).
 */
export interface ResearchUniverseMembershipRow {
  issuer_id: string;
  issuer_legal_name: string;
  issuer_ticker: string | null;
  rationale: string;
  rationale_as_of_date: string | null;
  verification_status: VerificationStatus;
  added_at: string;
  system_seeded: boolean;
}

export interface ResearchUniverseIssuersResponse {
  universe: ResearchUniverseSummary;
  issuers: ResearchUniverseMembershipRow[];
}

/** A universe an issuer belongs to — shown on Issuer Detail. */
export interface IssuerUniverseMembership {
  collection_id: string;
  slug: string;
  name: string;
  collection_type: CollectionType;
  rationale: string;
  rationale_as_of_date: string | null;
}

export async function fetchResearchUniverses(
  collectionType?: CollectionType,
): Promise<ResearchUniverseListResponse> {
  const params = new URLSearchParams();
  if (collectionType) params.set("collection_type", collectionType);
  const query = params.toString();
  return apiFetch<ResearchUniverseListResponse>(
    `/api/research-universes${query ? `?${query}` : ""}`,
  );
}

export async function fetchResearchUniverse(universeId: string): Promise<ResearchUniverseSummary> {
  return apiFetch<ResearchUniverseSummary>(`/api/research-universes/${universeId}`);
}

export async function fetchResearchUniverseIssuers(
  universeId: string,
): Promise<ResearchUniverseIssuersResponse> {
  return apiFetch<ResearchUniverseIssuersResponse>(`/api/research-universes/${universeId}/issuers`);
}
