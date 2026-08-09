import { useMutation, useQuery } from "@tanstack/react-query";
import { fetchMorningBrief, recordMorningBriefView } from "../api/filingMonitor";

export function useMorningBrief() {
  return useQuery({
    queryKey: ["morning-brief"],
    queryFn: fetchMorningBrief,
  });
}

/** Records that the brief was viewed. Call only once the brief query has
 * already resolved (see `MorningResearchBriefPage`'s effect), so this
 * visit's own view is never read as its own boundary. */
export function useRecordMorningBriefView() {
  return useMutation({
    mutationFn: recordMorningBriefView,
  });
}
