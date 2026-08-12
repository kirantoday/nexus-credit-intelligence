import type { ReactElement, ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router";
import { ResearchNotesSection } from "./ResearchNotesSection";
import * as researchNoteApi from "../api/researchNote";
import type { ResearchNoteListResponse, ResearchNoteSummary } from "../api/researchNote";

function renderWithProviders(issuerId = "issuer-1"): void {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  function Wrapper({ children }: { children: ReactNode }): ReactElement {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>{children}</MemoryRouter>
      </QueryClientProvider>
    );
  }
  render(<ResearchNotesSection issuerId={issuerId} />, { wrapper: Wrapper });
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

describe("ResearchNotesSection", () => {
  it("shows an empty state when the issuer has no research notes", async () => {
    vi.spyOn(researchNoteApi, "fetchResearchNotes").mockResolvedValue({
      notes: [],
    } satisfies ResearchNoteListResponse);

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText(/No research notes yet for this issuer/)).toBeInTheDocument();
    });
  });

  it("renders a note's title, thesis status, and conviction", async () => {
    vi.spyOn(researchNoteApi, "fetchResearchNotes").mockResolvedValue({
      notes: [makeNote()],
    });

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText("Covenant Stress Thesis")).toBeInTheDocument();
    });
    expect(screen.getByText("Active")).toBeInTheDocument();
    expect(screen.getByText("Medium Conviction")).toBeInTheDocument();
  });

  it("shows a Demo Research Note badge for demo notes", async () => {
    vi.spyOn(researchNoteApi, "fetchResearchNotes").mockResolvedValue({
      notes: [makeNote({ is_demo: true })],
    });

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText("Demo Research Note")).toBeInTheDocument();
    });
  });

  it("links Write Research Note to the issuer-scoped create route", async () => {
    vi.spyOn(researchNoteApi, "fetchResearchNotes").mockResolvedValue({ notes: [] });

    renderWithProviders("issuer-42");

    const link = await screen.findByRole("link", { name: /Write Research Note/ });
    expect(link).toHaveAttribute("href", "/issuers/issuer-42/research-notes/new");
  });

  it("links a note card to its detail route", async () => {
    vi.spyOn(researchNoteApi, "fetchResearchNotes").mockResolvedValue({
      notes: [makeNote({ id: "note-99" })],
    });

    renderWithProviders();

    const link = await screen.findByRole("link", { name: /Covenant Stress Thesis/ });
    expect(link).toHaveAttribute("href", "/research-notes/note-99");
  });
});
