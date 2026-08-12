import { apiFetch } from "./client";

/**
 * A dated, versioned investment thesis an analyst records against an
 * issuer/security (PLAN.md 4.10; Milestone 10A —
 * backend/app/schemas/research.py). Structured sections (bull/base/bear
 * case, catalysts, risks, invalidation conditions) are the note's content —
 * there is no separate free-text body.
 */
export type ThesisStatus = "draft" | "active" | "monitoring" | "invalidated" | "resolved";
export type Conviction = "low" | "medium" | "high";
export type AccessClassification = "standard" | "restricted";

export interface EvidenceRef {
  entity_table: string;
  entity_id: string;
  label: string | null;
}

export interface ResearchNote {
  id: string;
  issuer_id: string;
  security_id: string | null;
  title: string;
  thesis_status: ThesisStatus;
  conviction: Conviction | null;
  bull_case: string | null;
  base_case: string | null;
  bear_case: string | null;
  catalysts: string | null;
  risks: string | null;
  invalidation_conditions: string | null;
  evidence_refs: EvidenceRef[] | null;
  access_classification: AccessClassification;
  author_user_id: string | null;
  is_demo: boolean;
  current_version_number: number;
  is_archived: boolean;
  archived_at: string | null;
  archived_by: string | null;
  created_at: string;
  updated_at: string;
}

/** A `ResearchNote` plus issuer display fields — only `GET
 * /api/research-notes`'s list response includes these (Research Notes
 * workspace, cross-issuer listing follow-up to Milestone 10A). The
 * single-note fetch/create/update/archive calls keep returning a plain
 * `ResearchNote`. */
export interface ResearchNoteSummary extends ResearchNote {
  issuer_legal_name: string;
  issuer_ticker: string | null;
}

export interface ResearchNoteListResponse {
  notes: ResearchNoteSummary[];
}

export interface ResearchNoteVersion {
  id: string;
  research_note_id: string;
  version_number: number;
  title: string;
  thesis_status: ThesisStatus;
  conviction: Conviction | null;
  bull_case: string | null;
  base_case: string | null;
  bear_case: string | null;
  catalysts: string | null;
  risks: string | null;
  invalidation_conditions: string | null;
  evidence_refs: EvidenceRef[] | null;
  access_classification: AccessClassification;
  edited_by: string | null;
  edited_at: string;
}

export interface ResearchNoteVersionListResponse {
  versions: ResearchNoteVersion[];
}

export interface AuditEvent {
  id: string;
  user_id: string | null;
  event_type: string;
  entity_table: string;
  entity_id: string | null;
  before_state: Record<string, unknown> | null;
  after_state: Record<string, unknown> | null;
  occurred_at: string;
}

export interface AuditEventListResponse {
  events: AuditEvent[];
}

export interface ResearchNoteFieldsInput {
  title?: string;
  thesis_status?: ThesisStatus;
  conviction?: Conviction | null;
  bull_case?: string | null;
  base_case?: string | null;
  bear_case?: string | null;
  catalysts?: string | null;
  risks?: string | null;
  invalidation_conditions?: string | null;
  evidence_refs?: EvidenceRef[] | null;
  access_classification?: AccessClassification;
}

export interface ResearchNoteCreateInput extends ResearchNoteFieldsInput {
  issuer_id: string;
  security_id?: string | null;
  title: string;
  author_user_id?: string | null;
  is_demo?: boolean;
}

export interface ResearchNoteUpdateInput extends ResearchNoteFieldsInput {
  edited_by?: string | null;
}

/** `issuerId` omitted fetches across every issuer (Research Notes
 * workspace) — passing a real issuer id behaves exactly as before
 * (Issuer Detail's own "Analyst Research Notes" section). */
export async function fetchResearchNotes(
  issuerId?: string,
  includeArchived = false,
): Promise<ResearchNoteListResponse> {
  const params = new URLSearchParams();
  if (issuerId) params.set("issuer_id", issuerId);
  if (includeArchived) params.set("include_archived", "true");
  const query = params.toString();
  return apiFetch<ResearchNoteListResponse>(`/api/research-notes${query ? `?${query}` : ""}`);
}

export async function fetchResearchNote(noteId: string): Promise<ResearchNote> {
  return apiFetch<ResearchNote>(`/api/research-notes/${noteId}`);
}

export async function createResearchNote(input: ResearchNoteCreateInput): Promise<ResearchNote> {
  return apiFetch<ResearchNote>("/api/research-notes", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function updateResearchNote(
  noteId: string,
  input: ResearchNoteUpdateInput,
): Promise<ResearchNote> {
  return apiFetch<ResearchNote>(`/api/research-notes/${noteId}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}

export async function archiveResearchNote(
  noteId: string,
  archivedBy?: string | null,
): Promise<ResearchNote> {
  return apiFetch<ResearchNote>(`/api/research-notes/${noteId}/archive`, {
    method: "POST",
    body: JSON.stringify({ archived_by: archivedBy ?? null }),
  });
}

export async function fetchResearchNoteVersions(
  noteId: string,
): Promise<ResearchNoteVersionListResponse> {
  return apiFetch<ResearchNoteVersionListResponse>(`/api/research-notes/${noteId}/versions`);
}

export async function fetchResearchNoteVersion(
  noteId: string,
  versionNumber: number,
): Promise<ResearchNoteVersion> {
  return apiFetch<ResearchNoteVersion>(`/api/research-notes/${noteId}/versions/${versionNumber}`);
}

export async function fetchResearchNoteAuditEvents(
  noteId: string,
): Promise<AuditEventListResponse> {
  return apiFetch<AuditEventListResponse>(`/api/research-notes/${noteId}/audit-events`);
}
