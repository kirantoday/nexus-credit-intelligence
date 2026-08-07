import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router";
import { IssuerPage } from "./IssuerPage";
import * as capitalStructureApi from "../api/capitalStructure";
import * as courtDocketApi from "../api/courtDocket";
import * as issuerApi from "../api/issuer";
import { ApiError } from "../api/client";
import type { IssuerDetail } from "../api/issuer";
import type { CapitalStructureResponse } from "../api/capitalStructure";
import type { CourtDocketDetail, CourtDocketRow } from "../api/courtDocket";

function renderIssuerPage(issuerId = "iss-1"): void {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[`/issuers/${issuerId}`]}>{children}</MemoryRouter>
      </QueryClientProvider>
    );
  }
  render(
    <Routes>
      <Route path="/issuers/:issuerId" element={<IssuerPage />} />
    </Routes>,
    { wrapper: Wrapper },
  );
}

const BASE_ISSUER: IssuerDetail = {
  issuer_id: "iss-1",
  legal_name: "Cobalt Ridge Energy Corp",
  cik: null,
  lei: null,
  ticker: null,
  sic: null,
  sector: "Oilfield Services",
  is_synthetic: true,
  synthetic_reason: "SYNTHETIC_DEMO_DATA",
  securities: [],
  financial_facts: [],
  data_sources: [
    { provider: "synthetic", record_count: 9, latest_retrieved_at: "2026-08-06T12:00:00Z" },
  ],
  recent_activity: [],
  universe_memberships: [],
  court_dockets: [],
};

const EMPTY_CAPITAL_STRUCTURE: CapitalStructureResponse = {
  issuer_id: "iss-1",
  issuer_legal_name: "Cobalt Ridge Energy Corp",
  positions: [],
};

afterEach(() => {
  vi.restoreAllMocks();
});

