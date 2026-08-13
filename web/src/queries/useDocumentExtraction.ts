import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError } from "../api/client";
import {
  fetchChunks,
  fetchCurrentExtraction,
  fetchExtraction,
  fetchExtractions,
  processDocument,
  searchChunks,
  type DocumentExtraction,
} from "../api/documentExtraction";

const ACTIVE_STATUSES: DocumentExtraction["status"][] = ["pending", "processing"];

/** `null` (not an error) when no extraction has ever completed for this
 * document — 404 from the API is the expected "not processed yet"
 * shape, distinguished from a real fetch failure via `ApiError.status`. */
export function useCurrentExtraction(documentId: string | undefined) {
  return useQuery({
    queryKey: ["document-extraction", "current", documentId],
    queryFn: async () => {
      try {
        return await fetchCurrentExtraction(documentId as string);
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) return null;
        throw err;
      }
    },
    enabled: documentId !== undefined,
  });
}

/** Polls every 4s while any extraction for this document is `pending`/
 * `processing` — the worker runs on a Railway cron cycle (every 5
 * minutes), not synchronously, so the UI needs to notice completion on
 * its own rather than expecting an immediate response. Polling stops the
 * moment nothing active remains. */
export function useExtractionHistory(documentId: string | undefined) {
  return useQuery({
    queryKey: ["document-extraction", "history", documentId],
    queryFn: () => fetchExtractions(documentId as string),
    enabled: documentId !== undefined,
    refetchInterval: (query) => {
      const extractions = query.state.data?.extractions ?? [];
      const hasActive = extractions.some((e) => ACTIVE_STATUSES.includes(e.status));
      return hasActive ? 4000 : false;
    },
  });
}

export function useExtraction(extractionId: string | undefined) {
  return useQuery({
    queryKey: ["document-extraction", extractionId],
    queryFn: () => fetchExtraction(extractionId as string),
    enabled: extractionId !== undefined,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && ACTIVE_STATUSES.includes(status) ? 4000 : false;
    },
  });
}

export function useChunks(extractionId: string | undefined) {
  return useQuery({
    queryKey: ["document-chunks", extractionId],
    queryFn: () => fetchChunks(extractionId as string),
    enabled: extractionId !== undefined,
  });
}

export function useChunkSearch(extractionId: string | undefined, query: string) {
  return useQuery({
    queryKey: ["document-chunks", "search", extractionId, query],
    queryFn: () => searchChunks(extractionId as string, query),
    enabled: extractionId !== undefined && query.trim().length > 0,
  });
}

export function useProcessDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      documentId,
      requestedBy,
    }: {
      documentId: string;
      requestedBy?: string | null;
    }) => processDocument(documentId, requestedBy),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({
        queryKey: ["document-extraction", "current", variables.documentId],
      });
      void queryClient.invalidateQueries({
        queryKey: ["document-extraction", "history", variables.documentId],
      });
    },
  });
}
