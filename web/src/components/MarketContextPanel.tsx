import type { ReactElement } from "react";
import { Box, Paper, Skeleton, Stack, Tooltip, Typography } from "@mui/material";
import type { MarketContextObservation } from "../api/marketContext";
import { useMarketContext } from "../queries/useMarketContext";
import { formatBasisPoints, formatDate, formatPercent } from "../lib/format";

type MetricLabel = "SOFR" | "HY OAS";

const METRIC_DESCRIPTION: Record<MetricLabel, string> = {
  SOFR: "Secured Overnight Financing Rate — a base rate commonly used for floating-rate corporate loans.",
  "HY OAS":
    "High-Yield Option-Adjusted Spread — the additional spread investors demand for high-yield corporate credit relative to comparable Treasury rates, adjusted for embedded options.",
};

function InfoGlyph({ description }: { description: string }): ReactElement {
  return (
    <Tooltip title={description}>
      <Typography
        component="span"
        variant="caption"
        color="text.secondary"
        aria-label={description}
        sx={{ cursor: "help", ml: 0.5 }}
      >
        ⓘ
      </Typography>
    </Tooltip>
  );
}

/**
 * One market-context metric — SOFR (financing/refinancing pressure for
 * floating-rate borrowers) or HY OAS (broad market pricing of high-yield
 * credit risk). Each observation carries its own `as_of_date`; SOFR and HY
 * OAS commonly publish on different days, so each metric shows its own date
 * rather than one shared, potentially misleading date for both.
 */
function MetricCard({
  label,
  observation,
  showBasisPoints,
}: {
  label: MetricLabel;
  observation: MarketContextObservation | null;
  showBasisPoints?: boolean;
}): ReactElement {
  return (
    <Box>
      <Stack direction="row" alignItems="center">
        <Typography variant="caption" color="text.secondary">
          {label}
        </Typography>
        <InfoGlyph description={METRIC_DESCRIPTION[label]} />
      </Stack>
      {/* Honestly absent, never a placeholder number: a series that hasn't
          been synced yet renders as "—", not a fabricated or zeroed value. */}
      {observation === null ? (
        <Typography variant="h6">—</Typography>
      ) : (
        <>
          <Typography variant="h6" fontWeight={600}>
            {formatPercent(observation.value)}
          </Typography>
          {showBasisPoints && (
            <Typography variant="caption" color="text.secondary" display="block">
              {formatBasisPoints(observation.value)}
            </Typography>
          )}
          <Typography variant="caption" color="text.secondary" display="block">
            As of {formatDate(observation.as_of_date)}
          </Typography>
        </>
      )}
    </Box>
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
      <Typography variant="overline" color="text.secondary" display="block" sx={{ mb: 0.5 }}>
        Market Context
      </Typography>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={3}>
        <MetricCard label="SOFR" observation={data.sofr} />
        <MetricCard label="HY OAS" observation={data.high_yield_oas} showBasisPoints />
      </Stack>
    </Paper>
  );
}
