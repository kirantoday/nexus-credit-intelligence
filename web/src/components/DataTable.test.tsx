import { describe, expect, it, vi } from "vitest";
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
});
