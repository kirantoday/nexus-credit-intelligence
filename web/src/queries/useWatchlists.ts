import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  addIssuerToWatchlist,
  createWatchlist,
  deleteWatchlist,
  fetchWatchlist,
  fetchWatchlists,
  removeIssuerFromWatchlist,
  updateWatchlist,
} from "../api/watchlist";

export function useWatchlists(issuerId?: string) {
  return useQuery({
    queryKey: ["watchlists", issuerId ?? null],
    queryFn: () => fetchWatchlists(issuerId),
  });
}

export function useWatchlist(watchlistId: string | undefined) {
  return useQuery({
    queryKey: ["watchlist", watchlistId],
    queryFn: () => fetchWatchlist(watchlistId as string),
    enabled: watchlistId !== undefined,
  });
}

function invalidateWatchlists(queryClient: ReturnType<typeof useQueryClient>): void {
  void queryClient.invalidateQueries({ queryKey: ["watchlists"] });
  void queryClient.invalidateQueries({ queryKey: ["watchlist"] });
}

export function useCreateWatchlist() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { name: string; description?: string }) => createWatchlist(input),
    onSuccess: () => invalidateWatchlists(queryClient),
  });
}

export function useUpdateWatchlist() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      watchlistId,
      ...input
    }: {
      watchlistId: string;
      name?: string;
      description?: string;
    }) => updateWatchlist(watchlistId, input),
    onSuccess: () => invalidateWatchlists(queryClient),
  });
}

export function useDeleteWatchlist() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (watchlistId: string) => deleteWatchlist(watchlistId),
    onSuccess: () => invalidateWatchlists(queryClient),
  });
}

export function useAddIssuerToWatchlist() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      watchlistId,
      issuerId,
      rationale,
    }: {
      watchlistId: string;
      issuerId: string;
      rationale?: string;
    }) => addIssuerToWatchlist(watchlistId, { issuer_id: issuerId, rationale }),
    onSuccess: () => invalidateWatchlists(queryClient),
  });
}

export function useRemoveIssuerFromWatchlist() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ watchlistId, issuerId }: { watchlistId: string; issuerId: string }) =>
      removeIssuerFromWatchlist(watchlistId, issuerId),
    onSuccess: () => invalidateWatchlists(queryClient),
  });
}
