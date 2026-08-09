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
 * visit's own view is never read as its own boundary. Retries on failure
 * (the backend endpoint is idempotent — see `record_brief_view`'s own
 * gap-check — so a retry is always safe): a real, live-caught intermittent
 * failure mode was observed in production (an occasional `503`, cause
 * still under investigation — see PLAN.md TD-019) where the request
 * otherwise silently fails once with no user-visible effect beyond the
 * boundary not advancing that visit. */
export function useRecordMorningBriefView() {
  return useMutation({
    mutationFn: recordMorningBriefView,
    retry: 2,
    retryDelay: 1000,
  });
}
