import { useQuery } from "@tanstack/react-query";
import { fetchIssuerDetail } from "../api/issuer";

export function useIssuerDetail(issuerId: string | undefined) {
  return useQuery({
    queryKey: ["issuer-detail", issuerId],
    queryFn: () => fetchIssuerDetail(issuerId as string),
    enabled: issuerId !== undefined,
  });
}
