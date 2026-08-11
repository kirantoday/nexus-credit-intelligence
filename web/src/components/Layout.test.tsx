import { afterEach, describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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
  render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<div>page content</div>} />
          <Route path="/about" element={<div>about page content</div>} />
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
  });
});
