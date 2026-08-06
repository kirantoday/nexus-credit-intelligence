import type { ReactElement } from "react";
import { Box, Chip, Paper, Skeleton, Stack, Tooltip, Typography } from "@mui/material";
import type { MarketContextObservation } from "../api/marketContext";
import { useMarketContext } from "../queries/useMarketContext";
import { formatDate, formatPercent } from "../lib/format";

function ObservationChip({
  label,
  observation,
}: {
  label: string;
  observation: MarketContextObservation | null;
}): ReactElement {
  // Honestly absent, never a placeholder number: a series that hasn't been
  // synced yet renders as "—", not a fabricated or zeroed value.
  if (observation === null) {
    return (
      <Stack direction="row" spacing={0.75} alignItems="baseline">
        <Typography variant="caption" color="text.secondary">
          {label}
        </Typography>
        <Typography variant="body2">—</Typography>
      </Stack>
    );
  }
  return (
    <Tooltip
      title={`Source: FRED (${observation.series_id}) · As of ${formatDate(observation.as_of_date)}`}
    >
      <Stack direction="row" spacing={0.75} alignItems="baseline">
        <Typography variant="caption" color="text.secondary">
          {label}
        </Typography>
        <Typography variant="body2" fontWeight={600}>
          {formatPercent(observation.value)}
        </Typography>
        <Chip label={observation.freshness} size="small" variant="outlined" />
      </Stack>
    </Tooltip>
  );
}

/**
 * "What macroeconomic environment surrounds this credit?" (Milestone 5) —
 * real FRED observations shown as plain reported facts, not blended into a
 * new score. SOFR because it's the floating-rate benchmark this platform's
 * loan securities actually reference; HY OAS because it's the credit
 * market's own backdrop indicator.
 */
export function MarketContextPanel(): ReactElement {
  const { data, isLoading, isError } = useMarketContext();

  if (isLoading) {
    return (
      <Paper variant="outlined" sx={{ p: 1.5 }}>
        <Skeleton width={320} />
      </Paper>
    );
  }

  if (isError || !data) {
    return (
      <Paper variant="outlined" sx={{ p: 1.5 }}>
        <Typography variant="body2" color="text.secondary">
          Market context unavailable.
        </Typography>
      </Paper>
    );
  }

  return (
    <Paper variant="outlined" sx={{ p: 1.5 }}>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={3}>
        <Box>
          <Typography variant="overline" color="text.secondary">
            Market Context
          </Typography>
        </Box>
        <ObservationChip label="SOFR" observation={data.sofr} />
        <ObservationChip label="HY OAS" observation={data.high_yield_oas} />
      </Stack>
    </Paper>
  );
}
