import { useQuery } from "@tanstack/react-query";
import { fetchMarketContext } from "../api/marketContext";

export function useMarketContext() {
  return useQuery({
    queryKey: ["market-context"],
    queryFn: fetchMarketContext,
  });
}
