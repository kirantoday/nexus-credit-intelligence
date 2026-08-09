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
 * visit's own view is never read as its own boundary. `recordMorningBriefView`
 * itself retries directly (not via this hook's `retry` option, which was
 * live-verified in production to not actually re-attempt the call — see
 * PLAN.md TD-019) — a real, live-caught intermittent `503` was observed in
 * production for this specific endpoint, root cause still under
 * investigation. */
export function useRecordMorningBriefView() {
  return useMutation({
    mutationFn: recordMorningBriefView,
  });
}
