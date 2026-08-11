import type { ReactElement, ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router";
import { AlertsPage } from "./AlertsPage";
import * as filingMonitorApi from "../api/filingMonitor";
import * as researchUniverseApi from "../api/researchUniverse";
import * as watchlistApi from "../api/watchlist";
import type {
  AlertRow,
  AlertsPage as AlertsPageResponse,
  AlertsSummary,
} from "../api/filingMonitor";

function renderWithProviders(ui: ReactElement): void {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>{children}</MemoryRouter>
      </QueryClientProvider>
    );
  }
  render(ui, { wrapper: Wrapper });
}

const SUMMARY: AlertsSummary = {
  new_count: 5,
  high_severity_count: 2,
  watchlist_alert_count: 3,
  acknowledged_count: 7,
};

function makeAlert(overrides: Partial<AlertRow> = {}): AlertRow {
  return {
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
    primary_source_label: "8-K filed 2026-08-01",
    primary_source_url: "https://www.sec.gov/example.htm",
    as_of_date: "2026-08-01",
    triggered_at: "2026-08-06T09:00:00Z",
    status: "new",
    acknowledged_at: null,
    acknowledged_by: null,
    dismissed_at: null,
    dismissed_by: null,
    dismissal_reason: null,
    is_backfill: false,
    ...overrides,
  };
}

function makeAlertsPage(alerts: AlertRow[], total = alerts.length): AlertsPageResponse {
  return { alerts, total, page: 1, page_size: 25 };
}

