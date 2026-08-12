import type { ReactElement, ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router";
import { ResearchNotePage } from "./ResearchNotePage";
import * as researchNoteApi from "../api/researchNote";
import type {
  AuditEvent,
  ResearchNote,
  ResearchNoteVersion,
  ResearchNoteVersionListResponse,
} from "../api/researchNote";

function renderWithProviders(noteId = "note-1"): void {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  function Wrapper({ children }: { children: ReactNode }): ReactElement {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[`/research-notes/${noteId}`]}>{children}</MemoryRouter>
      </QueryClientProvider>
    );
  }
  render(
    <Routes>
      <Route path="/research-notes/:noteId" element={<ResearchNotePage />} />
    </Routes>,
    { wrapper: Wrapper },
  );
}

function makeNote(overrides: Partial<ResearchNote> = {}): ResearchNote {
  return {
    id: "note-1",
    issuer_id: "issuer-1",
    security_id: null,
    title: "Covenant Stress Thesis",
    thesis_status: "invalidated",
    conviction: "high",
    bull_case: "Refinancing completes on favorable terms.",
    base_case: "Covenant waiver secured.",
    bear_case: "Chapter 11 petition filed; the bear case has materialized.",
    catalysts: "Q3 covenant compliance certificate.",
    risks: "Further EBITDA deterioration.",
    invalidation_conditions: "Going concern qualification issued.",
    evidence_refs: null,
    access_classification: "standard",
    author_user_id: "demo-analyst",
    is_demo: true,
    current_version_number: 2,
    is_archived: false,
    archived_at: null,
    archived_by: null,
    created_at: "2026-08-01T00:00:00Z",
    updated_at: "2026-08-10T00:00:00Z",
    ...overrides,
  };
}

function makeVersion(overrides: Partial<ResearchNoteVersion> = {}): ResearchNoteVersion {
  return {
    id: "version-1",
    research_note_id: "note-1",
    version_number: 1,
    title: "Covenant Stress Thesis",
    thesis_status: "active",
    conviction: "medium",
    bull_case: "Refinancing completes on favorable terms.",
    base_case: "Covenant waiver secured.",
    bear_case: "Chapter 11 filing within two quarters.",
    catalysts: "Q3 covenant compliance certificate.",
    risks: "Further EBITDA deterioration.",
    invalidation_conditions: "Going concern qualification issued.",
    evidence_refs: null,
    access_classification: "standard",
    edited_by: "demo-analyst",
    edited_at: "2026-08-01T00:00:00Z",
    ...overrides,
  };
}

