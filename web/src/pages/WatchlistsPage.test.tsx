import type { ReactElement, ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router";
import { WatchlistsPage } from "./WatchlistsPage";
import * as watchlistApi from "../api/watchlist";
import type { WatchlistListResponse, WatchlistSummary } from "../api/watchlist";

function renderWithProviders(ui: ReactElement): void {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>{children}</MemoryRouter>
      </QueryClientProvider>
    );
  }
  render(ui, { wrapper: Wrapper });
}

function makeWatchlist(overrides: Partial<WatchlistSummary> = {}): WatchlistSummary {
  return {
    id: "watchlist-1",
    slug: "my-distressed-names",
    name: "My Distressed Names",
    description: "Names I'm personally tracking.",
    issuer_count: 12,
    issuers_with_new_developments: 3,
    high_severity_count: 2,
    last_activity_at: "2026-08-10T00:00:00Z",
    created_at: "2026-08-01T00:00:00Z",
    updated_at: "2026-08-10T00:00:00Z",
    contains_issuer: null,
    ...overrides,
  };
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("WatchlistsPage", () => {
  it("renders Watchlist cards with real summary counts", async () => {
    const response: WatchlistListResponse = { watchlists: [makeWatchlist()] };
    vi.spyOn(watchlistApi, "fetchWatchlists").mockResolvedValue(response);

    renderWithProviders(<WatchlistsPage />);

    await waitFor(() => {
      expect(screen.getByText("My Distressed Names")).toBeInTheDocument();
    });
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
  });

  it("shows an empty state when there are no Watchlists yet", async () => {
    vi.spyOn(watchlistApi, "fetchWatchlists").mockResolvedValue({ watchlists: [] });

    renderWithProviders(<WatchlistsPage />);

    await waitFor(() => {
      expect(screen.getByText(/No Watchlists yet/)).toBeInTheDocument();
    });
  });

  it("shows an error message when the API call fails", async () => {
    vi.spyOn(watchlistApi, "fetchWatchlists").mockRejectedValue(new Error("Network unreachable"));

    renderWithProviders(<WatchlistsPage />);

    await waitFor(() => {
      expect(screen.getByText(/Could not load Watchlists/)).toBeInTheDocument();
    });
  });

  it("opens a New Watchlist dialog and creates a Watchlist", async () => {
    vi.spyOn(watchlistApi, "fetchWatchlists").mockResolvedValue({ watchlists: [] });
    const createSpy = vi
      .spyOn(watchlistApi, "createWatchlist")
      .mockResolvedValue(makeWatchlist({ name: "New List" }));
    const user = userEvent.setup();

    renderWithProviders(<WatchlistsPage />);
    await waitFor(() => {
      expect(screen.getByText(/No Watchlists yet/)).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: "New Watchlist" }));
    await user.type(screen.getByLabelText("Name"), "New List");
    await user.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() => {
      expect(createSpy).toHaveBeenCalledWith({ name: "New List", description: "" });
    });
  });
});
