import type { ReactElement, ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router";
import { MorningResearchBriefPage } from "./MorningResearchBriefPage";
import * as filingMonitorApi from "../api/filingMonitor";
import * as researchUniverseApi from "../api/researchUniverse";
import type {
  AlertRow,
  AlertsPage,
  IssuerDevelopment,
  MorningBriefSummary,
} from "../api/filingMonitor";

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

const NO_UNIVERSES = { universes: [] };

const RUN_DETAILS: MorningBriefSummary["run_details"] = {
  last_successful_run: {
    id: "run-1",
    pipeline: "market_discovery",
    started_at: "2026-08-08T06:00:00Z",
    completed_at: "2026-08-08T06:05:00Z",
    status: "success",
    mode: "delta",
    window_start_date: "2026-08-07",
    window_end_date: "2026-08-07",
    research_day: "2026-08-07",
    errors_count: 0,
  },
  latest_run: {
    id: "run-1",
    pipeline: "market_discovery",
    started_at: "2026-08-08T06:00:00Z",
    completed_at: "2026-08-08T06:05:00Z",
    status: "success",
    mode: "delta",
    window_start_date: "2026-08-07",
    window_end_date: "2026-08-07",
    research_day: "2026-08-07",
    errors_count: 0,
  },
  since: "2026-08-08T06:00:00Z",
  universes_monitored: 15,
  issuers_monitored: 24,
  new_sec_filings: 1,
  new_court_events: 0,
  new_research_evidence: 1,
  failures_count: 0,
};

const BASE_ALERT: AlertRow = {
  id: "alert-1",
  issuer_id: "issuer-1",
  issuer_legal_name: "Acme Distressed Co",
  issuer_ticker: "ACME",
  universe_names: ["Distressed Core"],
  watchlist_names: [],
  category: "bankruptcy_or_receivership",
  severity: "high",
  headline: "Potential bankruptcy or receivership filing detected in a new 8-K.",
  explanation: "An 8-K disclosed a chapter 11 filing under Item 1.03.",
  evidence_ids: ["evidence-1"],
  detection_method: "deterministic",
  ai_assisted: false,
  confidence: 0.92,
  primary_evidence_provider: "sec_edgar",
  primary_source_label: "8-K filed 2026-08-01, Accession 0001234-26-000123",
  primary_source_url: "https://www.sec.gov/Archives/edgar/data/example.htm",
  as_of_date: "2026-08-01",
  triggered_at: "2026-08-08T09:00:00Z",
  status: "new",
  acknowledged_at: null,
  acknowledged_by: null,
  dismissed_at: null,
  dismissed_by: null,
  dismissal_reason: null,
  is_backfill: false,
};

const BASE_DEVELOPMENT: IssuerDevelopment = {
  issuer_id: "issuer-1",
  issuer_legal_name: "Acme Distressed Co",
  issuer_ticker: "ACME",
  max_severity: "high",
  alerts: [BASE_ALERT],
  universe_changes: [],
};

const BASE_SUMMARY: MorningBriefSummary = {
  latest_research_day: "2026-08-07",
  preceding_research_day: "2026-08-06",
  research_cycle_is_fallback: false,
  as_of: "2026-08-08T10:00:00Z",
  issuers_with_developments: 1,
  severity_counts: { high: 1, medium: 0, low: 0 },
  new_developments: [BASE_DEVELOPMENT],
  historical_intelligence: [],
  historical_intelligence_issuer_count: 0,
  no_material_changes: false,
  run_details: RUN_DETAILS,
};

const ONE_ALERT_PAGE: AlertsPage = {
  alerts: [BASE_ALERT],
  total: 1,
  page: 1,
  page_size: 100,
};

afterEach(() => {
  vi.restoreAllMocks();
});

describe("MorningResearchBriefPage", () => {
  it("renders the summary bar and issuer development cards", async () => {
    vi.spyOn(filingMonitorApi, "fetchMorningBrief").mockResolvedValue(BASE_SUMMARY);
    vi.spyOn(researchUniverseApi, "fetchResearchUniverses").mockResolvedValue(NO_UNIVERSES);

    renderWithProviders(<MorningResearchBriefPage />);

    await waitFor(() => {
      expect(screen.getByText("Issuers with developments")).toBeInTheDocument();
    });
    expect(
      screen.getByText("Potential bankruptcy or receivership filing detected in a new 8-K."),
    ).toBeInTheDocument();
    expect(screen.getByText("What changed in the latest research cycle")).toBeInTheDocument();
    expect(
      screen.getByText("Latest research day: Aug 7, 2026 · Compared with: Aug 6, 2026"),
    ).toBeInTheDocument();
    // Appears twice: once in the IssuerDevelopmentCard header, once in the
    // nested AlertCard's own issuer link.
    expect(screen.getAllByText("Acme Distressed Co (ACME)").length).toBeGreaterThan(0);
  });

  it("never calls any view-recording endpoint — the window is derived server-side, not from page visits", async () => {
    const fetchMorningBriefSpy = vi
      .spyOn(filingMonitorApi, "fetchMorningBrief")
      .mockResolvedValue(BASE_SUMMARY);
    vi.spyOn(researchUniverseApi, "fetchResearchUniverses").mockResolvedValue(NO_UNIVERSES);

    renderWithProviders(<MorningResearchBriefPage />);

    await waitFor(() => {
      expect(fetchMorningBriefSpy).toHaveBeenCalledTimes(1);
    });
    // `filingMonitorApi` has no `recordMorningBriefView`/view-recording
    // export at all anymore (PLAN.md Milestone 7.5.2's business-day-cycle
    // correction) — nothing to spy on or assert was never called, which is
    // itself the point: there is no such call to make.
    expect("recordMorningBriefView" in filingMonitorApi).toBe(false);
  });

  it("shows the identical comparison window across repeated fetches (idempotent refresh)", async () => {
    // The brief's window is a pure function of the API response — refetching
    // (e.g. a background revalidation) with the same underlying data must
    // render the same window every time.
    const fetchMorningBriefSpy = vi
      .spyOn(filingMonitorApi, "fetchMorningBrief")
      .mockResolvedValue(BASE_SUMMARY);
    vi.spyOn(researchUniverseApi, "fetchResearchUniverses").mockResolvedValue(NO_UNIVERSES);

    const { unmount } = render(<MorningResearchBriefPage />, {
      wrapper: ({ children }) => (
        <QueryClientProvider
          client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
        >
          <MemoryRouter>{children}</MemoryRouter>
        </QueryClientProvider>
      ),
    });
    await waitFor(() => {
      expect(
        screen.getByText("Latest research day: Aug 7, 2026 · Compared with: Aug 6, 2026"),
      ).toBeInTheDocument();
    });
    unmount();

    // A second, independent mount ("reopening" the page) against the same
    // server state must show the identical window.
    renderWithProviders(<MorningResearchBriefPage />);
    await waitFor(() => {
      expect(
        screen.getByText("Latest research day: Aug 7, 2026 · Compared with: Aug 6, 2026"),
      ).toBeInTheDocument();
    });
    expect(fetchMorningBriefSpy).toHaveBeenCalledTimes(2);
  });

  it("shows the fallback message when no research cycle has ever completed", async () => {
    vi.spyOn(filingMonitorApi, "fetchMorningBrief").mockResolvedValue({
      ...BASE_SUMMARY,
      research_cycle_is_fallback: true,
    });
    vi.spyOn(researchUniverseApi, "fetchResearchUniverses").mockResolvedValue(NO_UNIVERSES);

    renderWithProviders(<MorningResearchBriefPage />);

    await waitFor(() => {
      expect(screen.getByText(/No completed research cycle yet/)).toBeInTheDocument();
    });
  });

  it("shows a success message when there are no material developments", async () => {
    vi.spyOn(filingMonitorApi, "fetchMorningBrief").mockResolvedValue({
      ...BASE_SUMMARY,
      issuers_with_developments: 0,
      severity_counts: { high: 0, medium: 0, low: 0 },
      new_developments: [],
      no_material_changes: true,
    });
    vi.spyOn(researchUniverseApi, "fetchResearchUniverses").mockResolvedValue(NO_UNIVERSES);

    renderWithProviders(<MorningResearchBriefPage />);

    await waitFor(() => {
      expect(
        screen.getByText("No material research developments in the latest research cycle."),
      ).toBeInTheDocument();
    });
  });

  it("renders historical intelligence in its own de-emphasized section", async () => {
    const historicalAlert: AlertRow = { ...BASE_ALERT, id: "alert-2", is_backfill: true };
    vi.spyOn(filingMonitorApi, "fetchMorningBrief").mockResolvedValue({
      ...BASE_SUMMARY,
      new_developments: [],
      issuers_with_developments: 0,
      no_material_changes: true,
      historical_intelligence: [
        { ...BASE_DEVELOPMENT, issuer_id: "issuer-2", alerts: [historicalAlert] },
      ],
      historical_intelligence_issuer_count: 1,
    });
    vi.spyOn(researchUniverseApi, "fetchResearchUniverses").mockResolvedValue(NO_UNIVERSES);

    renderWithProviders(<MorningResearchBriefPage />);

    await waitFor(() => {
      expect(screen.getByText("Newly Discovered Historical Intelligence")).toBeInTheDocument();
    });
  });

  it("shows an error message when the brief summary API call fails", async () => {
    vi.spyOn(filingMonitorApi, "fetchMorningBrief").mockRejectedValue(
      new Error("Network unreachable"),
    );
    vi.spyOn(researchUniverseApi, "fetchResearchUniverses").mockResolvedValue(NO_UNIVERSES);

    renderWithProviders(<MorningResearchBriefPage />);

    await waitFor(() => {
      expect(screen.getByText(/Could not load the brief summary/)).toBeInTheDocument();
    });
  });

  it("shows the all-time flat alert list only when the historical toggle is on", async () => {
    vi.spyOn(filingMonitorApi, "fetchMorningBrief").mockResolvedValue(BASE_SUMMARY);
    vi.spyOn(researchUniverseApi, "fetchResearchUniverses").mockResolvedValue(NO_UNIVERSES);
    const fetchAlertsSpy = vi
      .spyOn(filingMonitorApi, "fetchAlerts")
      .mockResolvedValue(ONE_ALERT_PAGE);

    renderWithProviders(<MorningResearchBriefPage />);

    await waitFor(() => {
      expect(screen.getByText("Issuers with developments")).toBeInTheDocument();
    });
    // The default (non-historical) view never calls the flat alerts endpoint.
    expect(fetchAlertsSpy).not.toHaveBeenCalled();

    screen.getByLabelText("Show historical alerts (all-time, not just this period)").click();

    await waitFor(() => {
      expect(screen.getByText("All Research Alerts — All-Time")).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(fetchAlertsSpy).toHaveBeenCalled();
    });
  });
});
