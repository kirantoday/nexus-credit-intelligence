import type { ReactElement } from "react";
import { useSearchParams } from "react-router";
import {
  Alert,
  Box,
  CircularProgress,
  FormControlLabel,
  MenuItem,
  Paper,
  Stack,
  Switch,
  TextField,
  Typography,
} from "@mui/material";
import type {
  AlertStatus,
  DetectionMethod,
  EvidenceSeverity,
  IssuerDevelopment,
} from "../api/filingMonitor";
import { AlertCard } from "../components/AlertCard";
import { BriefSummaryBar } from "../components/BriefSummaryBar";
import { IssuerDevelopmentCard } from "../components/IssuerDevelopmentCard";
import { RunDetailsPanel } from "../components/RunDetailsPanel";
import { useAcknowledgeAlert, useAlerts, useDismissAlert } from "../queries/useAlerts";
import { useMorningBrief } from "../queries/useMorningBrief";
import { useResearchUniverses } from "../queries/useResearchUniverses";

function filterDevelopments(
  developments: IssuerDevelopment[],
  filters: {
    severity?: EvidenceSeverity;
    universeName?: string;
    detectionMethod?: DetectionMethod;
    status?: AlertStatus;
  },
): IssuerDevelopment[] {
  return developments
    .map((development) => ({
      ...development,
      alerts: development.alerts.filter(
        (alert) =>
          (!filters.severity || alert.severity === filters.severity) &&
          (!filters.detectionMethod || alert.detection_method === filters.detectionMethod) &&
          (!filters.status || alert.status === filters.status) &&
          (!filters.universeName || alert.universe_names.includes(filters.universeName)),
      ),
    }))
    .filter((development) => development.alerts.length > 0);
}

/**
 * The Morning Research Brief (PLAN.md Milestone 7.5.2's business-day-cycle
 * correction): "What materially changed during the latest completed
 * business-day research cycle, compared with the preceding one?" The
 * comparison window comes entirely from the API (canonical run data +
 * calendar arithmetic) — this page never records or reads any view/visit
 * state, so opening, refreshing, or revisiting it can never change what
 * counts as "new." `new_developments`/`historical_intelligence` come
 * pre-grouped and pre-ranked from the API — filters below apply
 * client-side to that already-fetched data, never a broader unscoped
 * query. The "Show historical alerts" toggle is a separate, explicit
 * escape hatch to the full all-time flat list (`GET /api/alerts`,
 * unchanged).
 */
