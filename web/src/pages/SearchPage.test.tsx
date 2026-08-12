import type { ReactElement, ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router";
import { SearchPage } from "./SearchPage";
import * as searchApi from "../api/search";
import type { SearchResponse, SearchResultItem } from "../api/search";

function renderWithProviders(initialQuery = ""): void {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  function Wrapper({ children }: { children: ReactNode }): ReactElement {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[`/search${initialQuery ? `?q=${initialQuery}` : ""}`]}>
          {children}
        </MemoryRouter>
      </QueryClientProvider>
    );
  }
  render(
    <Routes>
      <Route path="/search" element={<SearchPage />} />
    </Routes>,
    { wrapper: Wrapper },
  );
}

function makeItem(overrides: Partial<SearchResultItem> = {}): SearchResultItem {
  return {
    entity_type: "issuer",
    entity_id: "issuer-1",
    title: "Trinseo PLC",
    snippet: "Ticker: TSEOQ",
    issuer_id: "issuer-1",
    collection_type: null,
    context_date: null,
    matched_field: null,
    ...overrides,
  };
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("SearchPage", () => {
  it("shows a prompt when there is no query", () => {
    renderWithProviders();
    expect(screen.getByText(/Enter a search term above/)).toBeInTheDocument();
  });

  it("renders exact matches and grouped results for a query", async () => {
    vi.spyOn(searchApi, "fetchSearch").mockResolvedValue({
      query: "trinseo",
      exact_matches: [makeItem({ matched_field: "Ticker" })],
      groups: [
        {
          entity_type: "alert_event",
          results: [
            makeItem({
              entity_type: "alert_event",
              entity_id: "alert-1",
              title: "8-K discloses Chapter 11 filing plans",
              snippet: "Trinseo PLC: filing excerpt",
            }),
          ],
        },
      ],
    } satisfies SearchResponse);

    renderWithProviders("trinseo");

    await waitFor(() => {
      expect(screen.getByText("Exact Matches")).toBeInTheDocument();
    });
    expect(screen.getByText("Exact: Ticker")).toBeInTheDocument();
    expect(screen.getByText("Distress Development")).toBeInTheDocument();
    expect(screen.getByText("8-K discloses Chapter 11 filing plans")).toBeInTheDocument();
  });

  it("shows a no-results message for a query with no matches", async () => {
    vi.spyOn(searchApi, "fetchSearch").mockResolvedValue({
      query: "zzz",
      exact_matches: [],
      groups: [],
    });

    renderWithProviders("zzz");

    await waitFor(() => {
      expect(screen.getByText(/No results for "zzz"/)).toBeInTheDocument();
    });
  });

  it("shows an error state when the search request fails", async () => {
    vi.spyOn(searchApi, "fetchSearch").mockRejectedValue(new Error("network error"));

    renderWithProviders("trinseo");

    await waitFor(() => {
      expect(screen.getByText("Could not load search results.")).toBeInTheDocument();
    });
  });

  it("links issuer results to the issuer detail page", async () => {
    vi.spyOn(searchApi, "fetchSearch").mockResolvedValue({
      query: "trinseo",
      exact_matches: [],
      groups: [{ entity_type: "issuer", results: [makeItem()] }],
    });

    renderWithProviders("trinseo");

    const link = await screen.findByRole("link", { name: /Trinseo PLC/ });
    expect(link).toHaveAttribute("href", "/issuers/issuer-1");
  });

  it("links a Watchlist collection result to the Watchlist detail page", async () => {
    vi.spyOn(searchApi, "fetchSearch").mockResolvedValue({
      query: "cfo demo",
      exact_matches: [],
      groups: [
        {
          entity_type: "collection",
          results: [
            makeItem({
              entity_type: "collection",
              entity_id: "watchlist-1",
              title: "CFO Demo Watchlist",
              issuer_id: null,
              collection_type: "watchlist",
            }),
          ],
        },
      ],
    });

    renderWithProviders("cfo demo");

    const link = await screen.findByRole("link", { name: /CFO Demo Watchlist/ });
    expect(link).toHaveAttribute("href", "/watchlists/watchlist-1");
    expect(screen.getByText("Watchlist")).toBeInTheDocument();
  });

  it("shows a 'see all in Credit Universe' link only for issuer/security groups", async () => {
    vi.spyOn(searchApi, "fetchSearch").mockResolvedValue({
      query: "trinseo",
      exact_matches: [],
      groups: [
        { entity_type: "issuer", results: [makeItem()] },
        {
          entity_type: "alert_event",
          results: [makeItem({ entity_type: "alert_event", entity_id: "alert-1" })],
        },
      ],
    });

    renderWithProviders("trinseo");

    await waitFor(() => {
      expect(screen.getByText("Issuer")).toBeInTheDocument();
    });
    const seeAllLinks = screen.getAllByText("See all in Credit Universe");
    expect(seeAllLinks).toHaveLength(1);
  });
});
