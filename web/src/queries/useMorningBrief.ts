import { useQuery } from "@tanstack/react-query";
import { fetchMorningBrief } from "../api/filingMonitor";

export function useMorningBrief() {
  return useQuery({
    queryKey: ["morning-brief"],
    queryFn: fetchMorningBrief,
  });
}
