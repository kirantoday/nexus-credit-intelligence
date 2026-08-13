import type { ReactElement, ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router";
import { ResearchDocumentDetailPage } from "./ResearchDocumentDetailPage";
import * as researchDocumentApi from "../api/researchDocument";
import * as documentExtractionApi from "../api/documentExtraction";
import { ApiError } from "../api/client";
import type { ResearchDocument } from "../api/researchDocument";

function renderWithProviders(documentId = "doc-1"): void {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  function Wrapper({ children }: { children: ReactNode }): ReactElement {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[`/research-documents/${documentId}`]}>
          {children}
        </MemoryRouter>
      </QueryClientProvider>
    );
  }
  render(
    <Routes>
      <Route path="/research-documents/:documentId" element={<ResearchDocumentDetailPage />} />
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
    title: "Amended Credit Agreement",
    description: "The amended and restated credit agreement.",
    original_filename: "credit-agreement.pdf",
    document_date: "2026-06-01",
    confidentiality_classification: "standard",
    uploaded_by: "demo-analyst",
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

describe("ResearchDocumentDetailPage", () => {
  it("renders the document's title, description, and a link to its issuer", async () => {
    vi.spyOn(researchDocumentApi, "fetchResearchDocument").mockResolvedValue(makeDocument());
    vi.spyOn(documentExtractionApi, "fetchCurrentExtraction").mockRejectedValue(
      new ApiError("not found", 404),
    );
    vi.spyOn(documentExtractionApi, "fetchExtractions").mockResolvedValue({ extractions: [] });

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText("Amended Credit Agreement")).toBeInTheDocument();
    });
    expect(screen.getByText("The amended and restated credit agreement.")).toBeInTheDocument();
    const issuerLink = screen.getByRole("link", { name: "View issuer" });
    expect(issuerLink).toHaveAttribute("href", "/issuers/issuer-1");
  });

  it("embeds the Document Intelligence panel", async () => {
    vi.spyOn(researchDocumentApi, "fetchResearchDocument").mockResolvedValue(makeDocument());
    vi.spyOn(documentExtractionApi, "fetchCurrentExtraction").mockRejectedValue(
      new ApiError("not found", 404),
    );
    vi.spyOn(documentExtractionApi, "fetchExtractions").mockResolvedValue({ extractions: [] });

    renderWithProviders();

    expect(await screen.findByText("Document Intelligence")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("Status: Not processed")).toBeInTheDocument();
    });
  });

  it("shows an error state when the document fails to load", async () => {
    vi.spyOn(researchDocumentApi, "fetchResearchDocument").mockRejectedValue(
      new ApiError("not found", 404),
    );

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText("Could not load this research document.")).toBeInTheDocument();
    });
  });

  it("shows a Restricted chip for restricted documents", async () => {
    vi.spyOn(researchDocumentApi, "fetchResearchDocument").mockResolvedValue(
      makeDocument({ confidentiality_classification: "restricted" }),
    );
    vi.spyOn(documentExtractionApi, "fetchCurrentExtraction").mockRejectedValue(
      new ApiError("not found", 404),
    );
    vi.spyOn(documentExtractionApi, "fetchExtractions").mockResolvedValue({ extractions: [] });

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText("Restricted")).toBeInTheDocument();
    });
  });
});
