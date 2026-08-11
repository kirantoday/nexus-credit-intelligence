import { type ReactElement, useEffect, useMemo, useState } from "react";
import { Link as RouterLink, useSearchParams } from "react-router";
import type { ColumnDef, SortingState } from "@tanstack/react-table";
import {
  Alert,
  Box,
  Card,
  CardContent,
  Chip,
  Divider,
  Link,
  MenuItem,
  Paper,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import TablePagination from "@mui/material/TablePagination";
import { DataTable } from "../components/DataTable";
import { MarketContextPanel } from "../components/MarketContextPanel";
import { ProvenanceBadge } from "../components/ProvenanceBadge";
import { useCreditUniverse } from "../queries/useCreditUniverse";
import { useResearchUniverse, useResearchUniverseIssuers } from "../queries/useResearchUniverses";
import type {
  CreditUniverseRow,
  CreditUniverseSortField,
  InstrumentType,
  SortDirection,
} from "../api/creditUniverse";
import { formatCompactCurrency, formatDate, formatOrDash, formatPercent } from "../lib/format";
import { useDebouncedValue } from "../lib/useDebouncedValue";

const SORTABLE_COLUMN_IDS: readonly CreditUniverseSortField[] = [
  "legal_name",
  "instrument_type",
  "maturity_date",
  "amount_outstanding",
  "coupon",
];

function isSortField(value: string): value is CreditUniverseSortField {
  return (SORTABLE_COLUMN_IDS as readonly string[]).includes(value);
}

const SENIORITY_LABEL: Record<string, string> = {
  first_lien: "1st Lien",
  second_lien: "2nd Lien",
  senior_unsecured: "Senior Unsecured",
  subordinated: "Subordinated",
  preferred: "Preferred",
  common: "Common",
};

function couponOrSpread(row: CreditUniverseRow): string {
  if (row.coupon !== null) return formatPercent(row.coupon);
  if (row.spread !== null) return `${row.benchmark ?? ""}+${formatPercent(row.spread)}`.trim();
  return "—";
}

/**
 * Mobile equivalent of the desktop table's row — same fields, highest-value
 * first (issuer, then instrument), never fewer fields than the desktop
 * table shows (PLAN.md CFO-demo mobile-polish pass §2: "Do not remove data
 * merely to make the layout fit").
 */
function MobileSecurityCard({ row }: { row: CreditUniverseRow }): ReactElement {
  return (
    <Card variant="outlined">
      <CardContent sx={{ p: 1.5, "&:last-child": { pb: 1.5 } }}>
        <Link
          component={RouterLink}
          to={`/issuers/${row.issuer_id}`}
          underline="hover"
          color="inherit"
        >
          <Typography variant="body2" fontWeight={700}>
            {row.issuer_legal_name}
          </Typography>
        </Link>
        {row.issuer_ticker && (
          <Typography variant="caption" color="text.secondary" display="block">
            {row.issuer_ticker}
          </Typography>
        )}
        <Typography variant="body2" sx={{ mt: 0.5 }}>
          {row.description}
        </Typography>

        <Stack
          direction="row"
          spacing={1}
          alignItems="center"
          flexWrap="wrap"
          useFlexGap
          sx={{ mt: 1 }}
        >
          <Chip
            label={row.instrument_type}
            size="small"
            color={row.instrument_type === "bond" ? "primary" : "secondary"}
            variant="outlined"
          />
          {row.seniority && (
            <Typography variant="caption" color="text.secondary">
              {SENIORITY_LABEL[row.seniority] ?? row.seniority}
            </Typography>
          )}
          <Typography variant="caption" color="text.secondary">
            {row.secured === null ? "—" : row.secured ? "Secured" : "Unsecured"}
          </Typography>
        </Stack>

        <Divider sx={{ my: 1 }} />

        <Stack spacing={0.5}>
          <Stack direction="row" justifyContent="space-between">
            <Typography variant="caption" color="text.secondary">
              Maturity
            </Typography>
            <Typography variant="body2">{formatDate(row.maturity_date)}</Typography>
          </Stack>
          <Stack direction="row" justifyContent="space-between">
            <Typography variant="caption" color="text.secondary">
              Amount Outstanding
            </Typography>
            <Typography variant="body2">{formatCompactCurrency(row.amount_outstanding)}</Typography>
          </Stack>
          <Stack direction="row" justifyContent="space-between">
            <Typography variant="caption" color="text.secondary">
              Coupon / Spread
            </Typography>
            <Typography variant="body2">{couponOrSpread(row)}</Typography>
          </Stack>
        </Stack>

        <Stack direction="row" justifyContent="flex-end" sx={{ mt: 1 }}>
          <ProvenanceBadge
            provider={row.provider}
            asOfDate={row.as_of_date}
            retrievedAt={row.retrieved_at}
            freshness={row.freshness}
          />
        </Stack>
      </CardContent>
    </Card>
  );
}

export function CreditUniversePage(): ReactElement {
  const [searchParams, setSearchParams] = useSearchParams();

  const instrumentType = (searchParams.get("type") as InstrumentType | null) ?? undefined;
  const universeId = searchParams.get("universe") ?? undefined;
  const page = Number(searchParams.get("page") ?? "1");
  const pageSize = Number(searchParams.get("pageSize") ?? "25");
  const sortByParam = searchParams.get("sortBy");
  const sortBy: CreditUniverseSortField =
    sortByParam && isSortField(sortByParam) ? sortByParam : "legal_name";
  const sortDir = (searchParams.get("sortDir") as SortDirection | null) ?? "asc";

  // Milestone 6.5 (PLAN.md 24.9): clicking a Research Universe opens Credit
  // Universe pre-filtered to it via this `universe` URL param.
  const universeQuery = useResearchUniverse(universeId);
  // Milestone 7.5.3 CFO-demo fix: Research Universe membership is
  // issuer-level, Credit Universe is security-level — a universe can have
  // real issuer members that simply have no securities loaded yet (e.g. no
  // OpenFIGI match). That is a legitimate state, not a bug, but the
  // generic "No securities in the Credit Universe yet" message reads as
  // one. Only fetched when a universe filter is active, so this costs
  // nothing on the normal unfiltered page.
  const universeIssuersQuery = useResearchUniverseIssuers(universeId);

  function updateParams(updates: Record<string, string | null>): void {
    const next = new URLSearchParams(searchParams);
    for (const [key, value] of Object.entries(updates)) {
      if (value === null || value === "") {
        next.delete(key);
      } else {
        next.set(key, value);
      }
    }
    setSearchParams(next, { replace: true });
  }

  // The search box keeps its own local state so every keystroke is
  // instantly responsive. Driving it directly from the URL search param (as
  // every other filter does) loses keystrokes: each change re-renders with
  // a new controlled `value` before the next keypress lands, effectively
  // resetting the field mid-typing. The debounced value is what actually
  // drives the query and the URL, so typing doesn't fire a request (or a
  // history entry) per character either.
  const [searchInput, setSearchInput] = useState(() => searchParams.get("q") ?? "");
  const debouncedSearch = useDebouncedValue(searchInput, 300);

  useEffect(() => {
    updateParams({ q: debouncedSearch || null, page: "1" });
    // Deliberately only re-runs when the debounced value changes — including
    // `updateParams`/`searchParams` here would re-fire on every unrelated
    // filter change too, since updateParams closes over searchParams.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedSearch]);

  const { data, isLoading, isFetching, isError, error } = useCreditUniverse({
    search: debouncedSearch || undefined,
    instrumentType,
    universeId,
    sortBy,
    sortDir,
    page,
    pageSize,
  });

  const sorting: SortingState = [{ id: sortBy, desc: sortDir === "desc" }];

  // eslint-disable-next-line @typescript-eslint/no-explicit-any -- see DataTable.tsx's DataTableProps.columns
  const columns = useMemo<ColumnDef<CreditUniverseRow, any>[]>(
    () => [
      {
        id: "legal_name",
        header: "Issuer",
        accessorFn: (row) => row.issuer_legal_name,
        cell: ({ row }) => (
          <Box>
            <Link
              component={RouterLink}
              to={`/issuers/${row.original.issuer_id}`}
              underline="hover"
              color="inherit"
            >
              <Typography variant="body2" fontWeight={600}>
                {row.original.issuer_legal_name}
              </Typography>
            </Link>
            {row.original.issuer_ticker && (
              <Typography variant="caption" color="text.secondary">
                {row.original.issuer_ticker}
              </Typography>
            )}
          </Box>
        ),
      },
      {
        id: "description",
        header: "Instrument",
        accessorFn: (row) => row.description,
        enableSorting: false,
        cell: ({ row }) => <Typography variant="body2">{row.original.description}</Typography>,
      },
      {
        id: "instrument_type",
        header: "Type",
        accessorFn: (row) => row.instrument_type,
        cell: ({ row }) => (
          <Stack spacing={0.5} alignItems="flex-start">
            <Chip
              label={row.original.instrument_type}
              size="small"
              color={row.original.instrument_type === "bond" ? "primary" : "secondary"}
              variant="outlined"
            />
            {row.original.seniority && (
              <Typography variant="caption" color="text.secondary">
                {SENIORITY_LABEL[row.original.seniority] ?? row.original.seniority}
              </Typography>
            )}
          </Stack>
        ),
      },
      {
        id: "secured",
        header: "Secured",
        enableSorting: false,
        accessorFn: (row) => row.secured,
        cell: ({ row }) =>
          row.original.secured === null ? "—" : row.original.secured ? "Secured" : "Unsecured",
      },
      {
        id: "maturity_date",
        header: "Maturity",
        accessorFn: (row) => row.maturity_date,
        cell: ({ row }) => formatDate(row.original.maturity_date),
      },
      {
        id: "amount_outstanding",
        header: "Amount Outstanding",
        accessorFn: (row) => row.amount_outstanding,
        cell: ({ row }) => formatCompactCurrency(row.original.amount_outstanding),
      },
      {
        id: "coupon",
        header: "Coupon / Spread",
        accessorFn: (row) => row.coupon ?? row.spread,
        cell: ({ row }) => {
          const { coupon, spread, benchmark } = row.original;
          if (coupon !== null) return formatPercent(coupon);
          if (spread !== null) return `${benchmark ?? ""}+${formatPercent(spread)}`.trim();
          return "—";
        },
      },
      {
        id: "benchmark_rate",
        header: "Current Benchmark Rate",
        enableSorting: false,
        accessorFn: (row) => row.benchmark_rate,
        cell: ({ row }) => {
          const { benchmark, benchmark_rate, benchmark_rate_as_of_date } = row.original;
          if (benchmark_rate === null) return "—";
          return (
            <Tooltip
              title={`Source: FRED (${benchmark}) · As of ${formatDate(benchmark_rate_as_of_date)}`}
            >
              <span>{formatPercent(benchmark_rate)}</span>
            </Tooltip>
          );
        },
      },
      {
        id: "sector",
        header: "Sector",
        enableSorting: false,
        accessorFn: (row) => row.issuer_sector,
        cell: ({ row }) => formatOrDash(row.original.issuer_sector),
      },
      {
        id: "source",
        header: "Source",
        enableSorting: false,
        accessorFn: (row) => row.provider,
        cell: ({ row }) => (
          <ProvenanceBadge
            provider={row.original.provider}
            asOfDate={row.original.as_of_date}
            retrievedAt={row.original.retrieved_at}
            freshness={row.original.freshness}
          />
        ),
      },
    ],
    [],
  );

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h4" gutterBottom>
          Credit Universe
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Every bond and loan Nexus currently tracks — real issuer and instrument data with source
          provenance.
        </Typography>
      </Box>

      <MarketContextPanel />

      {universeId && (
        <Chip
          label={`Universe: ${universeQuery.data?.name ?? "…"}`}
          onDelete={() => updateParams({ universe: null, page: "1" })}
          color="primary"
          variant="outlined"
          sx={{ alignSelf: "flex-start" }}
        />
      )}

      <Paper variant="outlined" sx={{ p: 2 }}>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={2} alignItems={{ sm: "center" }}>
          <TextField
            label="Search issuer or instrument"
            size="small"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            sx={{ width: { xs: "100%", sm: 280 } }}
          />
          <TextField
            label="Instrument type"
            select
            size="small"
            value={instrumentType ?? ""}
            onChange={(e) => updateParams({ type: e.target.value || null, page: "1" })}
            sx={{ width: { xs: "100%", sm: 160 } }}
          >
            <MenuItem value="">All types</MenuItem>
            <MenuItem value="bond">Bond</MenuItem>
            <MenuItem value="loan">Loan</MenuItem>
            <MenuItem value="equity">Equity</MenuItem>
          </TextField>
        </Stack>
      </Paper>

      {isError && (
        <Alert severity="error">
          Could not load the Credit Universe:{" "}
          {error instanceof Error ? error.message : "unknown error"}
        </Alert>
      )}

      {universeId &&
        data &&
        data.total === 0 &&
        !isLoading &&
        !isFetching &&
        !debouncedSearch &&
        !instrumentType &&
        (universeIssuersQuery.data ? (
          universeIssuersQuery.data.issuers.length === 0 ? (
            <Alert severity="info">
              {universeQuery.data?.name ?? "This Research Universe"} has no issuer members yet.
            </Alert>
          ) : (
            <Alert severity="info">
              <Typography variant="body2" gutterBottom>
                {universeIssuersQuery.data.issuers.length} issuer
                {universeIssuersQuery.data.issuers.length === 1 ? "" : "s"} belong
                {universeIssuersQuery.data.issuers.length === 1 ? "s" : ""} to{" "}
                <strong>{universeQuery.data?.name ?? "this Research Universe"}</strong>, but Nexus
                currently has no securities loaded for{" "}
                {universeIssuersQuery.data.issuers.length === 1 ? "this issuer" : "these issuers"}.
              </Typography>
              <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap>
                {universeIssuersQuery.data.issuers.map((issuer) => (
                  <Link
                    key={issuer.issuer_id}
                    component={RouterLink}
                    to={`/issuers/${issuer.issuer_id}`}
                    underline="hover"
                  >
                    {issuer.issuer_legal_name}
                    {issuer.issuer_ticker ? ` (${issuer.issuer_ticker})` : ""}
                  </Link>
                ))}
              </Stack>
            </Alert>
          )
        ) : null)}

      <Paper variant="outlined">
        <DataTable
          data={data?.rows ?? []}
          columns={columns}
          renderMobileCard={(row) => <MobileSecurityCard row={row} />}
          sorting={sorting}
          onSortingChange={(updater) => {
            const next = typeof updater === "function" ? updater(sorting) : updater;
            const nextSort = next[0];
            if (!nextSort) return;
            updateParams({
              sortBy: nextSort.id,
              sortDir: nextSort.desc ? "desc" : "asc",
              page: "1",
            });
          }}
          isLoading={isLoading || isFetching}
          isError={isError}
          emptyMessage={
            debouncedSearch || instrumentType
              ? "No securities match these filters."
              : universeId
                ? "No securities for this Research Universe's members."
                : "No securities in the Credit Universe yet."
          }
        />
        {data && (
          <TablePagination
            component="div"
            count={data.total}
            page={page - 1}
            rowsPerPage={pageSize}
            rowsPerPageOptions={[10, 25, 50, 100]}
            onPageChange={(_e, newPage) => updateParams({ page: String(newPage + 1) })}
            onRowsPerPageChange={(e) => updateParams({ pageSize: e.target.value, page: "1" })}
          />
        )}
      </Paper>
    </Stack>
  );
}
