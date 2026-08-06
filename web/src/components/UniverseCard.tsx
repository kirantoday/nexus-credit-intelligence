import type { ReactElement } from "react";
import { useNavigate } from "react-router";
import { Box, Card, CardActionArea, CardContent, Chip, Stack, Typography } from "@mui/material";
import type { ResearchUniverseSummary } from "../api/researchUniverse";
import { formatDate } from "../lib/format";

const PRIORITY_COLOR: Record<string, "error" | "warning" | "info" | "default"> = {
  critical: "error",
  high: "warning",
  medium: "info",
  low: "default",
};

/**
 * One Research Universe / Benchmark card on the Research Universes page.
 * Clicking navigates to Credit Universe pre-filtered to this universe
 * (PLAN.md 24.9 — "clicking a universe opens Credit Universe with that
 * universe filter applied").
 */
export function UniverseCard({ universe }: { universe: ResearchUniverseSummary }): ReactElement {
  const navigate = useNavigate();

  return (
    <Card
      variant="outlined"
      sx={{
        borderColor: universe.collection_type === "benchmark" ? "info.main" : undefined,
      }}
    >
      <CardActionArea onClick={() => navigate(`/?universe=${universe.id}`)}>
        <CardContent>
          <Stack direction="row" justifyContent="space-between" alignItems="flex-start">
            <Typography variant="h6">{universe.name}</Typography>
            {universe.collection_type === "benchmark" && (
              <Chip label="Benchmark" size="small" color="info" variant="outlined" />
            )}
          </Stack>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, mb: 1.5 }}>
            {universe.description}
          </Typography>
          <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
            <Chip
              label={`${universe.issuer_count} issuer${universe.issuer_count === 1 ? "" : "s"}`}
              size="small"
            />
            {universe.priority && (
              <Chip
                label={universe.priority}
                size="small"
                color={PRIORITY_COLOR[universe.priority]}
                variant="outlined"
              />
            )}
            <Chip label={universe.verification_status} size="small" variant="outlined" />
          </Stack>
          <Box sx={{ mt: 1 }}>
            <Typography variant="caption" color="text.secondary">
              {universe.last_verified_at
                ? `Last verified ${formatDate(universe.last_verified_at)}`
                : "Not yet verified"}
            </Typography>
          </Box>
        </CardContent>
      </CardActionArea>
    </Card>
  );
}
