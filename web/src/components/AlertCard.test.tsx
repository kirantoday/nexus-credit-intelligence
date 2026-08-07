import type { ReactElement, ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router";
import { AlertCard } from "./AlertCard";
import type { AlertEvidenceDetail, AlertRow } from "../api/filingMonitor";
import * as filingMonitorApi from "../api/filingMonitor";

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

const EVIDENCE_DETAIL: AlertEvidenceDetail = {
  alert: BASE_ALERT,
  evidence: [
    {
      id: "evidence-1",
      issuer_id: "issuer-1",
      issuer_legal_name: "Acme Distressed Co",
      evidence_provider: "sec_edgar",
      source_type: "sec_filing",
      filing_id: "filing-1",
      evidence_type: "chapter_11",
      severity: "high",
      source_section: null,
      source_item: "Item 1.03",
      matched_rule: "8k_item_1_03_bankruptcy",
      evidence_excerpt: "the Company filed voluntary petitions for relief under chapter 11",
      confidence: 0.95,
      detection_method: "deterministic",
      review_status: "unreviewed",
      created_at: "2026-08-06T08:00:00Z",
    },
  ],
};

afterEach(() => {
  vi.restoreAllMocks();
});

describe("AlertCard", () => {
  it("renders headline, explanation, severity, and detection method", () => {
    renderWithProviders(<AlertCard alert={BASE_ALERT} />);

    expect(
      screen.getByText("Potential bankruptcy or receivership filing detected in a new 8-K."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("An 8-K disclosed a chapter 11 filing under Item 1.03."),
    ).toBeInTheDocument();
    expect(screen.getByText("High")).toBeInTheDocument();
    expect(screen.getByText("Deterministic")).toBeInTheDocument();
  });

  it("links the issuer name to Issuer Detail", () => {
    renderWithProviders(<AlertCard alert={BASE_ALERT} />);

    const link = screen.getByText("Acme Distressed Co (ACME)").closest("a");
    expect(link).toHaveAttribute("href", "/issuers/issuer-1");
  });

  it("shows a Historical chip only when is_backfill is true", () => {
    renderWithProviders(<AlertCard alert={{ ...BASE_ALERT, is_backfill: true }} />);

    expect(screen.getByText("Historical")).toBeInTheDocument();
  });

  it("does not show the backfill chip for a live alert", () => {
    renderWithProviders(<AlertCard alert={BASE_ALERT} />);

    expect(screen.queryByText("Historical")).not.toBeInTheDocument();
  });

  it("labels AI-assisted alerts distinctly from deterministic ones", () => {
    renderWithProviders(<AlertCard alert={{ ...BASE_ALERT, ai_assisted: true }} />);

    expect(screen.getByText("AI-assisted")).toBeInTheDocument();
    expect(screen.queryByText("Deterministic")).not.toBeInTheDocument();
  });

  it("expands to show evidence excerpts when 'Why was this flagged?' is clicked", async () => {
    vi.spyOn(filingMonitorApi, "fetchAlertEvidence").mockResolvedValue(EVIDENCE_DETAIL);
    renderWithProviders(<AlertCard alert={BASE_ALERT} />);

    await userEvent.click(screen.getByText("Why was this flagged?"));

    await waitFor(() => {
      expect(
        screen.getByText(/the Company filed voluntary petitions for relief under chapter 11/),
      ).toBeInTheDocument();
    });
    expect(screen.getByText("rule: 8k_item_1_03_bankruptcy")).toBeInTheDocument();
    expect(screen.getByText("Hide evidence")).toBeInTheDocument();
  });

  it("calls onAcknowledge with the alert id when Acknowledge is clicked", async () => {
    const onAcknowledge = vi.fn();
    renderWithProviders(<AlertCard alert={BASE_ALERT} onAcknowledge={onAcknowledge} />);

    await userEvent.click(screen.getByText("Acknowledge"));

    expect(onAcknowledge).toHaveBeenCalledWith("alert-1");
  });

  it("calls onDismiss with the alert id when Dismiss is clicked", async () => {
    const onDismiss = vi.fn();
    renderWithProviders(<AlertCard alert={BASE_ALERT} onDismiss={onDismiss} />);

    await userEvent.click(screen.getByText("Dismiss"));

    expect(onDismiss).toHaveBeenCalledWith("alert-1");
  });

  it("does not show an Acknowledge button for an already-acknowledged alert", () => {
    const onAcknowledge = vi.fn();
    renderWithProviders(
      <AlertCard alert={{ ...BASE_ALERT, status: "acknowledged" }} onAcknowledge={onAcknowledge} />,
    );

    expect(screen.queryByText("Acknowledge")).not.toBeInTheDocument();
  });

  it("does not show a Dismiss button for an already-dismissed alert", () => {
    const onDismiss = vi.fn();
    renderWithProviders(
      <AlertCard alert={{ ...BASE_ALERT, status: "dismissed" }} onDismiss={onDismiss} />,
    );

    expect(screen.queryByText("Dismiss")).not.toBeInTheDocument();
  });
});
