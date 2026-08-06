import type { ReactElement, ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router";
import { ResearchUniversesPage } from "./ResearchUniversesPage";
import * as researchUniverseApi from "../api/researchUniverse";
import type { ResearchUniverseListResponse } from "../api/researchUniverse";

function renderWithProviders(ui: ReactElement): void {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>{children}</MemoryRouter>
      </QueryClientProvider>
    );
  }
  render(ui, { wrapper: Wrapper });
}

const TWO_UNIVERSES_RESPONSE: ResearchUniverseListResponse = {
  universes: [
    {
      id: "universe-1",
      slug: "distressed-core",
      name: "Distressed Core",
      description: "Issuers currently in or near a distressed credit event.",
      collection_type: "research_universe",
      scope: "organization",
      visibility: "public",
      curation_method: "system_seeded",
      verification_status: "verified",
      last_verified_at: "2026-08-01T00:00:00Z",
      priority: "critical",
      issuer_count: 5,
    },
    {
      id: "universe-2",
      slug: "ig-benchmarks",
      name: "IG Benchmark Co",
      description: "A clean baseline for comparison.",
      collection_type: "benchmark",
      scope: "organization",
      visibility: "public",
      curation_method: "system_seeded",
      verification_status: "verified",
      last_verified_at: "2026-08-01T00:00:00Z",
      priority: null,
      issuer_count: 5,
    },
  ],
};

afterEach(() => {
  vi.restoreAllMocks();
});

describe("ResearchUniversesPage", () => {
  it("renders research universes and benchmarks in separate sections", async () => {
    vi.spyOn(researchUniverseApi, "fetchResearchUniverses").mockResolvedValue(
      TWO_UNIVERSES_RESPONSE,
    );

    renderWithProviders(<ResearchUniversesPage />);

    await waitFor(() => {
      expect(screen.getByText("Distressed Core")).toBeInTheDocument();
    });
    expect(screen.getByText("IG Benchmark Co")).toBeInTheDocument();
    expect(screen.getByText("Investment Grade Benchmarks")).toBeInTheDocument();
    expect(screen.getByText("Coverage Universes")).toBeInTheDocument();
  });

  it("shows an empty state when no universes have been seeded", async () => {
    vi.spyOn(researchUniverseApi, "fetchResearchUniverses").mockResolvedValue({ universes: [] });

    renderWithProviders(<ResearchUniversesPage />);

    await waitFor(() => {
      expect(screen.getByText("No Research Universes have been seeded yet.")).toBeInTheDocument();
    });
  });

  it("shows an error message when the API call fails", async () => {
    vi.spyOn(researchUniverseApi, "fetchResearchUniverses").mockRejectedValue(
      new Error("Network unreachable"),
    );

    renderWithProviders(<ResearchUniversesPage />);

    await waitFor(() => {
      expect(screen.getByText(/Could not load Research Universes/)).toBeInTheDocument();
    });
  });
});
