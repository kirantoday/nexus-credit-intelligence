import { useQuery } from "@tanstack/react-query";
import { fetchCapitalStructure } from "../api/capitalStructure";

export function useCapitalStructure(issuerId: string | undefined) {
  return useQuery({
    queryKey: ["capital-structure", issuerId],
    queryFn: () => fetchCapitalStructure(issuerId as string),
    enabled: issuerId !== undefined,
  });
}
