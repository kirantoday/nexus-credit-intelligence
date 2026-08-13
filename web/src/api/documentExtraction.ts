import { apiFetch } from "./client";

/**
 * Document Intelligence — extraction/chunking over an uploaded Research
 * Document (Milestone 10C — backend/app/schemas/document_extraction.py).
 * `document_extraction` is one immutable attempt; `is_current` marks the
 * single attempt whose chunks represent the document's corpus today.
 */
export type DocumentExtractionStatus =
  "pending" | "processing" | "completed" | "failed" | "needs_ocr";

export interface DocumentExtraction {
  id: string;
  research_document_id: string | null;
  status: DocumentExtractionStatus;
  extractor_provider: string | null;
  extractor_version: string | null;
  chunking_strategy_version: string | null;
  page_count: number | null;
  chunk_count: number | null;
  table_count: number | null;
  attempt_count: number;
  error_classification: string | null;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  is_current: boolean;
}

export interface DocumentExtractionListResponse {
  extractions: DocumentExtraction[];
}

export type DocumentChunkElementType = "text" | "heading" | "table" | "list";

export interface DocumentChunk {
  id: string;
  document_extraction_id: string;
  research_document_id: string;
  issuer_id: string;
  chunk_index: number;
  element_type: DocumentChunkElementType;
  content: string;
  content_type: string;
  page_start: number | null;
  page_end: number | null;
  section_path: string | null;
  section_title: string | null;
  token_count: number | null;
  confidentiality_classification: "standard" | "restricted";
  created_at: string;
}

export interface DocumentChunkListResponse {
  chunks: DocumentChunk[];
}

/** Enqueues a new extraction attempt — returns immediately with a
 * `pending` row; the actual extraction runs in the standalone worker,
 * never inline in this request. */
export async function processDocument(
  documentId: string,
  requestedBy?: string | null,
): Promise<DocumentExtraction> {
  return apiFetch<DocumentExtraction>(`/api/research-documents/${documentId}/process`, {
    method: "POST",
    body: JSON.stringify({ requested_by: requestedBy ?? null }),
  });
}

export async function fetchExtractions(
  documentId: string,
): Promise<DocumentExtractionListResponse> {
  return apiFetch<DocumentExtractionListResponse>(
    `/api/research-documents/${documentId}/extractions`,
  );
}

/** 404s (via `ApiError`) when no extraction has ever completed for this
 * document — callers treat that as "Not processed," not an error state. */
export async function fetchCurrentExtraction(documentId: string): Promise<DocumentExtraction> {
  return apiFetch<DocumentExtraction>(`/api/research-documents/${documentId}/extractions/current`);
}

export async function fetchExtraction(extractionId: string): Promise<DocumentExtraction> {
  return apiFetch<DocumentExtraction>(`/api/document-extractions/${extractionId}`);
}

export async function fetchChunks(extractionId: string): Promise<DocumentChunkListResponse> {
  return apiFetch<DocumentChunkListResponse>(`/api/document-extractions/${extractionId}/chunks`);
}

/** Internal lexical inspection search — `search_document_chunks`
 * (Milestone 10C), scoped to one extraction. Not Universal Search. */
export async function searchChunks(
  extractionId: string,
  query: string,
): Promise<DocumentChunkListResponse> {
  return apiFetch<DocumentChunkListResponse>(
    `/api/document-extractions/${extractionId}/chunks/search?q=${encodeURIComponent(query)}`,
  );
}
