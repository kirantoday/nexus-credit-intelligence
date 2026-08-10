import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { Layout } from "./Layout";

function renderLayout(): void {
  render(
    <MemoryRouter initialEntries={["/"]}>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<div>page content</div>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

describe("Layout", () => {
  it("shows an 'About Nexus' navigation item positioned after Morning Research Brief", () => {
    renderLayout();

    const links = screen.getAllByRole("link");
    const labels = links.map((link) => link.textContent);

    expect(labels).toContain("About Nexus");
    expect(labels.indexOf("About Nexus")).toBe(labels.indexOf("Morning Research Brief") + 1);

    expect(screen.getByRole("link", { name: "About Nexus" })).toHaveAttribute("href", "/about");
  });

  it("does not show not-yet-built nav items", () => {
    renderLayout();

    expect(screen.queryByText("Watchlists")).not.toBeInTheDocument();
    expect(screen.queryByText("Alerts")).not.toBeInTheDocument();
  });
});
