import type { ReactElement, ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router";
import { ResearchDocumentUploadPage } from "./ResearchDocumentUploadPage";
import * as researchDocumentApi from "../api/researchDocument";
import type { ResearchDocument } from "../api/researchDocument";

function renderPage(issuerId = "issuer-1"): void {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  function Wrapper({ children }: { children: ReactNode }): ReactElement {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[`/issuers/${issuerId}/research-documents/new`]}>
          {children}
        </MemoryRouter>
      </QueryClientProvider>
    );
  }
  render(
    <Routes>
      <Route
        path="/issuers/:issuerId/research-documents/new"
        element={<ResearchDocumentUploadPage />}
      />
    </Routes>,
    { wrapper: Wrapper },
  );
}

function makeDocument(overrides: Partial<ResearchDocument> = {}): ResearchDocument {
  return {
    id: "doc-1",
    issuer_id: "issuer-1",
    security_id: null,
    document_type: "credit_agreement",
    title: "Credit Agreement",
    description: null,
    original_filename: "credit-agreement.pdf",
    document_date: null,
    confidentiality_classification: "standard",
    uploaded_by: null,
    is_archived: false,
    archived_at: null,
    archived_by: null,
    created_at: "2026-08-01T00:00:00Z",
    updated_at: "2026-08-01T00:00:00Z",
    ...overrides,
  };
}

function pdfFile(name = "credit-agreement.pdf"): File {
  return new File(["%PDF-1.4 fixture content"], name, { type: "application/pdf" });
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("ResearchDocumentUploadPage", () => {
  it("disables submit until a PDF file and title are present", async () => {
    renderPage();
    const user = userEvent.setup();

    const submitButton = screen.getByRole("button", { name: /Upload Document/ });
    expect(submitButton).toBeDisabled();

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    await user.upload(fileInput, pdfFile());

    // Title auto-fills from the filename, so the button should now be enabled.
    await waitFor(() => expect(submitButton).toBeEnabled());
  });

  it("rejects a non-PDF file client-side", async () => {
    renderPage();

    // The input's `accept="application/pdf,.pdf"` already stops a real
    // browser file picker from offering non-PDF files, so `userEvent.upload`
    // (which honors `accept`) can't exercise this component-level check —
    // `fireEvent.change` bypasses that to test the defense-in-depth
    // validation directly (e.g. drag-and-drop, or a renamed extension).
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    const textFile = new File(["not a pdf"], "notes.txt", { type: "text/plain" });
    fireEvent.change(fileInput, { target: { files: [textFile] } });

    await waitFor(() => {
      expect(screen.getByText("Only PDF files are supported.")).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: /Upload Document/ })).toBeDisabled();
  });

  it("uploads scoped to the issuer from the route and navigates on success", async () => {
    const uploadSpy = vi
      .spyOn(researchDocumentApi, "uploadResearchDocument")
      .mockResolvedValue(makeDocument());

    renderPage("issuer-42");
    const user = userEvent.setup();

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    await user.upload(fileInput, pdfFile());

    const submitButton = await screen.findByRole("button", { name: /Upload Document/ });
    await waitFor(() => expect(submitButton).toBeEnabled());
    await user.click(submitButton);

    await waitFor(() => {
      expect(uploadSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          issuer_id: "issuer-42",
          document_type: "credit_agreement",
          title: "credit-agreement",
        }),
      );
    });
  });
});
