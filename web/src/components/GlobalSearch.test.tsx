import type { ReactElement, ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router";
import { GlobalSearch } from "./GlobalSearch";
import * as searchApi from "../api/search";
import type { SearchResponse } from "../api/search";

/** Mirrors the mobile-viewport mock already established in
 * `WatchlistDetailPage.test.tsx`/`DataTable.test.tsx`/`Layout.test.tsx`. */
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

function renderWithProviders(): void {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  function Wrapper({ children }: { children: ReactNode }): ReactElement {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/"]}>{children}</MemoryRouter>
      </QueryClientProvider>
    );
  }
  render(
    <Routes>
      <Route path="*" element={<GlobalSearch />} />
    </Routes>,
    { wrapper: Wrapper },
  );
}

function makeResponse(overrides: Partial<SearchResponse> = {}): SearchResponse {
  return {
    query: "trinseo",
    exact_matches: [],
    groups: [
      {
        entity_type: "issuer",
        results: [
          {
            entity_type: "issuer",
            entity_id: "issuer-1",
            title: "Trinseo PLC",
            snippet: "Ticker: TSEOQ",
            issuer_id: "issuer-1",
            collection_type: null,
            context_date: null,
            matched_field: null,
          },
        ],
      },
    ],
    ...overrides,
  };
}

afterEach(() => {
  window.matchMedia = originalMatchMedia;
  vi.restoreAllMocks();
});

describe("GlobalSearch — desktop", () => {
  it("shows grouped results after typing, debounced", async () => {
    vi.spyOn(searchApi, "fetchSearch").mockResolvedValue(makeResponse());
    const user = userEvent.setup();
    renderWithProviders();

    await user.type(screen.getByRole("textbox", { name: "Search Nexus" }), "Trinseo");

    await waitFor(() => {
      expect(screen.getByText("Trinseo PLC")).toBeInTheDocument();
    });
    expect(screen.getByText("Issuer")).toBeInTheDocument();
  });

  it("does not fetch until the debounce interval elapses", async () => {
    const fetchSpy = vi.spyOn(searchApi, "fetchSearch").mockResolvedValue(makeResponse());
    const user = userEvent.setup();
    renderWithProviders();

    await user.type(screen.getByRole("textbox", { name: "Search Nexus" }), "T");
    expect(fetchSpy).not.toHaveBeenCalled();

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalled();
    });
  });

  it("ArrowDown highlights a result and Enter navigates to it", async () => {
    vi.spyOn(searchApi, "fetchSearch").mockResolvedValue(makeResponse());
    const user = userEvent.setup();

    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    function Wrapper({ children }: { children: ReactNode }): ReactElement {
      return (
        <QueryClientProvider client={queryClient}>
          <MemoryRouter initialEntries={["/"]}>{children}</MemoryRouter>
        </QueryClientProvider>
      );
    }
    render(
      <Routes>
        <Route path="/" element={<GlobalSearch />} />
        <Route path="/issuers/:issuerId" element={<div>Issuer Detail Page</div>} />
      </Routes>,
      { wrapper: Wrapper },
    );

    const input = screen.getByRole("textbox", { name: "Search Nexus" });
    await user.type(input, "Trinseo");
    await waitFor(() => {
      expect(screen.getByText("Trinseo PLC")).toBeInTheDocument();
    });

    await user.keyboard("{ArrowDown}");
    await user.keyboard("{Enter}");

    await waitFor(() => {
      expect(screen.getByText("Issuer Detail Page")).toBeInTheDocument();
    });
  });

  it("Enter with nothing highlighted navigates to the full /search page", async () => {
    vi.spyOn(searchApi, "fetchSearch").mockResolvedValue(makeResponse());
    const user = userEvent.setup();

    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    function Wrapper({ children }: { children: ReactNode }): ReactElement {
      return (
        <QueryClientProvider client={queryClient}>
          <MemoryRouter initialEntries={["/"]}>{children}</MemoryRouter>
        </QueryClientProvider>
      );
    }
    render(
      <Routes>
        <Route path="/" element={<GlobalSearch />} />
        <Route path="/search" element={<div>Full Search Page</div>} />
      </Routes>,
      { wrapper: Wrapper },
    );

    const input = screen.getByRole("textbox", { name: "Search Nexus" });
    await user.type(input, "Trinseo");
    await waitFor(() => {
      expect(screen.getByText("Trinseo PLC")).toBeInTheDocument();
    });

    await user.keyboard("{Enter}");

    await waitFor(() => {
      expect(screen.getByText("Full Search Page")).toBeInTheDocument();
    });
  });

  it("Escape closes the dropdown without clearing focus behavior", async () => {
    vi.spyOn(searchApi, "fetchSearch").mockResolvedValue(makeResponse());
    const user = userEvent.setup();
    renderWithProviders();

    const input = screen.getByRole("textbox", { name: "Search Nexus" });
    await user.type(input, "Trinseo");
    await waitFor(() => {
      expect(screen.getByText("Trinseo PLC")).toBeInTheDocument();
    });

    await user.keyboard("{Escape}");

    await waitFor(() => {
      expect(screen.queryByText("Trinseo PLC")).not.toBeInTheDocument();
    });
  });

  it("shows a no-results message for a query with no matches", async () => {
    vi.spyOn(searchApi, "fetchSearch").mockResolvedValue({
      query: "zzz",
      exact_matches: [],
      groups: [],
    });
    const user = userEvent.setup();
    renderWithProviders();

    await user.type(screen.getByRole("textbox", { name: "Search Nexus" }), "zzz");

    await waitFor(() => {
      expect(screen.getByText(/No results for "zzz"/)).toBeInTheDocument();
    });
  });
});

describe("GlobalSearch — mobile", () => {
  it("renders a search icon button instead of an inline text field", () => {
    mockMobileViewport();
    renderWithProviders();

    expect(screen.getByRole("button", { name: "Search Nexus" })).toBeInTheDocument();
    expect(screen.queryByRole("textbox", { name: "Search Nexus" })).not.toBeInTheDocument();
  });

  it("opens a full-screen dialog when the search icon is clicked", async () => {
    mockMobileViewport();
    vi.spyOn(searchApi, "fetchSearch").mockResolvedValue(makeResponse());
    const user = userEvent.setup();
    renderWithProviders();

    await user.click(screen.getByRole("button", { name: "Search Nexus" }));

    expect(await screen.findByRole("textbox", { name: "Search Nexus" })).toBeInTheDocument();
  });
});
