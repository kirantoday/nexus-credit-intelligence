import type { ReactElement, ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router";
import { ResearchDocumentsWorkspacePage } from "./ResearchDocumentsWorkspacePage";
import * as researchDocumentApi from "../api/researchDocument";
import type {
  ResearchDocumentListResponse,
  ResearchDocumentSummary,
} from "../api/researchDocument";

function renderWithProviders(): void {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  function Wrapper({ children }: { children: ReactNode }): ReactElement {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/research-documents"]}>{children}</MemoryRouter>
      </QueryClientProvider>
    );
  }
  render(
    <Routes>
      <Route path="/research-documents" element={<ResearchDocumentsWorkspacePage />} />
    </Routes>,
    { wrapper: Wrapper },
  );
}

function makeDocument(overrides: Partial<ResearchDocumentSummary> = {}): ResearchDocumentSummary {
  return {
    id: "doc-1",
    issuer_id: "issuer-1",
    security_id: null,
    document_type: "credit_agreement",
    title: "Amended Credit Agreement",
    description: null,
    original_filename: "credit-agreement.pdf",
    document_date: "2026-06-01",
    confidentiality_classification: "standard",
    uploaded_by: "demo-analyst",
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

describe("ResearchDocumentsWorkspacePage", () => {
  it("shows a loading state", () => {
    vi.spyOn(researchDocumentApi, "fetchResearchDocuments").mockReturnValue(new Promise(() => {}));
    renderWithProviders();
    expect(screen.getByRole("progressbar")).toBeInTheDocument();
  });

  it("shows an error state", async () => {
    vi.spyOn(researchDocumentApi, "fetchResearchDocuments").mockRejectedValue(
      new Error("network error"),
    );
    renderWithProviders();
    await waitFor(() => {
      expect(screen.getByText("Could not load research documents.")).toBeInTheDocument();
    });
  });

  it("shows an empty state when there are no research documents", async () => {
    vi.spyOn(researchDocumentApi, "fetchResearchDocuments").mockResolvedValue({
      documents: [],
    } satisfies ResearchDocumentListResponse);
    renderWithProviders();
    await waitFor(() => {
      expect(screen.getByText(/No research documents yet/)).toBeInTheDocument();
    });
  });

  it("shows documents across issuers with issuer name, ticker, type, and dates", async () => {
    vi.spyOn(researchDocumentApi, "fetchResearchDocuments").mockResolvedValue({
      documents: [
        makeDocument(),
        makeDocument({
          id: "doc-2",
          issuer_id: "issuer-2",
          title: "No-Ticker Issuer Memo",
          issuer_legal_name: "Private Debt Co",
          issuer_ticker: null,
          document_type: "internal_research_memo",
        }),
      ],
    });

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText("Amended Credit Agreement")).toBeInTheDocument();
    });
    expect(screen.getByText("Trinseo PLC")).toBeInTheDocument();
    expect(screen.getByText("TSEOQ")).toBeInTheDocument();
    expect(screen.getByText("Credit Agreement")).toBeInTheDocument();

    expect(screen.getByText("No-Ticker Issuer Memo")).toBeInTheDocument();
    expect(screen.getByText("Private Debt Co")).toBeInTheDocument();
    expect(screen.getByText("Internal Research Memo")).toBeInTheDocument();
  });

  it("shows a Restricted chip for restricted documents", async () => {
    vi.spyOn(researchDocumentApi, "fetchResearchDocuments").mockResolvedValue({
      documents: [makeDocument({ confidentiality_classification: "restricted" })],
    });

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText("Restricted")).toBeInTheDocument();
    });
  });

  it("links the issuer name to Issuer Detail", async () => {
    vi.spyOn(researchDocumentApi, "fetchResearchDocuments").mockResolvedValue({
      documents: [makeDocument({ issuer_id: "issuer-42" })],
    });

    renderWithProviders();

    const link = await screen.findByRole("link", { name: "Trinseo PLC" });
    expect(link).toHaveAttribute("href", "/issuers/issuer-42");
  });

  it("links a document's title to its detail page", async () => {
    vi.spyOn(researchDocumentApi, "fetchResearchDocuments").mockResolvedValue({
      documents: [makeDocument()],
    });

    renderWithProviders();

    const titleLink = await screen.findByRole("link", { name: "Amended Credit Agreement" });
    expect(titleLink).toHaveAttribute("href", "/research-documents/doc-1");
  });

  it("fetches without an issuer_id filter (cross-issuer)", async () => {
    const fetchSpy = vi
      .spyOn(researchDocumentApi, "fetchResearchDocuments")
      .mockResolvedValue({ documents: [] });

    renderWithProviders();

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith(undefined, undefined, false);
    });
  });

  it("opens a signed URL in a new tab when View is clicked", async () => {
    vi.spyOn(researchDocumentApi, "fetchResearchDocuments").mockResolvedValue({
      documents: [makeDocument()],
    });
    vi.spyOn(researchDocumentApi, "fetchResearchDocumentDownloadUrl").mockResolvedValue({
      signed_url: "https://storage.test/signed/credit-agreement.pdf",
      expires_in_seconds: 300,
      original_filename: "credit-agreement.pdf",
    });
    const openSpy = vi.spyOn(window, "open").mockImplementation(() => null);

    renderWithProviders();
    const user = userEvent.setup();

    const viewButton = await screen.findByLabelText("View document");
    await user.click(viewButton);

    await waitFor(() => {
      expect(openSpy).toHaveBeenCalledWith(
        "https://storage.test/signed/credit-agreement.pdf",
        "_blank",
        "noopener,noreferrer",
      );
    });
  });
});
