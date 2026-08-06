import type { ReactElement, ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router";
import { CreditUniversePage } from "./CreditUniversePage";
import * as creditUniverseApi from "../api/creditUniverse";
import type { CreditUniversePage as CreditUniversePageResponse } from "../api/creditUniverse";
import * as marketContextApi from "../api/marketContext";

function renderWithProviders(ui: ReactElement): void {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>{children}</MemoryRouter>
      </QueryClientProvider>
    );
  }
  render(ui, { wrapper: Wrapper });
}

const ONE_ROW_RESPONSE: CreditUniversePageResponse = {
  rows: [
    {
      security_id: "sec-1",
      issuer_id: "iss-1",
      issuer_legal_name: "Apple Inc.",
      issuer_ticker: "AAPL",
      issuer_sector: null,
      instrument_type: "bond",
      description: "Apple Inc. — Long-Term Debt (SEC XBRL aggregate; not a specific instrument)",
      seniority: null,
      lien_position: null,
      secured: null,
      cusip: null,
      isin: null,
      figi: null,
      maturity_date: null,
      coupon: null,
      amount_outstanding: "71340000000",
      benchmark: null,
      spread: null,
      is_synthetic: false,
      synthetic_reason: null,
      provider: "sec_edgar",
      classification: "public",
      transformation: "reported",
      as_of_date: "2026-06-27",
      retrieved_at: "2026-08-06T04:47:38.603954Z",
      freshness: "live",
      benchmark_rate: null,
      benchmark_rate_as_of_date: null,
      benchmark_rate_provider: null,
    },
  ],
  total: 1,
  page: 1,
  page_size: 25,
};

const EMPTY_MARKET_CONTEXT = { sofr: null, high_yield_oas: null };

afterEach(() => {
  vi.restoreAllMocks();
});

describe("CreditUniversePage", () => {
  it("renders a row for each security returned by the API", async () => {
    vi.spyOn(creditUniverseApi, "fetchCreditUniverse").mockResolvedValue(ONE_ROW_RESPONSE);
    vi.spyOn(marketContextApi, "fetchMarketContext").mockResolvedValue(EMPTY_MARKET_CONTEXT);

    renderWithProviders(<CreditUniversePage />);

    await waitFor(() => {
      expect(screen.getByText("Apple Inc.")).toBeInTheDocument();
    });
    expect(screen.getByText("$71.3B")).toBeInTheDocument();
  });

  it("shows the empty state when the API returns no rows", async () => {
    vi.spyOn(creditUniverseApi, "fetchCreditUniverse").mockResolvedValue({
      rows: [],
      total: 0,
      page: 1,
      page_size: 25,
    });
    vi.spyOn(marketContextApi, "fetchMarketContext").mockResolvedValue(EMPTY_MARKET_CONTEXT);

    renderWithProviders(<CreditUniversePage />);

    await waitFor(() => {
      expect(screen.getByText("No securities in the Credit Universe yet.")).toBeInTheDocument();
    });
  });

  it("shows an error message when the API call fails", async () => {
    vi.spyOn(creditUniverseApi, "fetchCreditUniverse").mockRejectedValue(
      new Error("Network unreachable"),
    );
    vi.spyOn(marketContextApi, "fetchMarketContext").mockResolvedValue(EMPTY_MARKET_CONTEXT);

    renderWithProviders(<CreditUniversePage />);

    await waitFor(() => {
      expect(screen.getByText(/Could not load the Credit Universe/)).toBeInTheDocument();
    });
  });
});
