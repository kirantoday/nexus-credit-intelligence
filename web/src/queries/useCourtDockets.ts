import { useQuery } from "@tanstack/react-query";
import { fetchCourtDocketDetail, fetchCourtDockets } from "../api/courtDocket";

export function useCourtDockets(issuerId?: string) {
  return useQuery({
    queryKey: ["court-dockets", issuerId],
    queryFn: () => fetchCourtDockets(issuerId),
  });
}

export function useCourtDocketDetail(docketId: string | undefined) {
  return useQuery({
    queryKey: ["court-docket-detail", docketId],
    queryFn: () => fetchCourtDocketDetail(docketId as string),
    enabled: docketId !== undefined,
  });
}
