import { type ReactElement, useState } from "react";
import { Box, Button, Chip, Collapse, Stack, Typography } from "@mui/material";
import type { RunDetails } from "../api/filingMonitor";
import { formatDate, formatDateTime } from "../lib/format";

/**
 * Secondary, diagnostics-only pipeline-run detail (PLAN.md Milestone 7.5.2
 * correction) — collapsed by default. An analyst reading the Morning Brief
 * cares about research developments (`BriefSummaryBar`), not operational
 * run counters; this panel exists for anyone who does need them.
 */
export function RunDetailsPanel({ details }: { details: RunDetails }): ReactElement {
  const [expanded, setExpanded] = useState(false);
  const run = details.latest_run;
  const runStatusColor: "success" | "warning" | "error" | "default" =
    run?.status === "success" || run?.status === "baseline_established"
      ? "success"
      : run?.status === "completed_with_errors"
        ? "warning"
        : run?.status === "failed"
          ? "error"
          : "default";
  const dailyRun = details.last_successful_run;
  const runWindow =
    dailyRun?.window_start_date && dailyRun.window_end_date
      ? dailyRun.window_start_date === dailyRun.window_end_date
        ? formatDate(dailyRun.window_start_date)
        : `${formatDate(dailyRun.window_start_date)} – ${formatDate(dailyRun.window_end_date)}`
      : null;

  return (
    <Box>
      <Button size="small" onClick={() => setExpanded((e) => !e)}>
        {expanded ? "Hide run/data details" : "Show run/data details"}
      </Button>
      <Collapse in={expanded} unmountOnExit>
        <Box sx={{ mt: 1, p: 2, border: 1, borderColor: "divider", borderRadius: 1 }}>
          <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" sx={{ mb: 1 }}>
            <Typography variant="body2" color="text.secondary">
              Latest successful daily run:{" "}
              {dailyRun ? formatDateTime(dailyRun.completed_at ?? dailyRun.started_at) : "never"}
            </Typography>
            {run && (
              <Chip label={`Current run: ${run.status}`} size="small" color={runStatusColor} />
            )}
          </Stack>
          {runWindow && (
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              Run window: {runWindow}
            </Typography>
          )}
          <Stack direction="row" spacing={3} flexWrap="wrap" useFlexGap>
            <Typography variant="body2">
              Universes monitored: {details.universes_monitored}
            </Typography>
            <Typography variant="body2">Issuers monitored: {details.issuers_monitored}</Typography>
            <Typography variant="body2">
              New SEC filings (this run): {details.new_sec_filings}
            </Typography>
            <Typography variant="body2">
              New court events (this run): {details.new_court_events}
            </Typography>
            <Typography variant="body2">
              New research evidence (this run): {details.new_research_evidence}
            </Typography>
            {details.failures_count > 0 && (
              <Typography variant="body2" color="error">
                Failures: {details.failures_count}
              </Typography>
            )}
          </Stack>
        </Box>
      </Collapse>
    </Box>
  );
}
