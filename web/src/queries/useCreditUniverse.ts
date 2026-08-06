import { useQuery } from "@tanstack/react-query";
import { type CreditUniverseQuery, fetchCreditUniverse } from "../api/creditUniverse";

export function useCreditUniverse(query: CreditUniverseQuery) {
  return useQuery({
    queryKey: ["credit-universe", query],
    queryFn: () => fetchCreditUniverse(query),
    placeholderData: (previousData) => previousData,
  });
}
