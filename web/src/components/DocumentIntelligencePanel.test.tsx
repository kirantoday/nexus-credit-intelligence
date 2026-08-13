import type { ReactElement, ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router";
import { DocumentIntelligencePanel } from "./DocumentIntelligencePanel";
import * as documentExtractionApi from "../api/documentExtraction";
import { ApiError } from "../api/client";
import type { DocumentExtraction } from "../api/documentExtraction";

function renderWithProviders(documentId = "doc-1"): void {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  function Wrapper({ children }: { children: ReactNode }): ReactElement {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>{children}</MemoryRouter>
      </QueryClientProvider>
    );
  }
  render(<DocumentIntelligencePanel documentId={documentId} />, { wrapper: Wrapper });
}

function makeExtraction(overrides: Partial<DocumentExtraction> = {}): DocumentExtraction {
  return {
    id: "extraction-1",
    research_document_id: "doc-1",
    status: "completed",
    extractor_provider: "pymupdf4llm",
    extractor_version: "1.28.2",
    chunking_strategy_version: "structure_v1",
    page_count: 187,
    chunk_count: 412,
    table_count: 23,
    attempt_count: 1,
    error_classification: null,
    error_message: null,
    started_at: "2026-08-14T10:00:00Z",
    completed_at: "2026-08-14T10:00:30Z",
    created_at: "2026-08-14T10:00:00Z",
    is_current: true,
    ...overrides,
  };
}

const NOT_FOUND = new ApiError("not found", 404);

afterEach(() => {
  vi.restoreAllMocks();
});

describe("DocumentIntelligencePanel", () => {
  it("shows 'Not processed' and a Process Document button when no extraction exists", async () => {
    vi.spyOn(documentExtractionApi, "fetchCurrentExtraction").mockRejectedValue(NOT_FOUND);
    vi.spyOn(documentExtractionApi, "fetchExtractions").mockResolvedValue({ extractions: [] });

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText("Status: Not processed")).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: /Process Document/ })).toBeInTheDocument();
  });

  it("shows a Pending chip while an extraction is queued", async () => {
    const pending = makeExtraction({ status: "pending", started_at: null, is_current: false });
    vi.spyOn(documentExtractionApi, "fetchCurrentExtraction").mockRejectedValue(NOT_FOUND);
    vi.spyOn(documentExtractionApi, "fetchExtractions").mockResolvedValue({
      extractions: [pending],
    });

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText("Pending")).toBeInTheDocument();
    });
    expect(screen.getByText(/checks for new work every few minutes/)).toBeInTheDocument();
  });

  it("shows Processed status with metrics and an Inspect Chunks link for a completed extraction", async () => {
    const completed = makeExtraction();
    vi.spyOn(documentExtractionApi, "fetchCurrentExtraction").mockResolvedValue(completed);
    vi.spyOn(documentExtractionApi, "fetchExtractions").mockResolvedValue({
      extractions: [completed],
    });

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText("Processed")).toBeInTheDocument();
    });
    expect(screen.getByText("187")).toBeInTheDocument();
    expect(screen.getByText("412")).toBeInTheDocument();
    expect(screen.getByText("23")).toBeInTheDocument();
    const inspectLink = screen.getByRole("link", { name: /Inspect Chunks/ });
    expect(inspectLink).toHaveAttribute("href", "/document-extractions/extraction-1/chunks");
    expect(screen.getByRole("button", { name: /Reprocess/ })).toBeInTheDocument();
  });

  it("shows a needs_ocr explanation, not a generic failure", async () => {
    const needsOcr = makeExtraction({
      status: "needs_ocr",
      is_current: false,
      chunk_count: 0,
    });
    vi.spyOn(documentExtractionApi, "fetchCurrentExtraction").mockRejectedValue(NOT_FOUND);
    vi.spyOn(documentExtractionApi, "fetchExtractions").mockResolvedValue({
      extractions: [needsOcr],
    });

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText("Needs OCR")).toBeInTheDocument();
    });
    expect(screen.getByText(/appears to require OCR/)).toBeInTheDocument();
    expect(screen.queryByText(/Extraction failed/)).not.toBeInTheDocument();
  });

  it("shows a failed extraction's error classification without a stack trace", async () => {
    const failed = makeExtraction({
      status: "failed",
      is_current: false,
      error_classification: "deterministic",
      error_message: "ExtractionFailure: PyMuPDF4LLM failed to parse source: bad xref table",
    });
    vi.spyOn(documentExtractionApi, "fetchCurrentExtraction").mockRejectedValue(NOT_FOUND);
    vi.spyOn(documentExtractionApi, "fetchExtractions").mockResolvedValue({
      extractions: [failed],
    });

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText(/Extraction failed \(deterministic\)/)).toBeInTheDocument();
    });
    expect(screen.queryByText(/Traceback/)).not.toBeInTheDocument();
  });

  it("keeps a prior current extraction's metrics visible when the latest attempt failed", async () => {
    const current = makeExtraction({ id: "extraction-1", is_current: true });
    const failedReprocess = makeExtraction({
      id: "extraction-2",
      status: "failed",
      is_current: false,
      error_classification: "deterministic",
    });
    vi.spyOn(documentExtractionApi, "fetchCurrentExtraction").mockResolvedValue(current);
    vi.spyOn(documentExtractionApi, "fetchExtractions").mockResolvedValue({
      extractions: [failedReprocess, current],
    });

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText(/Extraction failed/)).toBeInTheDocument();
    });
    // The prior current extraction's metrics still render underneath.
    expect(screen.getByText("187")).toBeInTheDocument();
    expect(screen.getByText(/· current/)).toBeInTheDocument();
  });

  it("calls processDocument when Process Document is clicked", async () => {
    vi.spyOn(documentExtractionApi, "fetchCurrentExtraction").mockRejectedValue(NOT_FOUND);
    vi.spyOn(documentExtractionApi, "fetchExtractions").mockResolvedValue({ extractions: [] });
    const processSpy = vi
      .spyOn(documentExtractionApi, "processDocument")
      .mockResolvedValue(makeExtraction({ status: "pending", is_current: false }));

    renderWithProviders("doc-1");
    const user = userEvent.setup();

    const button = await screen.findByRole("button", { name: /Process Document/ });
    await user.click(button);

    await waitFor(() => {
      expect(processSpy).toHaveBeenCalledWith("doc-1", undefined);
    });
  });
});
