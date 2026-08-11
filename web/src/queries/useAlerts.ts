import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  type AlertsQuery,
  acknowledgeAlert,
  dismissAlert,
  fetchAlertEvidence,
  fetchAlerts,
  fetchAlertsSummary,
  searchAlertIssuers,
} from "../api/filingMonitor";

export function useAlerts(query: AlertsQuery, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ["alerts", query],
    queryFn: () => fetchAlerts(query),
    placeholderData: (previousData) => previousData,
    enabled: options?.enabled,
  });
}

export function useAlertsSummary() {
  return useQuery({
    queryKey: ["alerts-summary"],
    queryFn: () => fetchAlertsSummary(),
  });
}

export function useAlertIssuerSearch(query: string) {
  return useQuery({
    queryKey: ["alert-issuer-search", query],
    queryFn: () => searchAlertIssuers(query),
    enabled: query.trim().length > 0,
  });
}

export function useAlertEvidence(alertId: string | undefined) {
  return useQuery({
    queryKey: ["alert-evidence", alertId],
    queryFn: () => fetchAlertEvidence(alertId as string),
    enabled: alertId !== undefined,
  });
}

export function useAcknowledgeAlert() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ alertId, actedBy }: { alertId: string; actedBy?: string }) =>
      acknowledgeAlert(alertId, actedBy),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["alerts"] });
      void queryClient.invalidateQueries({ queryKey: ["alerts-summary"] });
      void queryClient.invalidateQueries({ queryKey: ["morning-brief"] });
    },
  });
}

export function useDismissAlert() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      alertId,
      reason,
      actedBy,
    }: {
      alertId: string;
      reason?: string;
      actedBy?: string;
    }) => dismissAlert(alertId, reason, actedBy),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["alerts"] });
      void queryClient.invalidateQueries({ queryKey: ["alerts-summary"] });
      void queryClient.invalidateQueries({ queryKey: ["morning-brief"] });
    },
  });
}
