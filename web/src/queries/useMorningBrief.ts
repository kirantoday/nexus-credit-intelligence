import { useQuery } from "@tanstack/react-query";
import { fetchMorningBrief } from "../api/filingMonitor";

/** A pure read — the comparison window (`latest_research_day`/
 * `preceding_research_day`) is derived server-side from canonical run
 * data and calendar arithmetic, never from having viewed this page
 * before (PLAN.md Milestone 7.5.2's business-day-cycle correction), so
 * there is no companion "record a view" call here anymore. */
export function useMorningBrief() {
  return useQuery({
    queryKey: ["morning-brief"],
    queryFn: fetchMorningBrief,
  });
}
