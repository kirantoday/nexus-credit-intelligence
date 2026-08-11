import type { ReactElement } from "react";
import { useNavigate } from "react-router";
import { Box, Card, CardActionArea, CardContent, Chip, Stack, Typography } from "@mui/material";
import type { WatchlistSummary } from "../api/watchlist";
import { formatDate } from "../lib/format";

/** One Watchlist card on the Watchlists landing page — an analyst-dashboard
 * summary ("MY DISTRESSED NAMES / 12 issuers / 3 with new developments / 2
 * high-severity developments"), never a bare CRUD row (PLAN.md Milestone 8
 * Phase 9). All counts are real, already-aggregated backend results. */
export function WatchlistCard({ watchlist }: { watchlist: WatchlistSummary }): ReactElement {
  const navigate = useNavigate();

  return (
    <Card
      variant="outlined"
      sx={{ borderLeft: 4, borderLeftColor: "primary.main", height: "100%" }}
    >
      <CardActionArea
        onClick={() => navigate(`/watchlists/${watchlist.id}`)}
        sx={{ height: "100%" }}
      >
        <CardContent>
          <Typography variant="h6" sx={{ textTransform: "uppercase", letterSpacing: 0.3 }}>
            {watchlist.name}
          </Typography>
          {watchlist.description && (
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, mb: 1.5 }}>
              {watchlist.description}
            </Typography>
          )}
          <Stack direction="row" spacing={3} sx={{ mt: 1 }}>
            <Box>
              <Typography variant="h5" fontWeight={700} lineHeight={1.1}>
                {watchlist.issuer_count}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                issuer{watchlist.issuer_count === 1 ? "" : "s"}
              </Typography>
            </Box>
            <Box>
              <Typography
                variant="h5"
                fontWeight={700}
                lineHeight={1.1}
                color={
                  watchlist.issuers_with_new_developments > 0 ? "warning.main" : "text.primary"
                }
              >
                {watchlist.issuers_with_new_developments}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                with new developments
              </Typography>
            </Box>
            <Box>
              <Typography
                variant="h5"
                fontWeight={700}
                lineHeight={1.1}
                color={watchlist.high_severity_count > 0 ? "error.main" : "text.primary"}
              >
                {watchlist.high_severity_count}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                high-severity
              </Typography>
            </Box>
          </Stack>
          <Box sx={{ mt: 1.5 }}>
            {watchlist.last_activity_at ? (
              <Chip
                label={`Last activity ${formatDate(watchlist.last_activity_at)}`}
                size="small"
                variant="outlined"
              />
            ) : (
              <Typography variant="caption" color="text.secondary">
                No issuers tracked yet
              </Typography>
            )}
          </Box>
        </CardContent>
      </CardActionArea>
    </Card>
  );
}