describe("IssuerPage", () => {
  it("renders the issuer's legal name and data sources once loaded", async () => {
    vi.spyOn(issuerApi, "fetchIssuerDetail").mockResolvedValue(BASE_ISSUER);
    vi.spyOn(capitalStructureApi, "fetchCapitalStructure").mockResolvedValue(
      EMPTY_CAPITAL_STRUCTURE,
    );

    renderIssuerPage();

    await waitFor(() => {
      expect(screen.getByText("Cobalt Ridge Energy Corp")).toBeInTheDocument();
    });
    expect(screen.getByText("Oilfield Services")).toBeInTheDocument();
    expect(screen.getByText(/9 records/)).toBeInTheDocument();
  });

  it("falls back to the flat securities table when no capital structure layers exist", async () => {
    vi.spyOn(issuerApi, "fetchIssuerDetail").mockResolvedValue({
      ...BASE_ISSUER,
      securities: [
        {
          security_id: "sec-1",
          instrument_type: "bond",
          description: "Cobalt Ridge Energy Corp — Test Bond",
          seniority: null,
          lien_position: null,
          secured: null,
          cusip: null,
          isin: null,
          figi: null,
          maturity_date: "2030-01-01",
          coupon: null,
          amount_outstanding: "500000000",
          benchmark: null,
          spread: null,
          is_synthetic: false,
          synthetic_reason: null,
          provider: "sec_edgar",
          classification: "public",
          transformation: "reported",
          as_of_date: "2026-06-01",
          retrieved_at: "2026-08-06T12:00:00Z",
          freshness: "live",
        },
      ],
    });
    vi.spyOn(capitalStructureApi, "fetchCapitalStructure").mockResolvedValue(
      EMPTY_CAPITAL_STRUCTURE,
    );

    renderIssuerPage();

    await waitFor(() => {
      expect(screen.getByText("Securities on file")).toBeInTheDocument();
    });
    expect(screen.getByText("Cobalt Ridge Energy Corp — Test Bond")).toBeInTheDocument();
  });

  it("hides the flat securities table when capital structure layers exist", async () => {
    vi.spyOn(issuerApi, "fetchIssuerDetail").mockResolvedValue(BASE_ISSUER);
    vi.spyOn(capitalStructureApi, "fetchCapitalStructure").mockResolvedValue({
      issuer_id: "iss-1",
      issuer_legal_name: "Cobalt Ridge Energy Corp",
      positions: [
        {
          position_id: "pos-1",
          security_id: null,
          layer_name: "Revolving Credit Facility (drawn)",
          rank_order: 1,
          instrument_type: "revolver",
          seniority: "first_lien",
          lien_position: null,
          secured: true,
          guarantor_scope: null,
          amount_outstanding: "45000000",
          currency: "USD",
          maturity_date: "2027-03-01",
          price: null,
          enterprise_value_coverage: "14.44",
          illustrative_recovery: "100.00",
          recovery_scenario: "Illustrative base-case Enterprise Value of $650,000,000.",
          is_synthetic: true,
          synthetic_reason: "SYNTHETIC_DEMO_DATA",
          provider: "synthetic",
          classification: "synthetic",
          transformation: "calculated",
          as_of_date: "2026-08-06",
          retrieved_at: "2026-08-06T12:00:00Z",
          freshness: "live",
        },
      ],
    });

    renderIssuerPage();

    await waitFor(() => {
      expect(screen.getByText("Revolving Credit Facility (drawn)")).toBeInTheDocument();
    });
    expect(screen.queryByText("Securities on file")).not.toBeInTheDocument();
  });

  it("shows the empty state when the issuer has no court docket", async () => {
    vi.spyOn(issuerApi, "fetchIssuerDetail").mockResolvedValue(BASE_ISSUER);
    vi.spyOn(capitalStructureApi, "fetchCapitalStructure").mockResolvedValue(
      EMPTY_CAPITAL_STRUCTURE,
    );

    renderIssuerPage();

    await waitFor(() => {
      expect(screen.getByText("What happened in court?")).toBeInTheDocument();
    });
    expect(screen.getByText("No court docket on file for this issuer.")).toBeInTheDocument();
  });

  it("renders a linked court docket and its entries", async () => {
    const docket: CourtDocketRow = {
      id: "docket-1",
      issuer_id: "iss-1",
      issuer_legal_name: "Cobalt Ridge Energy Corp",
      courtlistener_docket_id: 67460054,
      court: "United States Bankruptcy Court, S.D. Texas",
      docket_number: "23-90602",
      case_name: "Cobalt Ridge Holding Company, Inc.",
      nature_of_suit: null,
      chapter: "11",
      date_filed: "2023-06-01",
      courtlistener_url: "https://www.courtlistener.com/docket/67460054/",
      entry_count: 1,
      created_at: "2026-08-06T12:00:00Z",
    };
    const detail: CourtDocketDetail = {
      docket,
      entries: [
        {
          id: "entry-1",
          entry_number: 1,
          entry_date: "2023-06-01",
          description: "Chapter 11 Voluntary Petition Filed.",
          document_available: true,
          documents: [],
        },
      ],
    };
    vi.spyOn(issuerApi, "fetchIssuerDetail").mockResolvedValue({
      ...BASE_ISSUER,
      court_dockets: [docket],
    });
    vi.spyOn(capitalStructureApi, "fetchCapitalStructure").mockResolvedValue(
      EMPTY_CAPITAL_STRUCTURE,
    );
    vi.spyOn(courtDocketApi, "fetchCourtDocketDetail").mockResolvedValue(detail);

    renderIssuerPage();

    await waitFor(() => {
      expect(screen.getByText("Cobalt Ridge Holding Company, Inc.")).toBeInTheDocument();
    });
    expect(screen.getByText(/23-90602/)).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("Chapter 11 Voluntary Petition Filed.")).toBeInTheDocument();
    });
  });

  it("shows a not-found message for a 404 response", async () => {
    vi.spyOn(issuerApi, "fetchIssuerDetail").mockRejectedValue(
      new ApiError("Request failed with status 404", 404),
    );
    vi.spyOn(capitalStructureApi, "fetchCapitalStructure").mockResolvedValue(
      EMPTY_CAPITAL_STRUCTURE,
    );

    renderIssuerPage();

    await waitFor(() => {
      expect(screen.getByText("This issuer doesn't exist.")).toBeInTheDocument();
    });
  });
});
