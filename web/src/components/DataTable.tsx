import type { ReactElement } from "react";
import {
  type ColumnDef,
  type OnChangeFn,
  type SortingState,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import {
  Box,
  CircularProgress,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TableSortLabel,
  Typography,
} from "@mui/material";

/**
 * A TanStack Table wrapper for dense, institutional data grids (Credit
 * Universe and similar screens — PLAN.md section 17). Sorting is always
 * server-driven here (`manualSorting`): this component renders whatever page
 * of data it's given and reports sort-header clicks back via
 * `onSortingChange`, it never re-sorts client-side. Pagination and filtering
 * controls live in the calling page, not here, so this stays a plain,
 * reusable table renderer rather than a full data-grid replacement.
 */
export interface DataTableProps<T> {
  data: T[];
  // TanStack Table's own ColumnDef is generic over each column's value type,
  // which varies per column; callers get full inference on each column
  // definition they pass in, this container type just can't narrow it further.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  columns: ColumnDef<T, any>[];
  sorting: SortingState;
  onSortingChange: OnChangeFn<SortingState>;
  isLoading: boolean;
  isError: boolean;
  errorMessage?: string;
  emptyMessage: string;
  getRowId?: (row: T) => string;
}

export function DataTable<T>({
  data,
  columns,
  sorting,
  onSortingChange,
  isLoading,
  isError,
  errorMessage,
  emptyMessage,
  getRowId,
}: DataTableProps<T>): ReactElement {
  const table = useReactTable({
    data,
    columns,
    state: { sorting },
    onSortingChange,
    getCoreRowModel: getCoreRowModel(),
    manualSorting: true,
    getRowId,
  });

  if (isError) {
    return (
      <Box sx={{ py: 6, textAlign: "center" }}>
        <Typography color="error">
          {errorMessage ?? "Something went wrong loading this data."}
        </Typography>
      </Box>
    );
  }

  return (
    <TableContainer sx={{ position: "relative" }}>
      {isLoading && (
        <Box
          sx={{
            position: "absolute",
            inset: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            backgroundColor: "rgba(255, 255, 255, 0.6)",
            zIndex: 1,
          }}
        >
          <CircularProgress size={32} />
        </Box>
      )}
      <Table size="small" stickyHeader>
        <TableHead>
          {table.getHeaderGroups().map((headerGroup) => (
            <TableRow key={headerGroup.id}>
              {headerGroup.headers.map((header) => {
                const canSort = header.column.getCanSort();
                const sortDirection = header.column.getIsSorted();
                return (
                  <TableCell key={header.id}>
                    {header.isPlaceholder ? null : canSort ? (
                      <TableSortLabel
                        active={sortDirection !== false}
                        direction={sortDirection || "asc"}
                        onClick={header.column.getToggleSortingHandler()}
                      >
                        {flexRender(header.column.columnDef.header, header.getContext())}
                      </TableSortLabel>
                    ) : (
                      flexRender(header.column.columnDef.header, header.getContext())
                    )}
                  </TableCell>
                );
              })}
            </TableRow>
          ))}
        </TableHead>
        <TableBody>
          {data.length === 0 && !isLoading ? (
            <TableRow>
              <TableCell colSpan={columns.length} sx={{ py: 6, textAlign: "center" }}>
                <Typography color="text.secondary">{emptyMessage}</Typography>
              </TableCell>
            </TableRow>
          ) : (
            table.getRowModel().rows.map((row) => (
              <TableRow key={row.id} hover>
                {row.getVisibleCells().map((cell) => (
                  <TableCell key={cell.id}>
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </TableCell>
                ))}
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </TableContainer>
  );
}
