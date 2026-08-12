import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  archiveResearchNote,
  createResearchNote,
  fetchResearchNote,
  fetchResearchNoteAuditEvents,
  fetchResearchNotes,
  fetchResearchNoteVersion,
  fetchResearchNoteVersions,
  updateResearchNote,
  type ResearchNoteCreateInput,
  type ResearchNoteUpdateInput,
} from "../api/researchNote";

export function useResearchNotes(issuerId: string | undefined, includeArchived = false) {
  return useQuery({
    queryKey: ["research-notes", issuerId, includeArchived],
    queryFn: () => fetchResearchNotes(issuerId as string, includeArchived),
    enabled: issuerId !== undefined,
  });
}

/** Cross-issuer listing for the Research Notes workspace page —
 * `useResearchNotes` above is unchanged and still backs Issuer Detail's
 * own issuer-scoped notes section. */
export function useAllResearchNotes(includeArchived = false) {
  return useQuery({
    queryKey: ["research-notes", "all", includeArchived],
    queryFn: () => fetchResearchNotes(undefined, includeArchived),
  });
}

export function useResearchNote(noteId: string | undefined) {
  return useQuery({
    queryKey: ["research-note", noteId],
    queryFn: () => fetchResearchNote(noteId as string),
    enabled: noteId !== undefined,
  });
}

export function useResearchNoteVersions(noteId: string | undefined) {
  return useQuery({
    queryKey: ["research-note-versions", noteId],
    queryFn: () => fetchResearchNoteVersions(noteId as string),
    enabled: noteId !== undefined,
  });
}

export function useResearchNoteVersion(
  noteId: string | undefined,
  versionNumber: number | undefined,
) {
  return useQuery({
    queryKey: ["research-note-version", noteId, versionNumber],
    queryFn: () => fetchResearchNoteVersion(noteId as string, versionNumber as number),
    enabled: noteId !== undefined && versionNumber !== undefined,
  });
}

export function useResearchNoteAuditEvents(noteId: string | undefined) {
  return useQuery({
    queryKey: ["research-note-audit-events", noteId],
    queryFn: () => fetchResearchNoteAuditEvents(noteId as string),
    enabled: noteId !== undefined,
  });
}

function invalidateNote(queryClient: ReturnType<typeof useQueryClient>, noteId?: string): void {
  void queryClient.invalidateQueries({ queryKey: ["research-notes"] });
  if (noteId) {
    void queryClient.invalidateQueries({ queryKey: ["research-note", noteId] });
    void queryClient.invalidateQueries({ queryKey: ["research-note-versions", noteId] });
    void queryClient.invalidateQueries({ queryKey: ["research-note-audit-events", noteId] });
  }
}

export function useCreateResearchNote() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: ResearchNoteCreateInput) => createResearchNote(input),
    onSuccess: () => invalidateNote(queryClient),
  });
}

export function useUpdateResearchNote() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ noteId, ...input }: { noteId: string } & ResearchNoteUpdateInput) =>
      updateResearchNote(noteId, input),
    onSuccess: (_data, variables) => invalidateNote(queryClient, variables.noteId),
  });
}

export function useArchiveResearchNote() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ noteId, archivedBy }: { noteId: string; archivedBy?: string | null }) =>
      archiveResearchNote(noteId, archivedBy),
    onSuccess: (_data, variables) => invalidateNote(queryClient, variables.noteId),
  });
}
