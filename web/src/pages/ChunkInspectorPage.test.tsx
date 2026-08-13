import type { ReactElement, ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router";
import { ChunkInspectorPage } from "./ChunkInspectorPage";
import * as documentExtractionApi from "../api/documentExtraction";
import type { DocumentChunk, DocumentExtraction } from "../api/documentExtraction";

function renderWithProviders(extractionId = "extraction-1"): void {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  function Wrapper({ children }: { children: ReactNode }): ReactElement {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[`/document-extractions/${extractionId}/chunks`]}>
          {children}
        </MemoryRouter>
      </QueryClientProvider>
    );
  }
  render(
    <Routes>
      <Route path="/document-extractions/:extractionId/chunks" element={<ChunkInspectorPage />} />
    </Routes>,
    { wrapper: Wrapper },
  );
}

function makeExtraction(overrides: Partial<DocumentExtraction> = {}): DocumentExtraction {
  return {
    id: "extraction-1",
    research_document_id: "doc-1",
    status: "completed",
    extractor_provider: "pymupdf4llm",
    extractor_version: "1.28.2",
    chunking_strategy_version: "structure_v1",
    page_count: 2,
    chunk_count: 2,
    table_count: 0,
    attempt_count: 1,
    error_classification: null,
    error_message: null,
    started_at: null,
    completed_at: "2026-08-14T10:00:00Z",
    created_at: "2026-08-14T10:00:00Z",
    is_current: true,
    ...overrides,
  };
}

function makeChunk(overrides: Partial<DocumentChunk> = {}): DocumentChunk {
  return {
    id: "chunk-1",
    document_extraction_id: "extraction-1",
    research_document_id: "doc-1",
    issuer_id: "issuer-1",
    chunk_index: 0,
    element_type: "text",
    content: "The Borrower shall not permit the First Lien Leverage Ratio to exceed 4.50 to 1.00.",
    content_type: "markdown",
    page_start: 86,
    page_end: 87,
    section_path: "ARTICLE VI > Financial Covenants",
    section_title: "Financial Covenants",
    token_count: 20,
    confidentiality_classification: "standard",
    created_at: "2026-08-14T10:00:00Z",
    ...overrides,
  };
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("ChunkInspectorPage", () => {
  it("shows extraction metrics and every chunk with page/section metadata", async () => {
    vi.spyOn(documentExtractionApi, "fetchExtraction").mockResolvedValue(makeExtraction());
    vi.spyOn(documentExtractionApi, "fetchChunks").mockResolvedValue({
      chunks: [makeChunk()],
    });

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText(/pymupdf4llm\/1.28.2/)).toBeInTheDocument();
    });
    expect(screen.getByText("2 pages")).toBeInTheDocument();
    expect(screen.getByText("Pages 86–87")).toBeInTheDocument();
    expect(screen.getByText("ARTICLE VI > Financial Covenants")).toBeInTheDocument();
    expect(screen.getByText(/First Lien Leverage Ratio/)).toBeInTheDocument();
  });

  it("renders a table chunk in a monospace block", async () => {
    vi.spyOn(documentExtractionApi, "fetchExtraction").mockResolvedValue(makeExtraction());
    vi.spyOn(documentExtractionApi, "fetchChunks").mockResolvedValue({
      chunks: [
        makeChunk({
          id: "chunk-2",
          element_type: "table",
          content: "|Tranche|Amount|\n|---|---|\n|Revolver|$50M|",
          page_start: 3,
          page_end: 3,
          section_path: null,
          section_title: null,
        }),
      ],
    });

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText("Table")).toBeInTheDocument();
    });
    const pre = document.querySelector("pre");
    expect(pre).not.toBeNull();
    expect(pre?.textContent).toContain("|Revolver|$50M|");
  });

  it("shows an empty state when the extraction has no chunks yet", async () => {
    vi.spyOn(documentExtractionApi, "fetchExtraction").mockResolvedValue(
      makeExtraction({ chunk_count: 0 }),
    );
    vi.spyOn(documentExtractionApi, "fetchChunks").mockResolvedValue({ chunks: [] });

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText("This extraction has no chunks yet.")).toBeInTheDocument();
    });
  });

  it("switches to search results when a query is typed", async () => {
    vi.spyOn(documentExtractionApi, "fetchExtraction").mockResolvedValue(makeExtraction());
    vi.spyOn(documentExtractionApi, "fetchChunks").mockResolvedValue({
      chunks: [makeChunk({ id: "chunk-1", content: "unrelated body text about revenue" })],
    });
    const searchSpy = vi.spyOn(documentExtractionApi, "searchChunks").mockResolvedValue({
      chunks: [makeChunk({ id: "chunk-2", content: "covenant language about leverage" })],
    });

    renderWithProviders();
    const user = userEvent.setup();

    await waitFor(() => {
      expect(screen.getByText(/unrelated body text/)).toBeInTheDocument();
    });

    const searchBox = screen.getByLabelText("Search chunks");
    await user.type(searchBox, "covenant");

    await waitFor(() => {
      expect(searchSpy).toHaveBeenCalledWith("extraction-1", "covenant");
    });
    await waitFor(() => {
      expect(screen.getByText(/covenant language/)).toBeInTheDocument();
    });
    expect(screen.queryByText(/unrelated body text/)).not.toBeInTheDocument();
  });

  it("shows a no-matches message when a search finds nothing", async () => {
    vi.spyOn(documentExtractionApi, "fetchExtraction").mockResolvedValue(makeExtraction());
    vi.spyOn(documentExtractionApi, "fetchChunks").mockResolvedValue({ chunks: [makeChunk()] });
    vi.spyOn(documentExtractionApi, "searchChunks").mockResolvedValue({ chunks: [] });

    renderWithProviders();
    const user = userEvent.setup();

    const searchBox = await screen.findByLabelText("Search chunks");
    await user.type(searchBox, "nonexistent");

    await waitFor(() => {
      expect(screen.getByText(/No chunks match "nonexistent"/)).toBeInTheDocument();
    });
  });
});
