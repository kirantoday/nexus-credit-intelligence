import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ColumnDef } from "@tanstack/react-table";
import { DataTable } from "./DataTable";

interface Row {
  id: string;
  name: string;
}

const columns: ColumnDef<Row, string>[] = [
  { id: "name", header: "Name", accessorFn: (row) => row.name },
];

/** Forces `useIsMobile` (MUI `useMediaQuery(theme.breakpoints.down("md"))`)
 * to report a match, simulating a phone/tablet viewport for one test —
 * `src/test/setup.ts`'s default mock always reports "no match" (desktop).
 * Restored automatically after each test via the `afterEach` below. */
function mockMobileViewport(): void {
  window.matchMedia = (query: string) =>
    ({
      matches: true,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }) as MediaQueryList;
}

const originalMatchMedia = window.matchMedia;
afterEach(() => {
  window.matchMedia = originalMatchMedia;
});

describe("DataTable", () => {
  it("renders a row per data item", () => {
    const data: Row[] = [
      { id: "1", name: "Apple Inc." },
      { id: "2", name: "Ridgeline Industrial Holdings LLC" },
    ];
    render(
      <DataTable
        data={data}
        columns={columns}
        sorting={[]}
        onSortingChange={() => {}}
        isLoading={false}
        isError={false}
        emptyMessage="No rows"
      />,
    );
    expect(screen.getByText("Apple Inc.")).toBeInTheDocument();
    expect(screen.getByText("Ridgeline Industrial Holdings LLC")).toBeInTheDocument();
  });

  it("shows the empty message when there is no data and it isn't loading", () => {
    render(
      <DataTable
        data={[]}
        columns={columns}
        sorting={[]}
        onSortingChange={() => {}}
        isLoading={false}
        isError={false}
        emptyMessage="No securities in the Credit Universe yet."
      />,
    );
    expect(screen.getByText("No securities in the Credit Universe yet.")).toBeInTheDocument();
  });

  it("shows the error message instead of the table when isError is true", () => {
    render(
      <DataTable
        data={[]}
        columns={columns}
        sorting={[]}
        onSortingChange={() => {}}
        isLoading={false}
        isError={true}
        errorMessage="Could not reach the backend"
        emptyMessage="No rows"
      />,
    );
    expect(screen.getByText("Could not reach the backend")).toBeInTheDocument();
    expect(screen.queryByText("No rows")).not.toBeInTheDocument();
  });

  it("calls onSortingChange when a sortable header is clicked", async () => {
    const user = userEvent.setup();
    const onSortingChange = vi.fn();
    render(
      <DataTable
        data={[{ id: "1", name: "Apple Inc." }]}
        columns={columns}
        sorting={[]}
        onSortingChange={onSortingChange}
        isLoading={false}
        isError={false}
        emptyMessage="No rows"
      />,
    );

    await user.click(screen.getByText("Name"));

    expect(onSortingChange).toHaveBeenCalledTimes(1);
  });

  it("does not render an empty-message row while loading with no data yet", () => {
    render(
      <DataTable
        data={[]}
        columns={columns}
        sorting={[]}
        onSortingChange={() => {}}
        isLoading={true}
        isError={false}
        emptyMessage="No rows"
      />,
    );
    expect(screen.queryByText("No rows")).not.toBeInTheDocument();
  });

  it("renders the desktop table (not mobile cards) when renderMobileCard is provided but the viewport isn't mobile", () => {
    render(
      <DataTable
        data={[{ id: "1", name: "Apple Inc." }]}
        columns={columns}
        renderMobileCard={(row) => <div data-testid="mobile-card">{row.name}</div>}
        sorting={[]}
        onSortingChange={() => {}}
        isLoading={false}
        isError={false}
        emptyMessage="No rows"
      />,
    );
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.queryByTestId("mobile-card")).not.toBeInTheDocument();
  });

  it("renders mobile cards instead of a table when renderMobileCard is provided on a mobile viewport", () => {
    mockMobileViewport();
    render(
      <DataTable
        data={[
          { id: "1", name: "Apple Inc." },
          { id: "2", name: "Ridgeline Industrial Holdings LLC" },
        ]}
        columns={columns}
        renderMobileCard={(row) => <div data-testid="mobile-card">{row.name}</div>}
        sorting={[]}
        onSortingChange={() => {}}
        isLoading={false}
        isError={false}
        emptyMessage="No rows"
      />,
    );
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(screen.getAllByTestId("mobile-card")).toHaveLength(2);
    expect(screen.getByText("Apple Inc.")).toBeInTheDocument();
  });

  it("still renders the desktop table on a mobile viewport when no renderMobileCard is given", () => {
    mockMobileViewport();
    render(
      <DataTable
        data={[{ id: "1", name: "Apple Inc." }]}
        columns={columns}
        sorting={[]}
        onSortingChange={() => {}}
        isLoading={false}
        isError={false}
        emptyMessage="No rows"
      />,
    );
    expect(screen.getByRole("table")).toBeInTheDocument();
  });

  it("shows the empty message in the mobile-card layout too when there is no data", () => {
    mockMobileViewport();
    render(
      <DataTable
        data={[]}
        columns={columns}
        renderMobileCard={(row) => <div data-testid="mobile-card">{row.name}</div>}
        sorting={[]}
        onSortingChange={() => {}}
        isLoading={false}
        isError={false}
        emptyMessage="No securities in the Credit Universe yet."
      />,
    );
    expect(screen.getByText("No securities in the Credit Universe yet.")).toBeInTheDocument();
  });
});
