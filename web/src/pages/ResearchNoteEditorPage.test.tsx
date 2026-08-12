import type { ReactElement, ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router";
import { ResearchNoteEditorPage } from "./ResearchNoteEditorPage";
import * as researchNoteApi from "../api/researchNote";
import type { ResearchNote } from "../api/researchNote";

function renderCreateMode(issuerId = "issuer-1"): void {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  function Wrapper({ children }: { children: ReactNode }): ReactElement {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[`/issuers/${issuerId}/research-notes/new`]}>
          {children}
        </MemoryRouter>
      </QueryClientProvider>
    );
  }
  render(
    <Routes>
      <Route path="/issuers/:issuerId/research-notes/new" element={<ResearchNoteEditorPage />} />
    </Routes>,
    { wrapper: Wrapper },
  );
}

function renderEditMode(noteId = "note-1"): void {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  function Wrapper({ children }: { children: ReactNode }): ReactElement {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[`/research-notes/${noteId}/edit`]}>{children}</MemoryRouter>
      </QueryClientProvider>
    );
  }
  render(
    <Routes>
      <Route path="/research-notes/:noteId/edit" element={<ResearchNoteEditorPage />} />
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
    thesis_status: "active",
    conviction: "medium",
    bull_case: "Refinancing completes.",
    base_case: "Waiver secured.",
    bear_case: "Chapter 11 within two quarters.",
    catalysts: "Q3 compliance certificate.",
    risks: "EBITDA deterioration.",
    invalidation_conditions: "Going concern qualification.",
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
    ...overrides,
  };
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("ResearchNoteEditorPage — create mode", () => {
  it("creates a note scoped to the issuer from the route", async () => {
    const createSpy = vi.spyOn(researchNoteApi, "createResearchNote").mockResolvedValue(makeNote());
    const user = userEvent.setup();

    renderCreateMode("issuer-77");

    await user.type(screen.getByRole("textbox", { name: "Title" }), "New Thesis");
    await user.click(screen.getByRole("button", { name: "Create Research Note" }));

    await waitFor(() => {
      expect(createSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          issuer_id: "issuer-77",
          title: "New Thesis",
          thesis_status: "draft",
          is_demo: false,
        }),
      );
    });
  });

  it("disables submit until a title is entered", () => {
    renderCreateMode();
    expect(screen.getByRole("button", { name: "Create Research Note" })).toBeDisabled();
  });
});

describe("ResearchNoteEditorPage — edit mode", () => {
  it("hydrates the form from the existing note", async () => {
    vi.spyOn(researchNoteApi, "fetchResearchNote").mockResolvedValue(makeNote());

    renderEditMode();

    await waitFor(() => {
      expect(screen.getByDisplayValue("Covenant Stress Thesis")).toBeInTheDocument();
    });
    expect(screen.getByDisplayValue("Refinancing completes.")).toBeInTheDocument();
  });

  it("submits an update with the edited field", async () => {
    vi.spyOn(researchNoteApi, "fetchResearchNote").mockResolvedValue(makeNote());
    const updateSpy = vi
      .spyOn(researchNoteApi, "updateResearchNote")
      .mockResolvedValue(makeNote({ title: "Updated Thesis" }));
    const user = userEvent.setup();

    renderEditMode();
    await waitFor(() => {
      expect(screen.getByDisplayValue("Covenant Stress Thesis")).toBeInTheDocument();
    });

    const titleField = screen.getByRole("textbox", { name: "Title" });
    await user.clear(titleField);
    await user.type(titleField, "Updated Thesis");
    await user.click(screen.getByRole("button", { name: "Save Changes" }));

    await waitFor(() => {
      expect(updateSpy).toHaveBeenCalledWith(
        "note-1",
        expect.objectContaining({ title: "Updated Thesis" }),
      );
    });
  });

  it("shows a read-only message for an archived note instead of a form", async () => {
    vi.spyOn(researchNoteApi, "fetchResearchNote").mockResolvedValue(
      makeNote({ is_archived: true }),
    );

    renderEditMode();

    await waitFor(() => {
      expect(screen.getByText(/Archived notes are read-only/)).toBeInTheDocument();
    });
    expect(screen.queryByLabelText("Title")).not.toBeInTheDocument();
  });
});
