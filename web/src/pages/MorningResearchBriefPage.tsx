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
import type { AlertStatus, DetectionMethod, EvidenceSeverity } from "../api/filingMonitor";
import { AlertCard } from "../components/AlertCard";
import { BriefSummaryBar } from "../components/BriefSummaryBar";
import { useAcknowledgeAlert, useAlerts, useDismissAlert } from "../queries/useAlerts";
import { useMorningBrief } from "../queries/useMorningBrief";
import { useResearchUniverses } from "../queries/useResearchUniverses";

/**
 * The Morning Research Brief (PLAN.md 24.9). Title and heading are
 * deliberately worded generically ("New Research Alerts," not "New
 * Distress Filings") — this milestone's alerts are all SEC-filing-sourced,
 * but the page is designed so CourtListener/FRED/ratings/macro alerts can
 * appear here later without a copy or layout change.
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

  // Default scope is the latest successful DAILY run's boundary — showing
  // "6 actionable alerts" in the summary bar next to hundreds of all-time
  // alert rows below it is exactly the bug this milestone fixed (PLAN.md
  // Milestone 7.5.2 section 7). The "Show historical alerts" toggle is the
  // one escape hatch, and it's explicit, not a default.
  const triggeredSince = showHistory ? undefined : (briefQuery.data?.since ?? undefined);
  const alertsQuery = useAlerts({
    severity,
    universeId,
    status,
    detectionMethod,
    triggeredSince,
    pageSize: 100,
  });

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h4" gutterBottom>
          Morning Research Brief
        </Typography>
        <Typography variant="body1" color="text.secondary">
          {showHistory
            ? "All Research Alerts — All-Time"
            : "New Research Alerts — Since Last Successful Daily Run"}
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
      {briefQuery.data && <BriefSummaryBar summary={briefQuery.data} />}

      <Paper variant="outlined" sx={{ p: 2 }}>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={2} flexWrap="wrap" useFlexGap>
          <TextField
            label="Severity"
            select
            size="small"
            value={severity ?? ""}
            onChange={(e) => updateParams({ severity: e.target.value || null })}
            sx={{ minWidth: 140 }}
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
            sx={{ minWidth: 220 }}
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
            sx={{ minWidth: 160 }}
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
            sx={{ minWidth: 160 }}
          >
            <MenuItem value="">All statuses</MenuItem>
            <MenuItem value="new">New</MenuItem>
            <MenuItem value="acknowledged">Acknowledged</MenuItem>
            <MenuItem value="dismissed">Dismissed</MenuItem>
          </TextField>
          <FormControlLabel
            sx={{ ml: { sm: "auto" } }}
            control={
              <Switch
                checked={showHistory}
                onChange={(e) => updateParams({ history: e.target.checked ? "1" : null })}
              />
            }
            label="Show historical alerts (all-time, not just this daily run)"
          />
        </Stack>
      </Paper>

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
    </Stack>
  );
}
