import type { ReactElement, ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router";
import { ResearchDocumentsSection } from "./ResearchDocumentsSection";
import * as researchDocumentApi from "../api/researchDocument";
import type {
  ResearchDocumentListResponse,
  ResearchDocumentSummary,
} from "../api/researchDocument";

function renderWithProviders(issuerId = "issuer-1"): void {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  function Wrapper({ children }: { children: ReactNode }): ReactElement {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>{children}</MemoryRouter>
      </QueryClientProvider>
    );
  }
  render(<ResearchDocumentsSection issuerId={issuerId} />, { wrapper: Wrapper });
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

describe("ResearchDocumentsSection", () => {
  it("shows an empty state when the issuer has no research documents", async () => {
    vi.spyOn(researchDocumentApi, "fetchResearchDocuments").mockResolvedValue({
      documents: [],
    } satisfies ResearchDocumentListResponse);

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText(/No research documents yet for this issuer/)).toBeInTheDocument();
    });
  });

  it("renders a document's title, type badge, and filename", async () => {
    vi.spyOn(researchDocumentApi, "fetchResearchDocuments").mockResolvedValue({
      documents: [makeDocument()],
    });

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText("Amended Credit Agreement")).toBeInTheDocument();
    });
    expect(screen.getByText("Credit Agreement")).toBeInTheDocument();
    expect(screen.getByText(/credit-agreement\.pdf/)).toBeInTheDocument();
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

  it("does not show a Restricted chip for standard documents", async () => {
    vi.spyOn(researchDocumentApi, "fetchResearchDocuments").mockResolvedValue({
      documents: [makeDocument()],
    });

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText("Amended Credit Agreement")).toBeInTheDocument();
    });
    expect(screen.queryByText("Restricted")).not.toBeInTheDocument();
  });

  it("links Upload Document to the issuer-scoped upload route", async () => {
    vi.spyOn(researchDocumentApi, "fetchResearchDocuments").mockResolvedValue({ documents: [] });

    renderWithProviders("issuer-42");

    const link = await screen.findByRole("link", { name: /Upload Document/ });
    expect(link).toHaveAttribute("href", "/issuers/issuer-42/research-documents/new");
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
    expect(researchDocumentApi.fetchResearchDocumentDownloadUrl).toHaveBeenCalledWith(
      "doc-1",
      false,
    );
  });

  it("requests a forced-download URL when Download is clicked", async () => {
    vi.spyOn(researchDocumentApi, "fetchResearchDocuments").mockResolvedValue({
      documents: [makeDocument()],
    });
    vi.spyOn(researchDocumentApi, "fetchResearchDocumentDownloadUrl").mockResolvedValue({
      signed_url: "https://storage.test/signed/credit-agreement.pdf?download=1",
      expires_in_seconds: 300,
      original_filename: "credit-agreement.pdf",
    });
    vi.spyOn(window, "open").mockImplementation(() => null);

    renderWithProviders();
    const user = userEvent.setup();

    const downloadButton = await screen.findByLabelText("Download document");
    await user.click(downloadButton);

    await waitFor(() => {
      expect(researchDocumentApi.fetchResearchDocumentDownloadUrl).toHaveBeenCalledWith(
        "doc-1",
        true,
      );
    });
  });

  it("marks a document as archived and hides the Archive action after clicking Archive", async () => {
    vi.spyOn(researchDocumentApi, "fetchResearchDocuments").mockResolvedValue({
      documents: [makeDocument()],
    });
    vi.spyOn(researchDocumentApi, "archiveResearchDocument").mockResolvedValue(
      makeDocument({ is_archived: true }),
    );

    renderWithProviders();
    const user = userEvent.setup();

    const archiveButton = await screen.findByLabelText("Archive document");
    await user.click(archiveButton);

    await waitFor(() => {
      expect(screen.getByText("Archived")).toBeInTheDocument();
    });
    expect(screen.queryByLabelText("Archive document")).not.toBeInTheDocument();
  });
});
