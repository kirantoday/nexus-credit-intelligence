import type { ReactElement, ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AddToWatchlistButton } from "./AddToWatchlistButton";
import * as watchlistApi from "../api/watchlist";
import type { WatchlistListResponse, WatchlistSummary } from "../api/watchlist";

function renderWithProviders(ui: ReactElement): void {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  }
  render(ui, { wrapper: Wrapper });
}

function makeWatchlist(overrides: Partial<WatchlistSummary> = {}): WatchlistSummary {
  return {
    id: "watchlist-1",
    slug: "my-list",
    name: "My List",
    description: "",
    issuer_count: 1,
    issuers_with_new_developments: 0,
    high_severity_count: 0,
    new_alert_count: 0,
    high_severity_alert_count: 0,
    last_activity_at: null,
    created_at: "2026-08-01T00:00:00Z",
    updated_at: "2026-08-01T00:00:00Z",
    contains_issuer: false,
    ...overrides,
  };
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("AddToWatchlistButton", () => {
  it("shows 'Add to Watchlist' when the issuer isn't on any Watchlist", async () => {
    vi.spyOn(watchlistApi, "fetchWatchlists").mockResolvedValue({
      watchlists: [makeWatchlist({ contains_issuer: false })],
    } satisfies WatchlistListResponse);

    renderWithProviders(<AddToWatchlistButton issuerId="issuer-1" />);

    expect(await screen.findByRole("button", { name: /Add to Watchlist/ })).toBeInTheDocument();
  });

  it("shows the watched count when the issuer is already on a Watchlist", async () => {
    vi.spyOn(watchlistApi, "fetchWatchlists").mockResolvedValue({
      watchlists: [makeWatchlist({ contains_issuer: true })],
    });

    renderWithProviders(<AddToWatchlistButton issuerId="issuer-1" />);

    expect(await screen.findByRole("button", { name: "On 1 Watchlist" })).toBeInTheDocument();
  });

  it("opens the menu and shows each Watchlist with its already-added state", async () => {
    vi.spyOn(watchlistApi, "fetchWatchlists").mockResolvedValue({
      watchlists: [makeWatchlist({ name: "My List", contains_issuer: true })],
    });
    const user = userEvent.setup();

    renderWithProviders(<AddToWatchlistButton issuerId="issuer-1" />);
    await user.click(await screen.findByRole("button", { name: "On 1 Watchlist" }));

    const checkbox = await screen.findByRole("menuitemcheckbox", { name: "My List" });
    expect(checkbox).toHaveAttribute("aria-checked", "true");
  });

  it("adds the issuer to a Watchlist when toggled on", async () => {
    vi.spyOn(watchlistApi, "fetchWatchlists").mockResolvedValue({
      watchlists: [makeWatchlist({ contains_issuer: false })],
    });
    const addSpy = vi
      .spyOn(watchlistApi, "addIssuerToWatchlist")
      .mockResolvedValue(makeWatchlist({ contains_issuer: true }));
    const user = userEvent.setup();

    renderWithProviders(<AddToWatchlistButton issuerId="issuer-1" />);
    await user.click(await screen.findByRole("button", { name: /Add to Watchlist/ }));
    await user.click(await screen.findByRole("menuitemcheckbox", { name: "My List" }));

    await waitFor(() => {
      expect(addSpy).toHaveBeenCalledWith("watchlist-1", {
        issuer_id: "issuer-1",
        rationale: undefined,
      });
    });
  });

  it("creates a new Watchlist and adds the issuer to it inline", async () => {
    vi.spyOn(watchlistApi, "fetchWatchlists").mockResolvedValue({ watchlists: [] });
    const createSpy = vi
      .spyOn(watchlistApi, "createWatchlist")
      .mockResolvedValue(makeWatchlist({ id: "watchlist-2", name: "Brand New" }));
    const addSpy = vi
      .spyOn(watchlistApi, "addIssuerToWatchlist")
      .mockResolvedValue(makeWatchlist({ id: "watchlist-2" }));
    const user = userEvent.setup();

    renderWithProviders(<AddToWatchlistButton issuerId="issuer-1" />);
    await user.click(await screen.findByRole("button", { name: /Add to Watchlist/ }));
    await user.type(screen.getByPlaceholderText("New Watchlist name"), "Brand New");
    await user.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() => {
      expect(createSpy).toHaveBeenCalledWith({ name: "Brand New" });
    });
    await waitFor(() => {
      expect(addSpy).toHaveBeenCalledWith("watchlist-2", {
        issuer_id: "issuer-1",
        rationale: undefined,
      });
    });
  });
});
