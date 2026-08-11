import type { ReactElement, ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router";
import { WatchlistDetailPage } from "./WatchlistDetailPage";
import * as watchlistApi from "../api/watchlist";
import type { WatchlistDetailResponse, WatchlistIssuerRow } from "../api/watchlist";

/** Forces `useIsMobile` to report a match — mirrors the pattern already
 * established in `DataTable.test.tsx`/`Layout.test.tsx`. */
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

function renderWithProviders(watchlistId = "watchlist-1"): void {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  function Wrapper({ children }: { children: ReactNode }): ReactElement {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[`/watchlists/${watchlistId}`]}>{children}</MemoryRouter>
      </QueryClientProvider>
    );
  }
  render(
    <Routes>
      <Route path="/watchlists/:watchlistId" element={<WatchlistDetailPage />} />
    </Routes>,
    { wrapper: Wrapper },
  );
}

function makeIssuerRow(overrides: Partial<WatchlistIssuerRow> = {}): WatchlistIssuerRow {
  return {
    issuer_id: "issuer-1",
    issuer_legal_name: "Diebold Nixdorf, Incorporated",
    issuer_ticker: "DBD",
    current_status: ["Chapter 11"],
    latest_development_headline: "Filed for Chapter 11 protection",
    latest_development_date: "2026-06-01",
    severity: "high",
    new_developments_count: 2,
    securities_count: 4,
    rationale: "Tracking for restructuring outcome.",
    added_at: "2026-08-01T00:00:00Z",
    ...overrides,
  };
}

function makeDetail(
  overrides: Partial<WatchlistDetailResponse["watchlist"]> = {},
  issuers: WatchlistIssuerRow[] = [makeIssuerRow()],
): WatchlistDetailResponse {
  return {
    watchlist: {
      id: "watchlist-1",
      slug: "cfo-demo-watchlist",
      name: "CFO Demo Watchlist",
      description: "Curated for the CFO walkthrough.",
      issuer_count: issuers.length,
      issuers_with_new_developments: 1,
      high_severity_count: 1,
      new_alert_count: 1,
      high_severity_alert_count: 1,
      last_activity_at: "2026-08-10T00:00:00Z",
      created_at: "2026-08-01T00:00:00Z",
      updated_at: "2026-08-10T00:00:00Z",
      contains_issuer: null,
      ...overrides,
    },
    issuers,
  };
}

afterEach(() => {
  window.matchMedia = originalMatchMedia;
  vi.restoreAllMocks();
});

describe("WatchlistDetailPage", () => {
  it("renders the header summary and issuer table", async () => {
    vi.spyOn(watchlistApi, "fetchWatchlist").mockResolvedValue(makeDetail());

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText("CFO Demo Watchlist")).toBeInTheDocument();
    });
    expect(screen.getByText("Diebold Nixdorf, Incorporated")).toBeInTheDocument();
    expect(screen.getByText("Filed for Chapter 11 protection")).toBeInTheDocument();
    expect(screen.getByText("Chapter 11")).toBeInTheDocument();
  });

  it("shows a new-alerts count and a View Alerts link filtered to this Watchlist", async () => {
    vi.spyOn(watchlistApi, "fetchWatchlist").mockResolvedValue(makeDetail());

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText("CFO Demo Watchlist")).toBeInTheDocument();
    });
    expect(screen.getByText("new alerts")).toBeInTheDocument();
    const viewAlertsLink = screen.getByRole("link", { name: /View Alerts/ });
    expect(viewAlertsLink).toHaveAttribute("href", "/alerts?watchlist=watchlist-1");
  });

  it("shows an empty state when the Watchlist has no issuers", async () => {
    vi.spyOn(watchlistApi, "fetchWatchlist").mockResolvedValue(makeDetail({}, []));

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText(/No issuers on this Watchlist yet/)).toBeInTheDocument();
    });
  });

  it("shows a not-found message for an unknown Watchlist", async () => {
    const { ApiError } = await import("../api/client");
    vi.spyOn(watchlistApi, "fetchWatchlist").mockRejectedValue(
      new ApiError("Request failed with status 404", 404),
    );

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText("This Watchlist doesn't exist.")).toBeInTheDocument();
    });
  });

  it("navigates to Issuer Detail when clicking an issuer name", async () => {
    vi.spyOn(watchlistApi, "fetchWatchlist").mockResolvedValue(makeDetail());

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText("Diebold Nixdorf, Incorporated")).toBeInTheDocument();
    });
    const link = screen.getByRole("link", { name: "Diebold Nixdorf, Incorporated" });
    expect(link).toHaveAttribute("href", "/issuers/issuer-1");
  });

  it("removes an issuer from the Watchlist", async () => {
    vi.spyOn(watchlistApi, "fetchWatchlist").mockResolvedValue(makeDetail());
    const removeSpy = vi.spyOn(watchlistApi, "removeIssuerFromWatchlist").mockResolvedValue();
    const user = userEvent.setup();

    renderWithProviders();
    await waitFor(() => {
      expect(screen.getByText("Diebold Nixdorf, Incorporated")).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: "Remove from Watchlist" }));

    await waitFor(() => {
      expect(removeSpy).toHaveBeenCalledWith("watchlist-1", "issuer-1");
    });
  });

  it("renders mobile cards instead of a table on a mobile viewport", async () => {
    mockMobileViewport();
    vi.spyOn(watchlistApi, "fetchWatchlist").mockResolvedValue(makeDetail());

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText("Diebold Nixdorf, Incorporated")).toBeInTheDocument();
    });
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("renames the Watchlist", async () => {
    vi.spyOn(watchlistApi, "fetchWatchlist").mockResolvedValue(makeDetail());
    const updateSpy = vi
      .spyOn(watchlistApi, "updateWatchlist")
      .mockResolvedValue(makeDetail({ name: "Renamed" }).watchlist);
    const user = userEvent.setup();

    renderWithProviders();
    await waitFor(() => {
      expect(screen.getByText("CFO Demo Watchlist")).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: "Rename" }));
    const dialog = screen.getByRole("dialog");
    const nameField = within(dialog).getByLabelText("Name");
    await user.clear(nameField);
    await user.type(nameField, "Renamed");
    await user.click(within(dialog).getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(updateSpy).toHaveBeenCalledWith("watchlist-1", {
        name: "Renamed",
        description: "Curated for the CFO walkthrough.",
      });
    });
  });

  it("deletes the Watchlist after confirmation", async () => {
    vi.spyOn(watchlistApi, "fetchWatchlist").mockResolvedValue(makeDetail());
    const deleteSpy = vi.spyOn(watchlistApi, "deleteWatchlist").mockResolvedValue();
    const user = userEvent.setup();

    renderWithProviders();
    await waitFor(() => {
      expect(screen.getByText("CFO Demo Watchlist")).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: "Delete" }));
    const dialog = screen.getByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "Delete" }));

    await waitFor(() => {
      expect(deleteSpy).toHaveBeenCalledWith("watchlist-1");
    });
  });
});
