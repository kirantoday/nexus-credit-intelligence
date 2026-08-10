import type { ReactElement, ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router";
import { CreditUniversePage } from "./CreditUniversePage";
import * as creditUniverseApi from "../api/creditUniverse";
import type { CreditUniversePage as CreditUniversePageResponse } from "../api/creditUniverse";
import * as marketContextApi from "../api/marketContext";
import * as researchUniverseApi from "../api/researchUniverse";
import type {
  ResearchUniverseIssuersResponse,
  ResearchUniverseSummary,
} from "../api/researchUniverse";

function renderWithProviders(ui: ReactElement, initialEntries: string[] = ["/"]): void {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={initialEntries}>{children}</MemoryRouter>
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

  // PLAN.md Milestone 7.5.3 CFO-demo cleanup: Credit Universe is real-data
  // only now — there is no user-facing synthetic mode.
  it("does not render synthetic filter controls or synthetic badges", async () => {
    vi.spyOn(creditUniverseApi, "fetchCreditUniverse").mockResolvedValue(ONE_ROW_RESPONSE);
    vi.spyOn(marketContextApi, "fetchMarketContext").mockResolvedValue(EMPTY_MARKET_CONTEXT);

    renderWithProviders(<CreditUniversePage />);

    await waitFor(() => {
      expect(screen.getByText("Apple Inc.")).toBeInTheDocument();
    });
    expect(screen.queryByText("All data")).not.toBeInTheDocument();
    expect(screen.queryByText("Real only")).not.toBeInTheDocument();
    expect(screen.queryByText("Synthetic only")).not.toBeInTheDocument();
    expect(screen.queryByText(/synthetic/i)).not.toBeInTheDocument();
    // The description no longer mentions synthetic positions.
    expect(
      screen.getByText(
        "Every bond and loan Nexus currently tracks — real issuer and instrument data with source provenance.",
      ),
    ).toBeInTheDocument();
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

  // PLAN.md Milestone 7.5.3 CFO-demo fix: Research Universe membership is
  // issuer-level, Credit Universe is security-level — a universe with real
  // issuer members that simply have no securities loaded must show an
  // honest explanation with links to those issuers, never the generic
  // "No securities in the Credit Universe yet" message (which reads as a
  // bug, not a legitimate data state).
  it("shows an honest explanation with issuer links when a universe's members have no securities", async () => {
    const universeSummary: ResearchUniverseSummary = {
      id: "universe-1",
      slug: "consumer-retail",
      name: "Consumer & Retail",
      description: "Consumer and retail sector issuers.",
      collection_type: "research_universe",
      scope: "organization",
      visibility: "public",
      curation_method: "manual_curated",
      verification_status: "verified",
      last_verified_at: null,
      priority: null,
      issuer_count: 2,
    };
    const universeIssuers: ResearchUniverseIssuersResponse = {
      universe: universeSummary,
      issuers: [
        {
          issuer_id: "iss-carvana",
          issuer_legal_name: "Carvana Co.",
          issuer_ticker: "CVNA",
          rationale: "Consumer & retail sector.",
          rationale_as_of_date: null,
          verification_status: "verified",
          added_at: "2026-08-01T00:00:00Z",
          system_seeded: false,
        },
        {
          issuer_id: "iss-amc",
          issuer_legal_name: "AMC Entertainment Holdings, Inc.",
          issuer_ticker: "AMC",
          rationale: "Consumer & retail sector.",
          rationale_as_of_date: null,
          verification_status: "verified",
          added_at: "2026-08-01T00:00:00Z",
          system_seeded: false,
        },
      ],
    };
    vi.spyOn(creditUniverseApi, "fetchCreditUniverse").mockResolvedValue({
      rows: [],
      total: 0,
      page: 1,
      page_size: 25,
    });
    vi.spyOn(marketContextApi, "fetchMarketContext").mockResolvedValue(EMPTY_MARKET_CONTEXT);
    vi.spyOn(researchUniverseApi, "fetchResearchUniverse").mockResolvedValue(universeSummary);
    vi.spyOn(researchUniverseApi, "fetchResearchUniverseIssuers").mockResolvedValue(
      universeIssuers,
    );

    renderWithProviders(<CreditUniversePage />, ["/?universe=universe-1"]);

    await waitFor(() => {
      expect(screen.getByText(/2 issuers belong to/)).toBeInTheDocument();
    });
    expect(screen.getByText("Consumer & Retail")).toBeInTheDocument();
    expect(screen.getByText(/Carvana Co\. \(CVNA\)/)).toBeInTheDocument();
    expect(screen.getByText(/AMC Entertainment Holdings, Inc\. \(AMC\)/)).toBeInTheDocument();
    // The generic empty message must not also render alongside the honest one.
    expect(screen.queryByText("No securities in the Credit Universe yet.")).not.toBeInTheDocument();
  });

  it("clearing the universe filter chip restores the normal unfiltered Credit Universe", async () => {
    const universeSummary: ResearchUniverseSummary = {
      id: "universe-1",
      slug: "chapter-11-bankruptcy",
      name: "Chapter 11 / Bankruptcy",
      description: "Issuers in active Chapter 11 proceedings.",
      collection_type: "research_universe",
      scope: "organization",
      visibility: "public",
      curation_method: "manual_curated",
      verification_status: "verified",
      last_verified_at: null,
      priority: "critical",
      issuer_count: 1,
    };
    const fetchSpy = vi
      .spyOn(creditUniverseApi, "fetchCreditUniverse")
      .mockResolvedValue(ONE_ROW_RESPONSE);
    vi.spyOn(marketContextApi, "fetchMarketContext").mockResolvedValue(EMPTY_MARKET_CONTEXT);
    vi.spyOn(researchUniverseApi, "fetchResearchUniverse").mockResolvedValue(universeSummary);
    vi.spyOn(researchUniverseApi, "fetchResearchUniverseIssuers").mockResolvedValue({
      universe: universeSummary,
      issuers: [],
    });

    renderWithProviders(<CreditUniversePage />, ["/?universe=universe-1"]);

    await waitFor(() => {
      expect(screen.getByText("Universe: Chapter 11 / Bankruptcy")).toBeInTheDocument();
    });
    expect(fetchSpy).toHaveBeenCalledWith(expect.objectContaining({ universeId: "universe-1" }));

    // MUI Chip's onDelete fires from its own delete icon (not the chip
    // label) — MUI's built-in icons set `data-testid` to their component
    // name automatically.
    await userEvent.click(screen.getByTestId("CancelIcon"));

    await waitFor(() => {
      expect(screen.queryByText("Universe: Chapter 11 / Bankruptcy")).not.toBeInTheDocument();
    });
    expect(fetchSpy).toHaveBeenLastCalledWith(expect.objectContaining({ universeId: undefined }));
  });
});
