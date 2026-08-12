import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  archiveResearchDocument,
  fetchResearchDocument,
  fetchResearchDocumentDownloadUrl,
  fetchResearchDocuments,
  updateResearchDocumentMetadata,
  uploadResearchDocument,
  type ResearchDocumentMetadataUpdateInput,
  type ResearchDocumentType,
  type ResearchDocumentUploadInput,
} from "../api/researchDocument";

export function useResearchDocuments(
  issuerId: string | undefined,
  documentType?: ResearchDocumentType,
  includeArchived = false,
) {
  return useQuery({
    queryKey: ["research-documents", issuerId, documentType, includeArchived],
    queryFn: () => fetchResearchDocuments(issuerId as string, documentType, includeArchived),
    enabled: issuerId !== undefined,
  });
}

/** Cross-issuer listing for the global Research Documents workspace —
 * `useResearchDocuments` above is unchanged and still backs Issuer Detail's
 * own issuer-scoped section. */
export function useAllResearchDocuments(
  documentType?: ResearchDocumentType,
  includeArchived = false,
) {
  return useQuery({
    queryKey: ["research-documents", "all", documentType, includeArchived],
    queryFn: () => fetchResearchDocuments(undefined, documentType, includeArchived),
  });
}

export function useResearchDocument(documentId: string | undefined) {
  return useQuery({
    queryKey: ["research-document", documentId],
    queryFn: () => fetchResearchDocument(documentId as string),
    enabled: documentId !== undefined,
  });
}

/** Not cached by TanStack Query (no `useQuery`) — a signed URL is short-
 * lived and must be minted fresh at the moment of use (view/download
 * click), never reused from a stale cache entry. */
export function useResearchDocumentDownloadUrl() {
  return useMutation({
    mutationFn: ({ documentId, forceDownload }: { documentId: string; forceDownload?: boolean }) =>
      fetchResearchDocumentDownloadUrl(documentId, forceDownload),
  });
}

function invalidateDocument(
  queryClient: ReturnType<typeof useQueryClient>,
  documentId?: string,
): void {
  void queryClient.invalidateQueries({ queryKey: ["research-documents"] });
  if (documentId) {
    void queryClient.invalidateQueries({ queryKey: ["research-document", documentId] });
  }
}

export function useUploadResearchDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: ResearchDocumentUploadInput) => uploadResearchDocument(input),
    onSuccess: () => invalidateDocument(queryClient),
  });
}

export function useUpdateResearchDocumentMetadata() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      documentId,
      ...input
    }: { documentId: string } & ResearchDocumentMetadataUpdateInput) =>
      updateResearchDocumentMetadata(documentId, input),
    onSuccess: (_data, variables) => invalidateDocument(queryClient, variables.documentId),
  });
}

export function useArchiveResearchDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ documentId, archivedBy }: { documentId: string; archivedBy?: string | null }) =>
      archiveResearchDocument(documentId, archivedBy),
    onSuccess: (_data, variables) => invalidateDocument(queryClient, variables.documentId),
  });
}
