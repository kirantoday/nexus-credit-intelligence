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

const SOFR_OBSERVATION = {
  series_id: "SOFR",
  title: "Secured Overnight Financing Rate",
  value: "3.64",
  units: "Percent",
  as_of_date: "2026-08-05",
  freshness: "cached" as const,
  provider: "fred" as const,
};

const HY_OAS_OBSERVATION = {
  series_id: "BAMLH0A0HYM2",
  title: "ICE BofA US High Yield Index Option-Adjusted Spread",
  value: "2.73",
  units: "Percent",
  as_of_date: "2026-08-04",
  freshness: "cached" as const,
  provider: "fred" as const,
};

describe("MarketContextPanel", () => {
  it("renders real SOFR and HY OAS observations", async () => {
    vi.spyOn(marketContextApi, "fetchMarketContext").mockResolvedValue({
      sofr: SOFR_OBSERVATION,
      high_yield_oas: HY_OAS_OBSERVATION,
    });

    renderWithProviders(<MarketContextPanel />);

    await waitFor(() => {
      expect(screen.getByText("3.64%")).toBeInTheDocument();
    });
    expect(screen.getByText("2.73%")).toBeInTheDocument();
  });

  it("converts HY OAS percent to basis points deterministically, without a second fetch", async () => {
    const fetchSpy = vi
      .spyOn(marketContextApi, "fetchMarketContext")
      .mockResolvedValue({ sofr: SOFR_OBSERVATION, high_yield_oas: HY_OAS_OBSERVATION });

    renderWithProviders(<MarketContextPanel />);

    await waitFor(() => {
      expect(screen.getByText("273 bps")).toBeInTheDocument();
    });
    // SOFR is a rate, not a spread -- it must never get a bps conversion.
    expect(screen.queryByText("364 bps")).not.toBeInTheDocument();
    expect(fetchSpy).toHaveBeenCalledTimes(1);
  });

  it("shows each metric's own as-of date rather than one shared date", async () => {
    vi.spyOn(marketContextApi, "fetchMarketContext").mockResolvedValue({
      sofr: SOFR_OBSERVATION,
      high_yield_oas: HY_OAS_OBSERVATION,
    });

    renderWithProviders(<MarketContextPanel />);

    await waitFor(() => {
      expect(screen.getByText("As of Aug 5, 2026")).toBeInTheDocument();
    });
    expect(screen.getByText("As of Aug 4, 2026")).toBeInTheDocument();
  });

  it("does not prominently show the 'cached' implementation label", async () => {
    vi.spyOn(marketContextApi, "fetchMarketContext").mockResolvedValue({
      sofr: SOFR_OBSERVATION,
      high_yield_oas: HY_OAS_OBSERVATION,
    });

    renderWithProviders(<MarketContextPanel />);

    await waitFor(() => {
      expect(screen.getByText("3.64%")).toBeInTheDocument();
    });
    expect(screen.queryByText("cached")).not.toBeInTheDocument();
    expect(screen.queryByText(/cached/i)).not.toBeInTheDocument();
  });

  it("provides accurate SOFR and HY OAS definitions via tooltip", async () => {
    vi.spyOn(marketContextApi, "fetchMarketContext").mockResolvedValue({
      sofr: SOFR_OBSERVATION,
      high_yield_oas: HY_OAS_OBSERVATION,
    });

    renderWithProviders(<MarketContextPanel />);

    await waitFor(() => {
      expect(screen.getByText("3.64%")).toBeInTheDocument();
    });
    expect(
      screen.getByLabelText(
        "Secured Overnight Financing Rate — a base rate commonly used for floating-rate corporate loans.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText(
        "High-Yield Option-Adjusted Spread — the additional spread investors demand for high-yield corporate credit relative to comparable Treasury rates, adjusted for embedded options.",
      ),
    ).toBeInTheDocument();
  });

  it("shows a dash for a series that hasn't been synced yet, not a fabricated value or date", async () => {
    vi.spyOn(marketContextApi, "fetchMarketContext").mockResolvedValue({
      sofr: null,
      high_yield_oas: null,
    });

    renderWithProviders(<MarketContextPanel />);

    await waitFor(() => {
      expect(screen.getAllByText("—")).toHaveLength(2);
    });
    expect(screen.queryByText(/As of/)).not.toBeInTheDocument();
  });

  it("shows an unavailable message when the API call fails", async () => {
    vi.spyOn(marketContextApi, "fetchMarketContext").mockRejectedValue(new Error("network error"));

    renderWithProviders(<MarketContextPanel />);

    await waitFor(() => {
      expect(screen.getByText("Market context unavailable.")).toBeInTheDocument();
    });
  });
});
