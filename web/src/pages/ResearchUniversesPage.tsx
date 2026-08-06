import type { ReactElement } from "react";
import { Alert, Box, CircularProgress, Stack, Typography } from "@mui/material";
import { UniverseCard } from "../components/UniverseCard";
import { useResearchUniverses } from "../queries/useResearchUniverses";

export function ResearchUniversesPage(): ReactElement {
  const { data, isLoading, isError, error } = useResearchUniverses();

  const universes = data?.universes ?? [];
  const researchUniverses = universes.filter((u) => u.collection_type !== "benchmark");
  const benchmarks = universes.filter((u) => u.collection_type === "benchmark");

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h4" gutterBottom>
          Research Universes
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Organization-wide, curated coverage groups of real, SEC-verified issuers — organized the
          way a distressed-credit team thinks about coverage. Click a universe to open Credit
          Universe filtered to it.
        </Typography>
      </Box>

      {isLoading && (
        <Box sx={{ py: 8, textAlign: "center" }}>
          <CircularProgress />
        </Box>
      )}

      {isError && (
        <Alert severity="error">
          Could not load Research Universes:{" "}
          {error instanceof Error ? error.message : "unknown error"}
        </Alert>
      )}

      {!isLoading && !isError && universes.length === 0 && (
        <Alert severity="info">No Research Universes have been seeded yet.</Alert>
      )}

      {researchUniverses.length > 0 && (
        <Box>
          <Typography variant="h6" gutterBottom>
            Coverage Universes
          </Typography>
          <Stack direction="row" flexWrap="wrap" useFlexGap spacing={2}>
            {researchUniverses.map((universe) => (
              <Box key={universe.id} sx={{ width: { xs: "100%", sm: 340 } }}>
                <UniverseCard universe={universe} />
              </Box>
            ))}
          </Stack>
        </Box>
      )}

      {benchmarks.length > 0 && (
        <Box>
          <Typography variant="h6" gutterBottom>
            Investment Grade Benchmarks
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            A clean baseline for comparison — deliberately kept separate from the distress-oriented
            universes above.
          </Typography>
          <Stack direction="row" flexWrap="wrap" useFlexGap spacing={2}>
            {benchmarks.map((universe) => (
              <Box key={universe.id} sx={{ width: { xs: "100%", sm: 340 } }}>
                <UniverseCard universe={universe} />
              </Box>
            ))}
          </Stack>
        </Box>
      )}
    </Stack>
  );
}