function makeAuditEvent(overrides: Partial<AuditEvent> = {}): AuditEvent {
  return {
    id: "audit-1",
    user_id: "demo-analyst",
    event_type: "research_note_created",
    entity_table: "research_note",
    entity_id: "note-1",
    before_state: null,
    after_state: { title: "Covenant Stress Thesis" },
    occurred_at: "2026-08-01T00:00:00Z",
    ...overrides,
  };
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("ResearchNotePage", () => {
  it("renders the note's structured sections", async () => {
    vi.spyOn(researchNoteApi, "fetchResearchNote").mockResolvedValue(makeNote());
    vi.spyOn(researchNoteApi, "fetchResearchNoteVersions").mockResolvedValue({ versions: [] });
    vi.spyOn(researchNoteApi, "fetchResearchNoteAuditEvents").mockResolvedValue({ events: [] });

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText("Covenant Stress Thesis")).toBeInTheDocument();
    });
    expect(screen.getByText("Refinancing completes on favorable terms.")).toBeInTheDocument();
    expect(
      screen.getByText("Chapter 11 petition filed; the bear case has materialized."),
    ).toBeInTheDocument();
    expect(screen.getByText("Invalidated")).toBeInTheDocument();
    expect(screen.getByText("Demo Research Note")).toBeInTheDocument();
  });

  it("shows a not-found message for an unknown note", async () => {
    const { ApiError } = await import("../api/client");
    vi.spyOn(researchNoteApi, "fetchResearchNote").mockRejectedValue(
      new ApiError("Request failed with status 404", 404),
    );
    vi.spyOn(researchNoteApi, "fetchResearchNoteVersions").mockResolvedValue({ versions: [] });
    vi.spyOn(researchNoteApi, "fetchResearchNoteAuditEvents").mockResolvedValue({ events: [] });

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText("This research note doesn't exist.")).toBeInTheDocument();
    });
  });

  it("renders version history entries with the current version marked", async () => {
    vi.spyOn(researchNoteApi, "fetchResearchNote").mockResolvedValue(makeNote());
    vi.spyOn(researchNoteApi, "fetchResearchNoteVersions").mockResolvedValue({
      versions: [
        makeVersion({ version_number: 2, thesis_status: "invalidated", conviction: "high" }),
        makeVersion({ version_number: 1 }),
      ],
    } satisfies ResearchNoteVersionListResponse);
    vi.spyOn(researchNoteApi, "fetchResearchNoteAuditEvents").mockResolvedValue({ events: [] });

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText("Version 2")).toBeInTheDocument();
    });
    expect(screen.getByText("Version 1")).toBeInTheDocument();
    expect(screen.getByText("Current")).toBeInTheDocument();
  });

  it("switches to a historical version's read-only content when clicked", async () => {
    vi.spyOn(researchNoteApi, "fetchResearchNote").mockResolvedValue(makeNote());
    vi.spyOn(researchNoteApi, "fetchResearchNoteVersions").mockResolvedValue({
      versions: [
        makeVersion({ version_number: 2, thesis_status: "invalidated", conviction: "high" }),
        makeVersion({ version_number: 1 }),
      ],
    });
    vi.spyOn(researchNoteApi, "fetchResearchNoteAuditEvents").mockResolvedValue({ events: [] });
    vi.spyOn(researchNoteApi, "fetchResearchNoteVersion").mockResolvedValue(
      makeVersion({ version_number: 1 }),
    );
    const user = userEvent.setup();

    renderWithProviders();
    await waitFor(() => {
      expect(screen.getByText("Version 1")).toBeInTheDocument();
    });

    await user.click(screen.getByText("Version 1"));

    await waitFor(() => {
      expect(screen.getByText(/Viewing historical Version 1/)).toBeInTheDocument();
    });
    expect(screen.getByText("Chapter 11 filing within two quarters.")).toBeInTheDocument();
  });

  it("renders the audit trail", async () => {
    vi.spyOn(researchNoteApi, "fetchResearchNote").mockResolvedValue(makeNote());
    vi.spyOn(researchNoteApi, "fetchResearchNoteVersions").mockResolvedValue({ versions: [] });
    vi.spyOn(researchNoteApi, "fetchResearchNoteAuditEvents").mockResolvedValue({
      events: [makeAuditEvent()],
    });

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText("Note created")).toBeInTheDocument();
    });
  });

  it("archives the note when Archive is clicked", async () => {
    vi.spyOn(researchNoteApi, "fetchResearchNote").mockResolvedValue(makeNote());
    vi.spyOn(researchNoteApi, "fetchResearchNoteVersions").mockResolvedValue({ versions: [] });
    vi.spyOn(researchNoteApi, "fetchResearchNoteAuditEvents").mockResolvedValue({ events: [] });
    const archiveSpy = vi
      .spyOn(researchNoteApi, "archiveResearchNote")
      .mockResolvedValue(makeNote({ is_archived: true }));
    const user = userEvent.setup();

    renderWithProviders();
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Archive" })).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: "Archive" }));

    await waitFor(() => {
      expect(archiveSpy).toHaveBeenCalledWith("note-1", undefined);
    });
  });

  it("hides Edit/Archive actions for an already-archived note", async () => {
    vi.spyOn(researchNoteApi, "fetchResearchNote").mockResolvedValue(
      makeNote({ is_archived: true }),
    );
    vi.spyOn(researchNoteApi, "fetchResearchNoteVersions").mockResolvedValue({ versions: [] });
    vi.spyOn(researchNoteApi, "fetchResearchNoteAuditEvents").mockResolvedValue({ events: [] });

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText("Archived")).toBeInTheDocument();
    });
    expect(screen.queryByRole("button", { name: "Edit" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Archive" })).not.toBeInTheDocument();
  });
});
