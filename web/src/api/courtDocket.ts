import { apiFetch } from "./client";

// Mirrors backend/app/core/types.py's DocketDocumentAvailability exactly
// (PLAN.md sections 4.5, 15).
export type DocketDocumentAvailability =
  "recap_available" | "unavailable_admin_upload_needed" | "admin_uploaded";

export interface DocketDocumentRow {
  id: string;
  availability: DocketDocumentAvailability;
  description: string | null;
  page_count: number | null;
  is_sealed: boolean;
  recap_document_url: string | null;
}

export interface CourtDocketEntryRow {
  id: string;
  entry_number: number | null;
  entry_date: string | null;
  description: string;
  document_available: boolean;
  documents: DocketDocumentRow[];
}

/** One real, live-verified CourtListener docket (backend/app/schemas/court_docket.py). */
export interface CourtDocketRow {
  id: string;
  issuer_id: string | null;
  issuer_legal_name: string | null;
  courtlistener_docket_id: number;
  court: string;
  docket_number: string;
  case_name: string;
  nature_of_suit: string | null;
  chapter: string | null;
  date_filed: string | null;
  courtlistener_url: string;
  entry_count: number;
  created_at: string;
}

export interface CourtDocketDetail {
  docket: CourtDocketRow;
  entries: CourtDocketEntryRow[];
}

export interface CourtDocketsResponse {
  dockets: CourtDocketRow[];
}

export async function fetchCourtDockets(issuerId?: string): Promise<CourtDocketsResponse> {
  const params = new URLSearchParams();
  if (issuerId) params.set("issuer_id", issuerId);
  const query = params.toString();
  return apiFetch<CourtDocketsResponse>(`/api/court-dockets${query ? `?${query}` : ""}`);
}

export async function fetchCourtDocketDetail(docketId: string): Promise<CourtDocketDetail> {
  return apiFetch<CourtDocketDetail>(`/api/court-dockets/${docketId}`);
}
