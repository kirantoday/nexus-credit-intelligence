import type { ReactElement } from "react";
import { Box, Chip, Paper, Stack, Typography } from "@mui/material";
import type { MorningBriefSummary } from "../api/filingMonitor";
import { formatDateTime } from "../lib/format";

function Stat({ label, value }: { label: string; value: string | number }): ReactElement {
  return (
    <Box sx={{ minWidth: 120 }}>
      <Typography variant="h5">{value}</Typography>
      <Typography variant="caption" color="text.secondary">
        {label}
      </Typography>
    </Box>
  );
}

/** The Morning Research Brief's summary bar (PLAN.md 24.9). */
export function BriefSummaryBar({ summary }: { summary: MorningBriefSummary }): ReactElement {
  const run = summary.latest_run;
  const runStatusColor: "success" | "warning" | "error" | "default" =
    run?.status === "success" || run?.status === "baseline_established"
      ? "success"
      : run?.status === "completed_with_errors"
        ? "warning"
        : run?.status === "failed"
          ? "error"
          : "default";

  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 2 }} flexWrap="wrap">
        <Typography variant="body2" color="text.secondary">
          Last successful run:{" "}
          {summary.last_successful_run
            ? formatDateTime(
                summary.last_successful_run.completed_at ?? summary.last_successful_run.started_at,
              )
            : "never"}
        </Typography>
        {run && <Chip label={`Current run: ${run.status}`} size="small" color={runStatusColor} />}
      </Stack>
      <Stack direction="row" spacing={3} flexWrap="wrap" useFlexGap>
        <Stat label="Universes monitored" value={summary.universes_monitored} />
        <Stat label="Issuers monitored" value={summary.issuers_monitored} />
        <Stat label="New SEC filings" value={summary.new_sec_filings} />
        <Stat label="New court events" value={summary.new_court_events} />
        <Stat label="New research evidence" value={summary.new_research_evidence} />
        <Stat label="Actionable alerts" value={summary.actionable_alerts_total} />
        <Stat label="High severity" value={summary.alerts_by_severity.high} />
        <Stat label="Medium severity" value={summary.alerts_by_severity.medium} />
        <Stat label="Low severity" value={summary.alerts_by_severity.low} />
        <Stat label="AI-assisted" value={summary.ai_assisted_alert_count} />
        {summary.failures_count > 0 && <Stat label="Failures" value={summary.failures_count} />}
      </Stack>
      {summary.no_new_alerts && (
        <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
          No new distress alerts since the last successful run.
        </Typography>
      )}
    </Paper>
  );
}
