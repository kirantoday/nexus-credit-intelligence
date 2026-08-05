import type { ReactElement } from "react";
import { Alert, Box, CircularProgress, Paper, Stack, Typography } from "@mui/material";
import { useHealth } from "../queries/useHealth";

export function HomePage(): ReactElement {
  const { data, isLoading, isError, error } = useHealth();

  return (
    <Stack spacing={3}>
      <Typography variant="h4">Nexus Credit Intelligence</Typography>
      <Typography variant="body1" color="text.secondary">
        Milestone 1 application shell. Provider adapters, Credit Universe, and the rest of the
        product surface arrive in later milestones per PLAN.md.
      </Typography>

      <Paper variant="outlined" sx={{ p: 3, maxWidth: 480 }}>
        <Typography variant="h6" gutterBottom>
          Backend status
        </Typography>
        {isLoading && (
          <Box sx={{ py: 1 }}>
            <CircularProgress size={24} />
          </Box>
        )}
        {isError && (
          <Alert severity="error">
            Could not reach the backend: {error instanceof Error ? error.message : "unknown error"}
          </Alert>
        )}
        {data && (
          <Stack spacing={0.5}>
            <Typography>Status: {data.status}</Typography>
            <Typography>Service: {data.service}</Typography>
            <Typography>Environment: {data.environment}</Typography>
            <Typography variant="caption" color="text.secondary">
              As of {data.timestamp}
            </Typography>
          </Stack>
        )}
      </Paper>
    </Stack>
  );
}
