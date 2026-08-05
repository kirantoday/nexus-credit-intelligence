import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../api/client";

export interface HealthResponse {
  status: string;
  service: string;
  environment: string;
  timestamp: string;
}

export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: () => apiFetch<HealthResponse>("/health"),
    retry: 1,
    refetchInterval: 30_000,
  });
}
