import type { ReactElement, ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router";
import { MorningResearchBriefPage } from "./MorningResearchBriefPage";
import * as filingMonitorApi from "../api/filingMonitor";
import * as researchUniverseApi from "../api/researchUniverse";
import type { AlertRow, AlertsPage, MorningBriefSummary } from "../api/filingMonitor";

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

const BASE_SUMMARY: MorningBriefSummary = {
  last_successful_run: {
    id: "run-1",
    started_at: "2026-08-06T09:00:00Z",
    completed_at: "2026-08-06T09:05:00Z",
    status: "success",
    mode: "delta",
    previous_watermark: "2026-08-05T09:00:00Z",
    resulting_watermark: "2026-08-06T09:00:00Z",
    issuers_checked: 24,
    filings_discovered: 1,
    filings_processed: 1,
    alerts_created: 1,
    errors_count: 0,
    error_summary: null,
    backfill_lookback_days: null,
    is_backfill: false,
  },
  latest_run: {
    id: "run-1",
    started_at: "2026-08-06T09:00:00Z",
    completed_at: "2026-08-06T09:05:00Z",
    status: "success",
    mode: "delta",
    previous_watermark: "2026-08-05T09:00:00Z",
    resulting_watermark: "2026-08-06T09:00:00Z",
    issuers_checked: 24,
    filings_discovered: 1,
    filings_processed: 1,
    alerts_created: 1,
    errors_count: 0,
    error_summary: null,
    backfill_lookback_days: null,
    is_backfill: false,
  },
  universes_monitored: 15,
  issuers_monitored: 24,
  new_evidence_discovered: 1,
  alerts_total: 1,
  alerts_by_severity: { high: 1, medium: 0, low: 0 },
  deterministic_alert_count: 1,
  ai_assisted_alert_count: 0,
  failures_count: 0,
  no_new_alerts: false,
};

const BASE_ALERT: AlertRow = {
  id: "alert-1",
  issuer_id: "issuer-1",
  issuer_legal_name: "Acme Distressed Co",
  issuer_ticker: "ACME",
  universe_names: ["Distressed Core"],
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
  triggered_at: "2026-08-06T09:00:00Z",
  status: "new",
  acknowledged_at: null,
  acknowledged_by: null,
  dismissed_at: null,
  dismissed_by: null,
  dismissal_reason: null,
  is_backfill: false,
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
  it("renders the summary bar and alert cards", async () => {
    vi.spyOn(filingMonitorApi, "fetchMorningBrief").mockResolvedValue(BASE_SUMMARY);
    vi.spyOn(researchUniverseApi, "fetchResearchUniverses").mockResolvedValue(NO_UNIVERSES);
    vi.spyOn(filingMonitorApi, "fetchAlerts").mockResolvedValue(ONE_ALERT_PAGE);

    renderWithProviders(<MorningResearchBriefPage />);

    await waitFor(() => {
      expect(screen.getByText("Alerts")).toBeInTheDocument();
    });
    expect(
      screen.getByText("Potential bankruptcy or receivership filing detected in a new 8-K."),
    ).toBeInTheDocument();
    expect(screen.getByText("New Research Alerts — Since Last Successful Run")).toBeInTheDocument();
  });

  it("shows a success message when there are no alerts matching the filters", async () => {
    vi.spyOn(filingMonitorApi, "fetchMorningBrief").mockResolvedValue({
      ...BASE_SUMMARY,
      alerts_total: 0,
      no_new_alerts: true,
    });
    vi.spyOn(researchUniverseApi, "fetchResearchUniverses").mockResolvedValue(NO_UNIVERSES);
    vi.spyOn(filingMonitorApi, "fetchAlerts").mockResolvedValue({
      alerts: [],
      total: 0,
      page: 1,
      page_size: 100,
    });

    renderWithProviders(<MorningResearchBriefPage />);

    await waitFor(() => {
      expect(
        screen.getByText("No research alerts match these filters — nothing to review right now."),
      ).toBeInTheDocument();
    });
  });

  it("shows an error message when the alerts API call fails", async () => {
    vi.spyOn(filingMonitorApi, "fetchMorningBrief").mockResolvedValue(BASE_SUMMARY);
    vi.spyOn(researchUniverseApi, "fetchResearchUniverses").mockResolvedValue(NO_UNIVERSES);
    vi.spyOn(filingMonitorApi, "fetchAlerts").mockRejectedValue(new Error("Network unreachable"));

    renderWithProviders(<MorningResearchBriefPage />);

    await waitFor(() => {
      expect(screen.getByText(/Could not load alerts/)).toBeInTheDocument();
    });
  });

  it("shows an error message when the brief summary API call fails", async () => {
    vi.spyOn(filingMonitorApi, "fetchMorningBrief").mockRejectedValue(
      new Error("Network unreachable"),
    );
    vi.spyOn(researchUniverseApi, "fetchResearchUniverses").mockResolvedValue(NO_UNIVERSES);
    vi.spyOn(filingMonitorApi, "fetchAlerts").mockResolvedValue(ONE_ALERT_PAGE);

    renderWithProviders(<MorningResearchBriefPage />);

    await waitFor(() => {
      expect(screen.getByText(/Could not load the brief summary/)).toBeInTheDocument();
    });
  });
});
