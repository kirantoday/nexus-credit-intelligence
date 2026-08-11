import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router";
import { IssuerPage } from "./IssuerPage";
import * as capitalStructureApi from "../api/capitalStructure";
import * as courtDocketApi from "../api/courtDocket";
import * as issuerApi from "../api/issuer";
import * as issuerTimelineApi from "../api/issuerTimeline";
import { ApiError } from "../api/client";
import type { IssuerDetail } from "../api/issuer";
import type { CapitalStructureResponse } from "../api/capitalStructure";
import type { CourtDocketDetail, CourtDocketRow } from "../api/courtDocket";
import type { IssuerTimeline } from "../api/issuerTimeline";

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
  sec_filings: [],
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

const EMPTY_TIMELINE: IssuerTimeline = {
  issuer_id: "iss-1",
  events: [],
  total_events: 0,
  date_range_start: null,
  date_range_end: null,
  current_status: [],
  most_recent_event_title: null,
};

beforeEach(() => {
  vi.spyOn(issuerTimelineApi, "fetchIssuerTimeline").mockResolvedValue(EMPTY_TIMELINE);
});

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

  it("shows a View Alerts link filtered to this issuer", async () => {
    vi.spyOn(issuerApi, "fetchIssuerDetail").mockResolvedValue(BASE_ISSUER);
    vi.spyOn(capitalStructureApi, "fetchCapitalStructure").mockResolvedValue(
      EMPTY_CAPITAL_STRUCTURE,
    );

    renderIssuerPage();

    await waitFor(() => {
      expect(screen.getByText("Cobalt Ridge Energy Corp")).toBeInTheDocument();
    });
    const viewAlertsLink = screen.getByRole("link", { name: /View Alerts/ });
    expect(viewAlertsLink).toHaveAttribute("href", "/alerts?issuer=iss-1");
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
    expect(screen.queryByText("Chapter 11 Voluntary Petition Filed.")).not.toBeInTheDocument();

    await userEvent.setup().click(screen.getByRole("button", { name: "View docket entries" }));

    await waitFor(() => {
      expect(screen.getByText("Chapter 11 Voluntary Petition Filed.")).toBeInTheDocument();
    });
  });

  it("visually distinguishes a system-suggested membership from a verified one", async () => {
    vi.spyOn(issuerApi, "fetchIssuerDetail").mockResolvedValue({
      ...BASE_ISSUER,
      universe_memberships: [
        {
          collection_id: "col-verified",
          slug: "system-chapter-11",
          name: "System-Detected: Chapter 11",
          collection_type: "research_universe",
          curation_method: "system_seeded",
          rationale: "Verified test rationale.",
          rationale_as_of_date: "2026-08-01",
          verification_status: "verified",
        },
        {
          collection_id: "col-partial",
          slug: "system-going-concern",
          name: "System-Detected: Going Concern",
          collection_type: "research_universe",
          curation_method: "system_seeded",
          rationale: "Suggested test rationale.",
          rationale_as_of_date: "2026-08-01",
          verification_status: "partial",
        },
      ],
    });
    vi.spyOn(capitalStructureApi, "fetchCapitalStructure").mockResolvedValue(
      EMPTY_CAPITAL_STRUCTURE,
    );

    renderIssuerPage();

    await waitFor(() => {
      expect(screen.getByText("Current Research Universes")).toBeInTheDocument();
    });
    // Verified membership: shown under "Current", internal prefix stripped,
    // no "(suggested)" suffix.
    expect(screen.getByText("Chapter 11")).toBeInTheDocument();
    expect(screen.queryByText("System-Detected: Chapter 11")).not.toBeInTheDocument();
    expect(screen.queryByText("Chapter 11 (suggested)")).not.toBeInTheDocument();
    // Partial (system-suggested) membership: under "Nexus suggested
    // coverage", visibly marked, never rendered as confirmed (PLAN.md
    // Milestone 7.5.1 section 4).
    expect(screen.getByText("Nexus suggested coverage")).toBeInTheDocument();
    expect(screen.getByText("Going Concern (suggested)")).toBeInTheDocument();
  });

  it("prefers a manually-curated verified membership over its System-Detected duplicate", async () => {
    vi.spyOn(issuerApi, "fetchIssuerDetail").mockResolvedValue({
      ...BASE_ISSUER,
      universe_memberships: [
        {
          collection_id: "col-curated",
          slug: "chapter-11-bankruptcy",
          name: "Chapter 11 / Bankruptcy",
          collection_type: "research_universe",
          curation_method: "manual_curated",
          rationale: "Curated rationale.",
          rationale_as_of_date: "2026-08-01",
          verification_status: "verified",
        },
        {
          collection_id: "col-system",
          slug: "system-chapter-11",
          name: "System-Detected: Chapter 11",
          collection_type: "research_universe",
          curation_method: "system_seeded",
          rationale: "System rationale.",
          rationale_as_of_date: "2026-08-01",
          verification_status: "verified",
        },
      ],
    });
    vi.spyOn(capitalStructureApi, "fetchCapitalStructure").mockResolvedValue(
      EMPTY_CAPITAL_STRUCTURE,
    );

    renderIssuerPage();

    await waitFor(() => {
      expect(screen.getByText("Chapter 11 / Bankruptcy")).toBeInTheDocument();
    });
    expect(screen.queryByText("System-Detected: Chapter 11")).not.toBeInTheDocument();
    expect(screen.queryByText("Chapter 11")).not.toBeInTheDocument();
    expect(screen.queryByText("Nexus suggested coverage")).not.toBeInTheDocument();
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

  it("renders the Distress Timeline section with events from the timeline API", async () => {
    vi.spyOn(issuerApi, "fetchIssuerDetail").mockResolvedValue(BASE_ISSUER);
    vi.spyOn(capitalStructureApi, "fetchCapitalStructure").mockResolvedValue(
      EMPTY_CAPITAL_STRUCTURE,
    );
    vi.spyOn(issuerTimelineApi, "fetchIssuerTimeline").mockResolvedValue({
      issuer_id: "iss-1",
      events: [
        {
          event_date: "2026-05-26",
          event_type: "bankruptcy_or_receivership",
          title: "Bankruptcy Or Receivership",
          short_summary: "Voluntary Chapter 11 petition filed.",
          why_it_matters: "Confirms the issuer is now in active bankruptcy proceedings.",
          severity: "high",
          confidence: 0.98,
          primary_source: { provider: "sec_edgar", label: "8-K filed 2026-05-26", url: null },
          supporting_sources: [],
          is_historical_discovery: false,
          evidence_count: 1,
        },
      ],
      total_events: 1,
      date_range_start: "2026-05-26",
      date_range_end: "2026-05-26",
      current_status: ["Chapter 11 / Bankruptcy"],
      most_recent_event_title: "Bankruptcy Or Receivership",
    });

    renderIssuerPage();

    await waitFor(() => {
      expect(screen.getByText("Distress Timeline")).toBeInTheDocument();
    });
    expect(screen.getByText("Voluntary Chapter 11 petition filed.")).toBeInTheDocument();
    expect(screen.getByText(/Chapter 11 \/ Bankruptcy/)).toBeInTheDocument();
  });

  it("shows the honest empty-timeline message when the issuer has no qualifying events", async () => {
    vi.spyOn(issuerApi, "fetchIssuerDetail").mockResolvedValue(BASE_ISSUER);
    vi.spyOn(capitalStructureApi, "fetchCapitalStructure").mockResolvedValue(
      EMPTY_CAPITAL_STRUCTURE,
    );

    renderIssuerPage();

    await waitFor(() => {
      expect(
        screen.getByText(
          "Nexus has not identified enough material credit events to build a distress timeline for this issuer yet.",
        ),
      ).toBeInTheDocument();
    });
  });

  it("renders SEC filings on file and never shows the contradictory 'no filings' message when they exist", async () => {
    vi.spyOn(issuerApi, "fetchIssuerDetail").mockResolvedValue({
      ...BASE_ISSUER,
      sec_filings: [
        {
          filing_id: "filing-1",
          form_type: "10-Q",
          filing_date: "2026-07-29",
          accession_no: "0000028823-26-000033",
          is_amendment: false,
          primary_document_url: "https://www.sec.gov/Archives/example.htm",
          provider: "sec_edgar",
          classification: "public",
          as_of_date: "2026-07-29",
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
      expect(screen.getByText("10-Q")).toBeInTheDocument();
    });
    expect(screen.getByText("0000028823-26-000033")).toBeInTheDocument();
    expect(
      screen.queryByText("No SEC filings on file for this issuer yet."),
    ).not.toBeInTheDocument();
  });

  it("shows an honest empty message when there are no SEC filings on file", async () => {
    vi.spyOn(issuerApi, "fetchIssuerDetail").mockResolvedValue(BASE_ISSUER);
    vi.spyOn(capitalStructureApi, "fetchCapitalStructure").mockResolvedValue(
      EMPTY_CAPITAL_STRUCTURE,
    );

    renderIssuerPage();

    await waitFor(() => {
      expect(screen.getByText("No SEC filings on file for this issuer yet.")).toBeInTheDocument();
    });
  });

  it("labels recent updates as data updates rather than issuer developments, and groups same-day security identifications", async () => {
    vi.spyOn(issuerApi, "fetchIssuerDetail").mockResolvedValue({
      ...BASE_ISSUER,
      recent_activity: [
        {
          occurred_on: "2026-08-09",
          category: "security_identified",
          headline: "Security identified: Issuer Co — Bond A",
          provider: "openfigi",
          source_url: null,
          as_of_date: "2026-08-09",
        },
        {
          occurred_on: "2026-08-09",
          category: "security_identified",
          headline: "Security identified: Issuer Co — Bond B",
          provider: "openfigi",
          source_url: null,
          as_of_date: "2026-08-09",
        },
        {
          occurred_on: "2026-08-09",
          category: "security_identified",
          headline: "Security identified: Issuer Co — Bond C",
          provider: "openfigi",
          source_url: null,
          as_of_date: "2026-08-09",
        },
        {
          occurred_on: "2026-07-29",
          category: "filing",
          headline: "10-Q filed",
          provider: "sec_edgar",
          source_url: null,
          as_of_date: "2026-07-29",
        },
      ],
    });
    vi.spyOn(capitalStructureApi, "fetchCapitalStructure").mockResolvedValue(
      EMPTY_CAPITAL_STRUCTURE,
    );

    renderIssuerPage();

    await waitFor(() => {
      expect(screen.getByText("Recent data updates")).toBeInTheDocument();
    });
    expect(screen.queryByText("What changed recently?")).not.toBeInTheDocument();
    // Three same-day security_identified rows collapse into one grouped row.
    expect(screen.getByText("3 securities identified through OpenFIGI")).toBeInTheDocument();
    expect(screen.queryByText("Security identified: Issuer Co — Bond A")).not.toBeInTheDocument();
    // A different category on a different day still renders individually.
    expect(screen.getByText("10-Q filed")).toBeInTheDocument();
  });
});
