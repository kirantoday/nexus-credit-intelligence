import { useQuery } from "@tanstack/react-query";
import { fetchSearch } from "../api/search";

export function useSearch(query: string, limit = 5) {
  const trimmed = query.trim();
  return useQuery({
    queryKey: ["search", trimmed, limit],
    queryFn: () => fetchSearch(trimmed, limit),
    enabled: trimmed.length > 0,
  });
}
