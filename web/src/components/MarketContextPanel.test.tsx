import type { ReactElement, ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MarketContextPanel } from "./MarketContextPanel";
import * as marketContextApi from "../api/marketContext";

function renderWithProviders(ui: ReactElement): void {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  }
  render(ui, { wrapper: Wrapper });
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("MarketContextPanel", () => {
  it("renders real SOFR and HY OAS observations", async () => {
    vi.spyOn(marketContextApi, "fetchMarketContext").mockResolvedValue({
      sofr: {
        series_id: "SOFR",
        title: "Secured Overnight Financing Rate",
        value: "3.64",
        units: "Percent",
        as_of_date: "2026-08-05",
        freshness: "live",
        provider: "fred",
      },
      high_yield_oas: {
        series_id: "BAMLH0A0HYM2",
        title: "ICE BofA US High Yield Index Option-Adjusted Spread",
        value: "2.73",
        units: "Percent",
        as_of_date: "2026-08-04",
        freshness: "live",
        provider: "fred",
      },
    });

    renderWithProviders(<MarketContextPanel />);

    await waitFor(() => {
      expect(screen.getByText("3.64%")).toBeInTheDocument();
    });
    expect(screen.getByText("2.73%")).toBeInTheDocument();
  });

  it("shows a dash for a series that hasn't been synced yet, not a fabricated value", async () => {
    vi.spyOn(marketContextApi, "fetchMarketContext").mockResolvedValue({
      sofr: null,
      high_yield_oas: null,
    });

    renderWithProviders(<MarketContextPanel />);

    await waitFor(() => {
      expect(screen.getAllByText("—")).toHaveLength(2);
    });
  });

  it("shows an unavailable message when the API call fails", async () => {
    vi.spyOn(marketContextApi, "fetchMarketContext").mockRejectedValue(new Error("network error"));

    renderWithProviders(<MarketContextPanel />);

    await waitFor(() => {
      expect(screen.getByText("Market context unavailable.")).toBeInTheDocument();
    });
  });
});
