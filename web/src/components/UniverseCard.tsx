import type { ReactElement } from "react";
import { useNavigate } from "react-router";
import { Box, Card, CardActionArea, CardContent, Chip, Stack, Typography } from "@mui/material";
import type { ResearchUniverseSummary } from "../api/researchUniverse";
import { categoryAccentColor } from "../lib/categoryColor";
import { formatDate } from "../lib/format";

const PRIORITY_COLOR: Record<string, "error" | "warning" | "info" | "default"> = {
  critical: "error",
  high: "warning",
  medium: "info",
  low: "default",
};

const VERIFICATION_COLOR: Record<string, "success" | "default"> = {
  verified: "success",
  partial: "default",
  unverified: "default",
};

/**
 * One Research Universe / Benchmark card on the Research Universes page.
 * Clicking navigates to Credit Universe pre-filtered to this universe
 * (PLAN.md 24.9 — "clicking a universe opens Credit Universe with that
 * universe filter applied").
 */
export function UniverseCard({ universe }: { universe: ResearchUniverseSummary }): ReactElement {
  const navigate = useNavigate();
  const accent =
    universe.collection_type === "benchmark" ? "info" : categoryAccentColor(universe.name);

  return (
    <Card
      variant="outlined"
      sx={{
        borderLeft: 4,
        borderLeftColor: `${accent}.main`,
        height: "100%",
      }}
    >
      <CardActionArea onClick={() => navigate(`/?universe=${universe.id}`)} sx={{ height: "100%" }}>
        <CardContent>
          <Stack direction="row" justifyContent="space-between" alignItems="flex-start" spacing={1}>
            <Box>
              <Typography variant="h6">{universe.name}</Typography>
              {universe.collection_type === "benchmark" && (
                <Chip
                  label="Benchmark"
                  size="small"
                  color="info"
                  variant="outlined"
                  sx={{ mt: 0.5 }}
                />
              )}
            </Box>
            <Box sx={{ textAlign: "right", flexShrink: 0 }}>
              <Typography variant="h5" fontWeight={700} color="primary.main" lineHeight={1.1}>
                {universe.issuer_count}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                issuer{universe.issuer_count === 1 ? "" : "s"}
              </Typography>
            </Box>
          </Stack>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1, mb: 1.5 }}>
            {universe.description}
          </Typography>
          <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
            {universe.priority && (
              <Chip
                label={universe.priority}
                size="small"
                color={PRIORITY_COLOR[universe.priority]}
                variant="outlined"
              />
            )}
            <Chip
              label={universe.verification_status}
              size="small"
              color={VERIFICATION_COLOR[universe.verification_status] ?? "default"}
              variant={
                VERIFICATION_COLOR[universe.verification_status] === "success"
                  ? "filled"
                  : "outlined"
              }
            />
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
