import { useQuery } from "@tanstack/react-query";
import { fetchIssuerTimeline } from "../api/issuerTimeline";

export function useIssuerTimeline(issuerId: string | undefined) {
  return useQuery({
    queryKey: ["issuer-timeline", issuerId],
    queryFn: () => fetchIssuerTimeline(issuerId as string),
    enabled: issuerId !== undefined,
  });
}
