import type { ReactElement, ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router";
import { ResearchNotesWorkspacePage } from "./ResearchNotesWorkspacePage";
import * as researchNoteApi from "../api/researchNote";
import type { ResearchNoteListResponse, ResearchNoteSummary } from "../api/researchNote";

function renderWithProviders(): void {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  function Wrapper({ children }: { children: ReactNode }): ReactElement {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/research-notes"]}>{children}</MemoryRouter>
      </QueryClientProvider>
    );
  }
  render(
    <Routes>
      <Route path="/research-notes" element={<ResearchNotesWorkspacePage />} />
    </Routes>,
    { wrapper: Wrapper },
  );
}

function makeNote(overrides: Partial<ResearchNoteSummary> = {}): ResearchNoteSummary {
  return {
    id: "note-1",
    issuer_id: "issuer-1",
    security_id: null,
    title: "Covenant Stress Thesis",
    thesis_status: "active",
    conviction: "medium",
    bull_case: null,
    base_case: null,
    bear_case: null,
    catalysts: null,
    risks: null,
    invalidation_conditions: null,
    evidence_refs: null,
    access_classification: "standard",
    author_user_id: "demo-analyst",
    is_demo: false,
    current_version_number: 1,
    is_archived: false,
    archived_at: null,
    archived_by: null,
    created_at: "2026-08-01T00:00:00Z",
    updated_at: "2026-08-01T00:00:00Z",
    issuer_legal_name: "Trinseo PLC",
    issuer_ticker: "TSEOQ",
    ...overrides,
  };
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("ResearchNotesWorkspacePage", () => {
  it("shows a loading state", () => {
    vi.spyOn(researchNoteApi, "fetchResearchNotes").mockReturnValue(new Promise(() => {}));
    renderWithProviders();
    expect(screen.getByRole("progressbar")).toBeInTheDocument();
  });

  it("shows an error state", async () => {
    vi.spyOn(researchNoteApi, "fetchResearchNotes").mockRejectedValue(new Error("network error"));
    renderWithProviders();
    await waitFor(() => {
      expect(screen.getByText("Could not load research notes.")).toBeInTheDocument();
    });
  });

  it("shows an empty state when there are no research notes", async () => {
    vi.spyOn(researchNoteApi, "fetchResearchNotes").mockResolvedValue({
      notes: [],
    } satisfies ResearchNoteListResponse);
    renderWithProviders();
    await waitFor(() => {
      expect(screen.getByText(/No research notes yet/)).toBeInTheDocument();
    });
  });

  it("shows notes across issuers with issuer name, ticker, thesis status, conviction, and updated date", async () => {
    vi.spyOn(researchNoteApi, "fetchResearchNotes").mockResolvedValue({
      notes: [
        makeNote(),
        makeNote({
          id: "note-2",
          issuer_id: "issuer-2",
          title: "No-Ticker Issuer Thesis",
          issuer_legal_name: "Private Debt Co",
          issuer_ticker: null,
          thesis_status: "monitoring",
          conviction: null,
        }),
      ],
    });

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText("Covenant Stress Thesis")).toBeInTheDocument();
    });
    expect(screen.getByText("Trinseo PLC")).toBeInTheDocument();
    expect(screen.getByText("TSEOQ")).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
    expect(screen.getByText("Medium Conviction")).toBeInTheDocument();

    expect(screen.getByText("No-Ticker Issuer Thesis")).toBeInTheDocument();
    expect(screen.getByText("Private Debt Co")).toBeInTheDocument();
    expect(screen.getByText("Monitoring")).toBeInTheDocument();
  });

  it("links a note title to its ResearchNotePage", async () => {
    vi.spyOn(researchNoteApi, "fetchResearchNotes").mockResolvedValue({
      notes: [makeNote({ id: "note-99" })],
    });

    renderWithProviders();

    const link = await screen.findByRole("link", { name: "Covenant Stress Thesis" });
    expect(link).toHaveAttribute("href", "/research-notes/note-99");
  });

  it("links the issuer name to Issuer Detail", async () => {
    vi.spyOn(researchNoteApi, "fetchResearchNotes").mockResolvedValue({
      notes: [makeNote({ issuer_id: "issuer-42" })],
    });

    renderWithProviders();

    const link = await screen.findByRole("link", { name: "Trinseo PLC" });
    expect(link).toHaveAttribute("href", "/issuers/issuer-42");
  });

  it("fetches without an issuer_id filter (cross-issuer)", async () => {
    const fetchSpy = vi
      .spyOn(researchNoteApi, "fetchResearchNotes")
      .mockResolvedValue({ notes: [] });

    renderWithProviders();

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith(undefined, false);
    });
  });
});
