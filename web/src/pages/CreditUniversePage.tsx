import { type ReactElement, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router";
import type { ColumnDef, SortingState } from "@tanstack/react-table";
import {
  Alert,
  Box,
  Chip,
  MenuItem,
  Paper,
  Stack,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Typography,
} from "@mui/material";
import TablePagination from "@mui/material/TablePagination";
import { DataTable } from "../components/DataTable";
import { MarketContextPanel } from "../components/MarketContextPanel";
import { ProvenanceBadge } from "../components/ProvenanceBadge";
import { SyntheticDataBadge } from "../components/SyntheticDataBadge";
import { useCreditUniverse } from "../queries/useCreditUniverse";
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

export function CreditUniversePage(): ReactElement {
  const [searchParams, setSearchParams] = useSearchParams();

  const instrumentType = (searchParams.get("type") as InstrumentType | null) ?? undefined;
  const syntheticFilter = searchParams.get("synthetic") as "all" | "real" | "synthetic" | null;
  const page = Number(searchParams.get("page") ?? "1");
  const pageSize = Number(searchParams.get("pageSize") ?? "25");
  const sortByParam = searchParams.get("sortBy");
  const sortBy: CreditUniverseSortField =
    sortByParam && isSortField(sortByParam) ? sortByParam : "legal_name";
  const sortDir = (searchParams.get("sortDir") as SortDirection | null) ?? "asc";

  const isSynthetic =
    syntheticFilter === "real" ? false : syntheticFilter === "synthetic" ? true : undefined;

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
    isSynthetic,
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
            <Typography variant="body2" fontWeight={600}>
              {row.original.issuer_legal_name}
            </Typography>
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
          <Stack direction="row" spacing={1} alignItems="center">
            <ProvenanceBadge
              provider={row.original.provider}
              asOfDate={row.original.as_of_date}
              retrievedAt={row.original.retrieved_at}
              freshness={row.original.freshness}
            />
            <SyntheticDataBadge
              isSynthetic={row.original.is_synthetic}
              reason={row.original.synthetic_reason}
            />
          </Stack>
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
          Every bond and loan Nexus currently tracks — real issuer data sourced from SEC EDGAR,
          synthetic loan positions clearly labeled. Every value carries provenance.
        </Typography>
      </Box>

      <MarketContextPanel />

      <Paper variant="outlined" sx={{ p: 2 }}>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={2} alignItems={{ sm: "center" }}>
          <TextField
            label="Search issuer or instrument"
            size="small"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            sx={{ minWidth: 280 }}
          />
          <TextField
            label="Instrument type"
            select
            size="small"
            value={instrumentType ?? ""}
            onChange={(e) => updateParams({ type: e.target.value || null, page: "1" })}
            sx={{ minWidth: 160 }}
          >
            <MenuItem value="">All types</MenuItem>
            <MenuItem value="bond">Bond</MenuItem>
            <MenuItem value="loan">Loan</MenuItem>
            <MenuItem value="equity">Equity</MenuItem>
          </TextField>
          <ToggleButtonGroup
            size="small"
            exclusive
            value={syntheticFilter ?? "all"}
            onChange={(_e, value) => {
              if (value !== null)
                updateParams({ synthetic: value === "all" ? null : value, page: "1" });
            }}
          >
            <ToggleButton value="all">All data</ToggleButton>
            <ToggleButton value="real">Real only</ToggleButton>
            <ToggleButton value="synthetic">Synthetic only</ToggleButton>
          </ToggleButtonGroup>
        </Stack>
      </Paper>

      {isError && (
        <Alert severity="error">
          Could not load the Credit Universe:{" "}
          {error instanceof Error ? error.message : "unknown error"}
        </Alert>
      )}

      <Paper variant="outlined">
        <DataTable
          data={data?.rows ?? []}
          columns={columns}
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
            debouncedSearch || instrumentType || syntheticFilter
              ? "No securities match these filters."
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
