import { apiFetch, apiUpload } from "./client";
import type { AccessClassification } from "./researchNote";

export type { AccessClassification };

/**
 * A manually-uploaded PDF research artifact associated with an issuer
 * (PLAN.md 4.10; Milestone 10B —
 * backend/app/schemas/research_document.py). Distinct from a Research
 * Note: a document is an uploaded original file with provenance, not
 * analyst-authored text.
 */
export type ResearchDocumentType =
  | "credit_agreement"
  | "amendment"
  | "earnings_presentation"
  | "investor_presentation"
  | "restructuring_presentation"
  | "lender_presentation"
  | "bankruptcy_court_document"
  | "financial_model_analysis"
  | "internal_research_memo"
  | "other";

export type OriginalSource = "pacer" | "courtlistener" | "issuer_site" | "other";

export interface ResearchDocument {
  id: string;
  issuer_id: string;
  security_id: string | null;
  document_type: ResearchDocumentType;
  title: string;
  description: string | null;
  original_filename: string;
  document_date: string | null;
  confidentiality_classification: AccessClassification;
  uploaded_by: string | null;
  is_archived: boolean;
  archived_at: string | null;
  archived_by: string | null;
  created_at: string;
  updated_at: string;
}

/** A `ResearchDocument` plus issuer display fields — `GET
 * /api/research-documents`'s list response includes these, backing both
 * Issuer Detail's issuer-scoped section and the global workspace. */
export interface ResearchDocumentSummary extends ResearchDocument {
  issuer_legal_name: string;
  issuer_ticker: string | null;
}

export interface ResearchDocumentListResponse {
  documents: ResearchDocumentSummary[];
}

export interface ResearchDocumentDownloadResponse {
  signed_url: string;
  expires_in_seconds: number;
  original_filename: string;
}

export interface ResearchDocumentUploadInput {
  issuer_id: string;
  security_id?: string | null;
  document_type: ResearchDocumentType;
  title: string;
  description?: string | null;
  document_date?: string | null;
  confidentiality_classification?: AccessClassification;
  uploaded_by?: string | null;
  original_source?: OriginalSource;
  file: File;
}

export interface ResearchDocumentMetadataUpdateInput {
  title?: string;
  description?: string | null;
  document_type?: ResearchDocumentType;
  document_date?: string | null;
  confidentiality_classification?: AccessClassification;
  edited_by?: string | null;
}

/** `issuerId` omitted fetches across every issuer (the global Research
 * Documents workspace); passing a real issuer id scopes to Issuer Detail's
 * own Research Documents section. */
export async function fetchResearchDocuments(
  issuerId?: string,
  documentType?: ResearchDocumentType,
  includeArchived = false,
): Promise<ResearchDocumentListResponse> {
  const params = new URLSearchParams();
  if (issuerId) params.set("issuer_id", issuerId);
  if (documentType) params.set("document_type", documentType);
  if (includeArchived) params.set("include_archived", "true");
  const query = params.toString();
  return apiFetch<ResearchDocumentListResponse>(
    `/api/research-documents${query ? `?${query}` : ""}`,
  );
}

export async function fetchResearchDocument(documentId: string): Promise<ResearchDocument> {
  return apiFetch<ResearchDocument>(`/api/research-documents/${documentId}`);
}

export async function uploadResearchDocument(
  input: ResearchDocumentUploadInput,
): Promise<ResearchDocument> {
  const formData = new FormData();
  formData.set("issuer_id", input.issuer_id);
  if (input.security_id) formData.set("security_id", input.security_id);
  formData.set("document_type", input.document_type);
  formData.set("title", input.title);
  if (input.description) formData.set("description", input.description);
  if (input.document_date) formData.set("document_date", input.document_date);
  if (input.confidentiality_classification) {
    formData.set("confidentiality_classification", input.confidentiality_classification);
  }
  if (input.uploaded_by) formData.set("uploaded_by", input.uploaded_by);
  if (input.original_source) formData.set("original_source", input.original_source);
  formData.set("file", input.file);
  return apiUpload<ResearchDocument>("/api/research-documents", formData);
}

/** Mints a fresh, short-lived signed URL on every call — never cached.
 * `forceDownload=false` (default) opens the PDF inline in a new tab;
 * `true` forces a Save-As with the document's original filename. */
export async function fetchResearchDocumentDownloadUrl(
  documentId: string,
  forceDownload = false,
): Promise<ResearchDocumentDownloadResponse> {
  const query = forceDownload ? "?download=true" : "";
  return apiFetch<ResearchDocumentDownloadResponse>(
    `/api/research-documents/${documentId}/download${query}`,
  );
}

export async function updateResearchDocumentMetadata(
  documentId: string,
  input: ResearchDocumentMetadataUpdateInput,
): Promise<ResearchDocument> {
  return apiFetch<ResearchDocument>(`/api/research-documents/${documentId}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}

export async function archiveResearchDocument(
  documentId: string,
  archivedBy?: string | null,
): Promise<ResearchDocument> {
  return apiFetch<ResearchDocument>(`/api/research-documents/${documentId}/archive`, {
    method: "POST",
    body: JSON.stringify({ archived_by: archivedBy ?? null }),
  });
}
