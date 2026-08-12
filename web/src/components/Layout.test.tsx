import { afterEach, describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router";
import { Layout } from "./Layout";

/** Forces `useIsMobile` (MUI `useMediaQuery(theme.breakpoints.down("md"))`)
 * to report a match, simulating a phone/tablet viewport — the default
 * `src/test/setup.ts` mock always reports "no match" (desktop). Restored
 * automatically after each test. */
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

function renderLayout(initialPath = "/"): void {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<div>page content</div>} />
            <Route path="/about" element={<div>about page content</div>} />
            <Route path="/research-notes" element={<div>research notes page content</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Layout", () => {
  it("shows a 'Watchlists' navigation item positioned after Morning Research Brief", () => {
    renderLayout();

    const links = screen.getAllByRole("link");
    const labels = links.map((link) => link.textContent);

    expect(labels).toContain("Watchlists");
    expect(labels.indexOf("Watchlists")).toBe(labels.indexOf("Morning Research Brief") + 1);

    expect(screen.getByRole("link", { name: "Watchlists" })).toHaveAttribute("href", "/watchlists");
  });

  it("shows an 'Alerts' navigation item positioned after Watchlists", () => {
    renderLayout();

    const links = screen.getAllByRole("link");
    const labels = links.map((link) => link.textContent);

    expect(labels).toContain("Alerts");
    expect(labels.indexOf("Alerts")).toBe(labels.indexOf("Watchlists") + 1);

    expect(screen.getByRole("link", { name: "Alerts" })).toHaveAttribute("href", "/alerts");
  });

  it("shows a 'Research Notes' navigation item positioned after Alerts", () => {
    renderLayout();

    const links = screen.getAllByRole("link");
    const labels = links.map((link) => link.textContent);

    expect(labels).toContain("Research Notes");
    expect(labels.indexOf("Research Notes")).toBe(labels.indexOf("Alerts") + 1);

    expect(screen.getByRole("link", { name: "Research Notes" })).toHaveAttribute(
      "href",
      "/research-notes",
    );
  });

  it("shows a 'Search' navigation item positioned after Research Notes", () => {
    renderLayout();

    const links = screen.getAllByRole("link");
    const labels = links.map((link) => link.textContent);

    expect(labels.indexOf("Search")).toBe(labels.indexOf("Research Notes") + 1);
    expect(screen.getByRole("link", { name: "Search" })).toHaveAttribute("href", "/search");
  });

  it("shows an 'About Nexus' navigation item positioned last, after Search", () => {
    renderLayout();

    const links = screen.getAllByRole("link");
    const labels = links.map((link) => link.textContent);

    expect(labels).toContain("About Nexus");
    expect(labels.indexOf("About Nexus")).toBe(labels.indexOf("Search") + 1);

    expect(screen.getByRole("link", { name: "About Nexus" })).toHaveAttribute("href", "/about");
  });

  it("does not show not-yet-built nav items", () => {
    renderLayout();

    expect(screen.queryByText("Research Workspace")).not.toBeInTheDocument();
    expect(screen.queryByText("Research Assistant")).not.toBeInTheDocument();
    expect(screen.queryByText("Dashboard")).not.toBeInTheDocument();
  });

  it("renders the GlobalSearch input in the header", () => {
    renderLayout();

    expect(screen.getByRole("textbox", { name: "Search Nexus" })).toBeInTheDocument();
  });

  it("marks the current page's nav item as selected", () => {
    renderLayout("/about");

    const aboutLink = screen.getByRole("link", { name: "About Nexus" });
    expect(aboutLink).toHaveClass("Mui-selected");
    const creditUniverseLink = screen.getByRole("link", { name: "Credit Universe" });
    expect(creditUniverseLink).not.toHaveClass("Mui-selected");
  });

  describe("on a mobile viewport", () => {
    it("shows a hamburger menu button that opens the navigation drawer", async () => {
      mockMobileViewport();
      const user = userEvent.setup();
      renderLayout();

      // The drawer is a temporary (closed-by-default) overlay on mobile —
      // its nav items aren't reachable until the menu button opens it.
      const menuButton = screen.getByRole("button", { name: /open navigation menu/i });
      expect(menuButton).toBeInTheDocument();

      await user.click(menuButton);

      const dialog = screen.getByRole("presentation");
      expect(within(dialog).getByRole("link", { name: "Credit Universe" })).toBeInTheDocument();
    });

    it("closes the drawer after navigating to a page", async () => {
      mockMobileViewport();
      const user = userEvent.setup();
      renderLayout();

      await user.click(screen.getByRole("button", { name: /open navigation menu/i }));
      const dialog = screen.getByRole("presentation");
      await user.click(within(dialog).getByRole("link", { name: "About Nexus" }));

      expect(screen.getByText("about page content")).toBeInTheDocument();
    });

    it("shows and navigates to Research Notes from the mobile drawer", async () => {
      mockMobileViewport();
      const user = userEvent.setup();
      renderLayout();

      await user.click(screen.getByRole("button", { name: /open navigation menu/i }));
      const dialog = screen.getByRole("presentation");
      const researchNotesLink = within(dialog).getByRole("link", { name: "Research Notes" });
      expect(researchNotesLink).toHaveAttribute("href", "/research-notes");

      await user.click(researchNotesLink);

      expect(screen.getByText("research notes page content")).toBeInTheDocument();
    });
  });
});
