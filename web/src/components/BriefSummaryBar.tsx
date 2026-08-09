import type { ReactElement } from "react";
import { Box, Paper, Stack, Typography } from "@mui/material";
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

/**
 * The Morning Research Brief's primary summary bar (PLAN.md Milestone
 * 7.5.2 correction) — analyst-relevant research counts only. Pipeline/run
 * operational counters live in `RunDetailsPanel`, a secondary block, not
 * here.
 */
export function BriefSummaryBar({ summary }: { summary: MorningBriefSummary }): ReactElement {
  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Stack spacing={0.5} sx={{ mb: 2 }}>
        <Typography variant="body2" color="text.secondary">
          {summary.period_start_is_fallback
            ? `First time viewing — showing developments since ${formatDateTime(summary.period_start)} (previous business day)`
            : `Since your last review: ${formatDateTime(summary.period_start)}`}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Period covered: {formatDateTime(summary.period_start)} –{" "}
          {formatDateTime(summary.period_end)}
        </Typography>
      </Stack>
      <Stack direction="row" spacing={3} flexWrap="wrap" useFlexGap>
        <Stat label="Issuers with developments" value={summary.issuers_with_developments} />
        <Stat label="High severity" value={summary.severity_counts.high} />
        <Stat label="Medium severity" value={summary.severity_counts.medium} />
        <Stat label="Low severity" value={summary.severity_counts.low} />
        {summary.historical_intelligence_issuer_count > 0 && (
          <Stat
            label="Issuers with historical intelligence"
            value={summary.historical_intelligence_issuer_count}
          />
        )}
      </Stack>
      {summary.no_material_changes && (
        <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
          No material research developments since your last review.
        </Typography>
      )}
    </Paper>
  );
}