function mockCommonQueries(): void {
  vi.spyOn(filingMonitorApi, "fetchAlertsSummary").mockResolvedValue(SUMMARY);
  vi.spyOn(researchUniverseApi, "fetchResearchUniverses").mockResolvedValue({ universes: [] });
  vi.spyOn(watchlistApi, "fetchWatchlists").mockResolvedValue({
    watchlists: [
      {
        id: "watchlist-1",
        slug: "demo-watchlist",
        name: "Demo Watchlist",
        description: "",
        issuer_count: 6,
        issuers_with_new_developments: 1,
        high_severity_count: 0,
        new_alert_count: 3,
        high_severity_alert_count: 2,
        last_activity_at: null,
        created_at: "2026-08-01T00:00:00Z",
        updated_at: "2026-08-01T00:00:00Z",
        contains_issuer: null,
      },
    ],
  });
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("AlertsPage", () => {
  it("renders the summary tiles from real backend counts", async () => {
    mockCommonQueries();
    vi.spyOn(filingMonitorApi, "fetchAlerts").mockResolvedValue(makeAlertsPage([makeAlert()]));

    renderWithProviders(<AlertsPage />);

    await waitFor(() => {
      expect(screen.getByText("5")).toBeInTheDocument();
    });
    expect(screen.getByText("New")).toBeInTheDocument();
    expect(screen.getByText("High Severity")).toBeInTheDocument();
    expect(screen.getByText("Watchlist Alerts")).toBeInTheDocument();
    expect(screen.getByText("Acknowledged")).toBeInTheDocument();
  });

  it("renders alert cards from the paginated list", async () => {
    mockCommonQueries();
    vi.spyOn(filingMonitorApi, "fetchAlerts").mockResolvedValue(makeAlertsPage([makeAlert()]));

    renderWithProviders(<AlertsPage />);

    await waitFor(() => {
      expect(screen.getByText("Acme Distressed Co (ACME)")).toBeInTheDocument();
    });
  });

  it("shows an empty state when no alerts match", async () => {
    mockCommonQueries();
    vi.spyOn(filingMonitorApi, "fetchAlerts").mockResolvedValue(makeAlertsPage([]));

    renderWithProviders(<AlertsPage />);

    await waitFor(() => {
      expect(screen.getByText(/No alerts match these filters/)).toBeInTheDocument();
    });
  });

  it("re-fetches with the status filter applied", async () => {
    mockCommonQueries();
    const fetchSpy = vi
      .spyOn(filingMonitorApi, "fetchAlerts")
      .mockResolvedValue(makeAlertsPage([makeAlert()]));
    const user = userEvent.setup();

    renderWithProviders(<AlertsPage />);
    await waitFor(() => {
      expect(screen.getByText("Acme Distressed Co (ACME)")).toBeInTheDocument();
    });

    await user.click(screen.getByLabelText("Status"));
    await user.click(await screen.findByRole("option", { name: "Acknowledged" }));

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenLastCalledWith(
        expect.objectContaining({ status: "acknowledged" }),
      );
    });
  });

  it("re-fetches with the watchlist filter applied", async () => {
    mockCommonQueries();
    const fetchSpy = vi
      .spyOn(filingMonitorApi, "fetchAlerts")
      .mockResolvedValue(makeAlertsPage([makeAlert()]));
    const user = userEvent.setup();

    renderWithProviders(<AlertsPage />);
    await waitFor(() => {
      expect(screen.getByText("Acme Distressed Co (ACME)")).toBeInTheDocument();
    });

    await user.click(screen.getByLabelText("Watchlist"));
    await user.click(await screen.findByRole("option", { name: "Demo Watchlist" }));

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenLastCalledWith(
        expect.objectContaining({ watchlistId: "watchlist-1" }),
      );
    });
  });

  it("acknowledges an alert", async () => {
    mockCommonQueries();
    vi.spyOn(filingMonitorApi, "fetchAlerts").mockResolvedValue(makeAlertsPage([makeAlert()]));
    const ackSpy = vi
      .spyOn(filingMonitorApi, "acknowledgeAlert")
      .mockResolvedValue(makeAlert({ status: "acknowledged" }));
    const user = userEvent.setup();

    renderWithProviders(<AlertsPage />);
    await waitFor(() => {
      expect(screen.getByText("Acme Distressed Co (ACME)")).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: "Acknowledge" }));

    await waitFor(() => {
      expect(ackSpy).toHaveBeenCalledWith("alert-1", undefined);
    });
  });

  it("dismisses an alert", async () => {
    mockCommonQueries();
    vi.spyOn(filingMonitorApi, "fetchAlerts").mockResolvedValue(makeAlertsPage([makeAlert()]));
    const dismissSpy = vi
      .spyOn(filingMonitorApi, "dismissAlert")
      .mockResolvedValue(makeAlert({ status: "dismissed" }));
    const user = userEvent.setup();

    renderWithProviders(<AlertsPage />);
    await waitFor(() => {
      expect(screen.getByText("Acme Distressed Co (ACME)")).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: "Dismiss" }));

    await waitFor(() => {
      expect(dismissSpy).toHaveBeenCalled();
    });
  });

  it("links the issuer name to Issuer Detail", async () => {
    mockCommonQueries();
    vi.spyOn(filingMonitorApi, "fetchAlerts").mockResolvedValue(makeAlertsPage([makeAlert()]));

    renderWithProviders(<AlertsPage />);

    await waitFor(() => {
      expect(screen.getByText("Acme Distressed Co (ACME)")).toBeInTheDocument();
    });
    const link = screen.getByRole("link", { name: /Acme Distressed Co/ });
    expect(link).toHaveAttribute("href", "/issuers/issuer-1");
  });

  it("shows a source link", async () => {
    mockCommonQueries();
    vi.spyOn(filingMonitorApi, "fetchAlerts").mockResolvedValue(makeAlertsPage([makeAlert()]));

    renderWithProviders(<AlertsPage />);

    await waitFor(() => {
      const sourceLink = screen.getByRole("link", { name: "8-K filed 2026-08-01" });
      expect(sourceLink).toHaveAttribute("href", "https://www.sec.gov/example.htm");
    });
  });

  it("shows watchlist membership chips distinctly from universe chips", async () => {
    mockCommonQueries();
    vi.spyOn(filingMonitorApi, "fetchAlerts").mockResolvedValue(
      makeAlertsPage([makeAlert({ watchlist_names: ["Demo Watchlist"] })]),
    );

    renderWithProviders(<AlertsPage />);

    await waitFor(() => {
      expect(screen.getByText("Demo Watchlist")).toBeInTheDocument();
    });
    expect(screen.getByText("Distressed Core")).toBeInTheDocument();
  });

  it("shows pagination controls reflecting the real total", async () => {
    mockCommonQueries();
    vi.spyOn(filingMonitorApi, "fetchAlerts").mockResolvedValue(makeAlertsPage([makeAlert()], 42));

    renderWithProviders(<AlertsPage />);

    await waitFor(() => {
      expect(screen.getByText((content) => content.includes("42"))).toBeInTheDocument();
    });
  });
});
