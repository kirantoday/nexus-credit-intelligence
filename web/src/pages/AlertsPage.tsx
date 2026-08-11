import { type ReactElement, useEffect, useState } from "react";
import { useSearchParams } from "react-router";
import {
  Alert,
  Autocomplete,
  Box,
  Card,
  CardContent,
  CircularProgress,
  MenuItem,
  Paper,
  Stack,
  TablePagination,
  TextField,
  Typography,
} from "@mui/material";
import type {
  AlertIssuerSearchResult,
  AlertStatus,
  DetectionMethod,
  EvidenceSeverity,
} from "../api/filingMonitor";
import { AlertCard } from "../components/AlertCard";
import {
  useAcknowledgeAlert,
  useAlertIssuerSearch,
  useAlerts,
  useAlertsSummary,
  useDismissAlert,
} from "../queries/useAlerts";
import { useIssuerDetail } from "../queries/useIssuerDetail";
import { useResearchUniverses } from "../queries/useResearchUniverses";
import { useWatchlists } from "../queries/useWatchlists";
import { useDebouncedValue } from "../lib/useDebouncedValue";

function SummaryTile({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color?: "warning.main" | "error.main";
}): ReactElement {
  return (
    <Card variant="outlined" sx={{ flex: "1 1 140px", minWidth: 140 }}>
      <CardContent sx={{ py: 1.5, "&:last-child": { pb: 1.5 } }}>
        <Typography variant="h4" fontWeight={700} color={color ?? "text.primary"} lineHeight={1.1}>
          {value}
        </Typography>
        <Typography variant="caption" color="text.secondary">
          {label}
        </Typography>
      </CardContent>
    </Card>
  );
}

/**
 * The Alerts Center (PLAN.md Milestone 9, 24.11): "What research alerts
 * require my attention, especially for issuers I care about?" — an
 * analyst review inbox over the same `alert_event` intelligence the
 * Morning Research Brief already surfaces, organized by workflow state
 * (new/acknowledged/dismissed) rather than by research cycle. Deliberately
 * not a second Morning Brief: this page never computes or displays a
 * research-cycle boundary — "new" here means "not yet acknowledged or
 * dismissed," a completely different axis from the Brief's "new in the
 * latest research cycle vs. the preceding one."
 */