export function MorningResearchBriefPage(): ReactElement {
  const [searchParams, setSearchParams] = useSearchParams();
  const briefQuery = useMorningBrief();
  const universesQuery = useResearchUniverses();
  const acknowledgeMutation = useAcknowledgeAlert();
  const dismissMutation = useDismissAlert();

  const severity = (searchParams.get("severity") as EvidenceSeverity | null) ?? undefined;
  const universeId = searchParams.get("universe") ?? undefined;
  const status = (searchParams.get("status") as AlertStatus | null) ?? undefined;
  const detectionMethod = (searchParams.get("detection") as DetectionMethod | null) ?? undefined;
  const showHistory = searchParams.get("history") === "1";

  function updateParams(updates: Record<string, string | null>): void {
    const next = new URLSearchParams(searchParams);
    for (const [key, value] of Object.entries(updates)) {
      if (value === null || value === "") {
        next.delete(key);
      } else {
        next.set(key, value);
      }
    }
    setSearchParams(next, { replace: true });
  }

  const universeName = universesQuery.data?.universes.find((u) => u.id === universeId)?.name;
  const filters = { severity, universeName, detectionMethod, status };

  const alertsQuery = useAlerts(
    { severity, universeId, status, detectionMethod, pageSize: 100 },
    { enabled: showHistory },
  );

  const newDevelopments = briefQuery.data
    ? filterDevelopments(briefQuery.data.new_developments, filters)
    : [];
  const historicalIntelligence = briefQuery.data
    ? filterDevelopments(briefQuery.data.historical_intelligence, filters)
    : [];

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h4" gutterBottom>
          Morning Research Brief
        </Typography>
        <Typography variant="body1" color="text.secondary">
          {showHistory
            ? "All Research Alerts — All-Time"
            : "What changed in the latest research cycle"}
        </Typography>
      </Box>

      {briefQuery.isLoading && (
        <Box sx={{ py: 4, textAlign: "center" }}>
          <CircularProgress />
        </Box>
      )}
      {briefQuery.isError && (
        <Alert severity="error">
          Could not load the brief summary:{" "}
          {briefQuery.error instanceof Error ? briefQuery.error.message : "unknown error"}
        </Alert>
      )}
      {briefQuery.data && (
        <>
          <BriefSummaryBar summary={briefQuery.data} />
          <RunDetailsPanel details={briefQuery.data.run_details} />
        </>
      )}

      <Paper variant="outlined" sx={{ p: 2 }}>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={2} flexWrap="wrap" useFlexGap>
          <TextField
            label="Severity"
            select
            size="small"
            value={severity ?? ""}
            onChange={(e) => updateParams({ severity: e.target.value || null })}
            sx={{ width: { xs: "100%", sm: 140 } }}
          >
            <MenuItem value="">All severities</MenuItem>
            <MenuItem value="high">High</MenuItem>
            <MenuItem value="medium">Medium</MenuItem>
            <MenuItem value="low">Low</MenuItem>
          </TextField>
          <TextField
            label="Research Universe"
            select
            size="small"
            value={universeId ?? ""}
            onChange={(e) => updateParams({ universe: e.target.value || null })}
            sx={{ width: { xs: "100%", sm: 220 } }}
          >
            <MenuItem value="">All universes</MenuItem>
            {universesQuery.data?.universes.map((universe) => (
              <MenuItem key={universe.id} value={universe.id}>
                {universe.name}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            label="Detection"
            select
            size="small"
            value={detectionMethod ?? ""}
            onChange={(e) => updateParams({ detection: e.target.value || null })}
            sx={{ width: { xs: "100%", sm: 160 } }}
          >
            <MenuItem value="">Deterministic + AI-assisted</MenuItem>
            <MenuItem value="deterministic">Deterministic only</MenuItem>
            <MenuItem value="ai_assisted">AI-assisted only</MenuItem>
          </TextField>
          <TextField
            label="Status"
            select
            size="small"
            value={status ?? ""}
            onChange={(e) => updateParams({ status: e.target.value || null })}
            sx={{ width: { xs: "100%", sm: 160 } }}
          >
            <MenuItem value="">All statuses</MenuItem>
            <MenuItem value="new">New</MenuItem>
            <MenuItem value="acknowledged">Acknowledged</MenuItem>
            <MenuItem value="dismissed">Dismissed</MenuItem>
          </TextField>
          <FormControlLabel
            sx={{ ml: { sm: "auto" }, mr: 0 }}
            control={
              <Switch
                checked={showHistory}
                onChange={(e) => updateParams({ history: e.target.checked ? "1" : null })}
              />
            }
            label="Show historical alerts (all-time, not just this period)"
          />
        </Stack>
      </Paper>

      {showHistory ? (
        <>
          {alertsQuery.isLoading && (
            <Box sx={{ py: 4, textAlign: "center" }}>
              <CircularProgress />
            </Box>
          )}
          {alertsQuery.isError && (
            <Alert severity="error">
              Could not load alerts:{" "}
              {alertsQuery.error instanceof Error ? alertsQuery.error.message : "unknown error"}
            </Alert>
          )}
          {alertsQuery.data && alertsQuery.data.alerts.length === 0 && (
            <Alert severity="success">
              No research alerts match these filters — nothing to review right now.
            </Alert>
          )}
          <Stack spacing={2}>
            {alertsQuery.data?.alerts.map((alert) => (
              <AlertCard
                key={alert.id}
                alert={alert}
                onAcknowledge={(alertId) => acknowledgeMutation.mutate({ alertId })}
                onDismiss={(alertId, reason) => dismissMutation.mutate({ alertId, reason })}
              />
            ))}
          </Stack>
        </>
      ) : (
        <>
          {briefQuery.data && newDevelopments.length === 0 && (
            <Alert severity="success">
              No material research developments match these filters — nothing new to review.
            </Alert>
          )}
          <Stack spacing={3}>
            {newDevelopments.map((development) => (
              <IssuerDevelopmentCard
                key={development.issuer_id}
                development={development}
                onAcknowledge={(alertId) => acknowledgeMutation.mutate({ alertId })}
                onDismiss={(alertId, reason) => dismissMutation.mutate({ alertId, reason })}
              />
            ))}
          </Stack>

          {historicalIntelligence.length > 0 && (
            <Box
              sx={{
                mt: 2,
                p: 2,
                bgcolor: "background.default",
                border: 1,
                borderColor: "divider",
                borderRadius: 1,
              }}
            >
              <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                Newly Discovered Historical Intelligence
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Older events Nexus discovered this period — not new developments; shown separately
                so they're never mistaken for overnight news.
              </Typography>
              <Stack spacing={3}>
                {historicalIntelligence.map((development) => (
                  <IssuerDevelopmentCard
                    key={development.issuer_id}
                    development={development}
                    onAcknowledge={(alertId) => acknowledgeMutation.mutate({ alertId })}
                    onDismiss={(alertId, reason) => dismissMutation.mutate({ alertId, reason })}
                  />
                ))}
              </Stack>
            </Box>
          )}
        </>
      )}
    </Stack>
  );
}
