import type { ReactElement, ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { CourtDocketSection } from "./CourtDocketSection";
import * as courtDocketApi from "../api/courtDocket";
import type { CourtDocketDetail, CourtDocketRow } from "../api/courtDocket";

function renderWithProviders(ui: ReactElement): void {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  }
  render(ui, { wrapper: Wrapper });
}

const BASE_DOCKET: CourtDocketRow = {
  id: "docket-1",
  issuer_id: "iss-1",
  issuer_legal_name: "EchoStar CORP",
  courtlistener_docket_id: 73709078,
  court: "United States Bankruptcy Court, S.D. Texas",
  docket_number: "26-90739",
  case_name: "Hughes Satellite Systems Corporation",
  nature_of_suit: null,
  chapter: "11",
  date_filed: "2026-08-02",
  courtlistener_url: "https://www.courtlistener.com/docket/73709078/",
  entry_count: 2,
  created_at: "2026-08-06T12:00:00Z",
};

const BASE_DETAIL: CourtDocketDetail = {
  docket: BASE_DOCKET,
  entries: [
    {
      id: "entry-2",
      entry_number: 2,
      entry_date: "2026-08-02",
      description: "Motion for Joint Administration.",
      document_available: false,
      documents: [],
    },
    {
      id: "entry-1",
      entry_number: 1,
      entry_date: "2026-08-02",
      description: "Chapter 11 Voluntary Petition Filed.",
      document_available: true,
      documents: [
        {
          id: "doc-1",
          availability: "recap_available",
          description: "Voluntary Petition",
          page_count: 12,
          is_sealed: false,
          recap_document_url: "https://www.courtlistener.com/docket/doc-1/",
        },
      ],
    },
  ],
};

afterEach(() => {
  vi.restoreAllMocks();
});

describe("CourtDocketSection", () => {
  it("shows an empty-state message when there are no dockets", () => {
    renderWithProviders(<CourtDocketSection dockets={[]} />);

    expect(screen.getByText("No court docket on file for this issuer.")).toBeInTheDocument();
  });

  it("renders the docket header with case name, court, and chapter", async () => {
    vi.spyOn(courtDocketApi, "fetchCourtDocketDetail").mockResolvedValue(BASE_DETAIL);

    renderWithProviders(<CourtDocketSection dockets={[BASE_DOCKET]} />);

    expect(screen.getByText("Hughes Satellite Systems Corporation")).toBeInTheDocument();
    expect(screen.getByText(/26-90739/)).toBeInTheDocument();
    expect(screen.getByText("Chapter 11")).toBeInTheDocument();
    const link = screen.getByText("View on CourtListener").closest("a");
    expect(link).toHaveAttribute("href", "https://www.courtlistener.com/docket/73709078/");
  });

  it("renders docket entries sorted with the most recent first", async () => {
    vi.spyOn(courtDocketApi, "fetchCourtDocketDetail").mockResolvedValue(BASE_DETAIL);

    renderWithProviders(<CourtDocketSection dockets={[BASE_DOCKET]} />);

    await waitFor(() => {
      expect(screen.getByText("Motion for Joint Administration.")).toBeInTheDocument();
    });
    expect(screen.getByText("Chapter 11 Voluntary Petition Filed.")).toBeInTheDocument();
    expect(screen.getByText("Available")).toBeInTheDocument();
    expect(screen.getByText("Not on RECAP")).toBeInTheDocument();
  });

  it("shows an error message when entries fail to load", async () => {
    vi.spyOn(courtDocketApi, "fetchCourtDocketDetail").mockRejectedValue(
      new Error("Network unreachable"),
    );

    renderWithProviders(<CourtDocketSection dockets={[BASE_DOCKET]} />);

    await waitFor(() => {
      expect(screen.getByText("Could not load docket entries.")).toBeInTheDocument();
    });
  });
});