export function AlertsPage(): ReactElement {
  const [searchParams, setSearchParams] = useSearchParams();
  const summaryQuery = useAlertsSummary();
  const universesQuery = useResearchUniverses();
  const watchlistsQuery = useWatchlists();
  const acknowledgeMutation = useAcknowledgeAlert();
  const dismissMutation = useDismissAlert();

  const status = (searchParams.get("status") as AlertStatus | null) ?? undefined;
  const severity = (searchParams.get("severity") as EvidenceSeverity | null) ?? undefined;
  const watchlistId = searchParams.get("watchlist") ?? undefined;
  const universeId = searchParams.get("universe") ?? undefined;
  const detectionMethod = (searchParams.get("detection") as DetectionMethod | null) ?? undefined;
  const issuerId = searchParams.get("issuer") ?? undefined;
  const page = Number(searchParams.get("page") ?? "1");
  const pageSize = Number(searchParams.get("pageSize") ?? "25");

  function updateParams(updates: Record<string, string | null>): void {
    const next = new URLSearchParams(searchParams);
    for (const [key, value] of Object.entries(updates)) {
      if (value === null || value === "") {
        next.delete(key);
      } else {
        next.set(key, value);
      }
    }
    if (!("page" in updates)) next.set("page", "1");
    setSearchParams(next, { replace: true });
  }

  const alertsQuery = useAlerts({
    status,
    severity,
    watchlistId,
    universeId,
    detectionMethod,
    issuerId,
    page,
    pageSize,
  });

  // Issuer filter: an Autocomplete searching only issuers with alerts
  // (Milestone 9's `/api/alerts/issuers`), pre-populated with the current
  // issuer's name when arriving via a URL that already carries `issuer`
  // (e.g. Issuer Detail's "View Alerts for this issuer" link).
  const [issuerInput, setIssuerInput] = useState("");
  const debouncedIssuerInput = useDebouncedValue(issuerInput, 300);
  const issuerSearchQuery = useAlertIssuerSearch(debouncedIssuerInput);
  const currentIssuerQuery = useIssuerDetail(issuerId);
  const [selectedIssuer, setSelectedIssuer] = useState<AlertIssuerSearchResult | null>(null);

  useEffect(() => {
    if (issuerId && currentIssuerQuery.data && currentIssuerQuery.data.issuer_id === issuerId) {
      setSelectedIssuer({
        issuer_id: currentIssuerQuery.data.issuer_id,
        issuer_legal_name: currentIssuerQuery.data.legal_name,
        issuer_ticker: currentIssuerQuery.data.ticker,
      });
    }
    if (!issuerId) setSelectedIssuer(null);
  }, [issuerId, currentIssuerQuery.data]);

  const selectedWatchlistName = watchlistsQuery.data?.watchlists.find(
    (w) => w.id === watchlistId,
  )?.name;

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h4" gutterBottom>
          Alerts
        </Typography>
        <Typography variant="body1" color="text.secondary">
          The research alerts that need your review — reused from the same evidence-backed
          intelligence as the Morning Research Brief, organized as a review inbox rather than a
          research-cycle digest. "New" below means not yet acknowledged or dismissed, not "new this
          research cycle" — see the Morning Research Brief for that view.
        </Typography>
      </Box>

      <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap>
        <SummaryTile label="New" value={summaryQuery.data?.new_count ?? 0} />
        <SummaryTile
          label="High Severity"
          value={summaryQuery.data?.high_severity_count ?? 0}
          color="error.main"
        />
        <SummaryTile
          label="Watchlist Alerts"
          value={summaryQuery.data?.watchlist_alert_count ?? 0}
          color="warning.main"
        />
        <SummaryTile label="Acknowledged" value={summaryQuery.data?.acknowledged_count ?? 0} />
      </Stack>

      <Paper variant="outlined" sx={{ p: 2 }}>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={2} flexWrap="wrap" useFlexGap>
          <TextField
            label="Status"
            select
            size="small"
            value={status ?? ""}
            onChange={(e) => updateParams({ status: e.target.value || null })}
            sx={{ width: { xs: "100%", sm: 150 } }}
          >
            <MenuItem value="">All statuses</MenuItem>
            <MenuItem value="new">New</MenuItem>
            <MenuItem value="acknowledged">Acknowledged</MenuItem>
            <MenuItem value="dismissed">Dismissed</MenuItem>
          </TextField>
          <TextField
            label="Severity"
            select
            size="small"
            value={severity ?? ""}
            onChange={(e) => updateParams({ severity: e.target.value || null })}
            sx={{ width: { xs: "100%", sm: 140 } }}
          >
            <MenuItem value="">All severities</MenuItem>
            <MenuItem value="high">High</MenuItem>
            <MenuItem value="medium">Medium</MenuItem>
            <MenuItem value="low">Low</MenuItem>
          </TextField>
          <TextField
            label="Watchlist"
            select
            size="small"
            value={watchlistId ?? ""}
            onChange={(e) => updateParams({ watchlist: e.target.value || null })}
            sx={{ width: { xs: "100%", sm: 200 } }}
          >
            <MenuItem value="">All Watchlists</MenuItem>
            {watchlistsQuery.data?.watchlists.map((watchlist) => (
              <MenuItem key={watchlist.id} value={watchlist.id}>
                {watchlist.name}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            label="Research Universe"
            select
            size="small"
            value={universeId ?? ""}
            onChange={(e) => updateParams({ universe: e.target.value || null })}
            sx={{ width: { xs: "100%", sm: 200 } }}
          >
            <MenuItem value="">All universes</MenuItem>
            {universesQuery.data?.universes.map((universe) => (
              <MenuItem key={universe.id} value={universe.id}>
                {universe.name}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            label="Detection"
            select
            size="small"
            value={detectionMethod ?? ""}
            onChange={(e) => updateParams({ detection: e.target.value || null })}
            sx={{ width: { xs: "100%", sm: 160 } }}
          >
            <MenuItem value="">Deterministic + AI-assisted</MenuItem>
            <MenuItem value="deterministic">Deterministic only</MenuItem>
            <MenuItem value="ai_assisted">AI-assisted only</MenuItem>
          </TextField>
          <Autocomplete
            size="small"
            sx={{ width: { xs: "100%", sm: 260 } }}
            options={issuerSearchQuery.data?.issuers ?? []}
            getOptionLabel={(option) =>
              option.issuer_ticker
                ? `${option.issuer_legal_name} (${option.issuer_ticker})`
                : option.issuer_legal_name
            }
            isOptionEqualToValue={(option, value) => option.issuer_id === value.issuer_id}
            value={selectedIssuer}
            onChange={(_e, value) => {
              setSelectedIssuer(value);
              updateParams({ issuer: value?.issuer_id ?? null });
            }}
            onInputChange={(_e, value) => setIssuerInput(value)}
            loading={issuerSearchQuery.isLoading}
            renderInput={(params) => <TextField {...params} label="Issuer search" />}
          />
        </Stack>
        {watchlistId && selectedWatchlistName && (
          <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: "block" }}>
            Showing alerts for issuers on "{selectedWatchlistName}"
          </Typography>
        )}
      </Paper>

      {alertsQuery.isLoading && (
        <Box sx={{ py: 4, textAlign: "center" }}>
          <CircularProgress />
        </Box>
      )}
      {alertsQuery.isError && (
        <Alert severity="error">
          Could not load alerts:{" "}
          {alertsQuery.error instanceof Error ? alertsQuery.error.message : "unknown error"}
        </Alert>
      )}
      {alertsQuery.data && alertsQuery.data.alerts.length === 0 && (
        <Alert severity="success">No alerts match these filters — nothing to review.</Alert>
      )}

      <Stack spacing={2}>
        {alertsQuery.data?.alerts.map((alert) => (
          <AlertCard
            key={alert.id}
            alert={alert}
            onAcknowledge={(alertId) => acknowledgeMutation.mutate({ alertId })}
            onDismiss={(alertId, reason) => dismissMutation.mutate({ alertId, reason })}
          />
        ))}
      </Stack>

      {alertsQuery.data && alertsQuery.data.total > 0 && (
        <TablePagination
          component="div"
          count={alertsQuery.data.total}
          page={page - 1}
          rowsPerPage={pageSize}
          rowsPerPageOptions={[10, 25, 50, 100]}
          onPageChange={(_e, newPage) => updateParams({ page: String(newPage + 1) })}
          onRowsPerPageChange={(e) => updateParams({ pageSize: e.target.value, page: "1" })}
        />
      )}
    </Stack>
  );
}
