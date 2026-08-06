import type { ReactElement, ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { UniverseCard } from "./UniverseCard";
import type { ResearchUniverseSummary } from "../api/researchUniverse";

const mockNavigate = vi.fn();
vi.mock("react-router", async () => {
  const actual = await vi.importActual<typeof import("react-router")>("react-router");
  return { ...actual, useNavigate: () => mockNavigate };
});

function renderWithRouter(ui: ReactElement): void {
  function Wrapper({ children }: { children: ReactNode }) {
    return <MemoryRouter>{children}</MemoryRouter>;
  }
  render(ui, { wrapper: Wrapper });
}

const BASE_UNIVERSE: ResearchUniverseSummary = {
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
};

describe("UniverseCard", () => {
  it("renders the universe name, issuer count, priority, and verification status", () => {
    renderWithRouter(<UniverseCard universe={BASE_UNIVERSE} />);

    expect(screen.getByText("Distressed Core")).toBeInTheDocument();
    expect(screen.getByText("5 issuers")).toBeInTheDocument();
    expect(screen.getByText("critical")).toBeInTheDocument();
    expect(screen.getByText("verified")).toBeInTheDocument();
    expect(screen.getByText(/Last verified/)).toBeInTheDocument();
  });

  it("shows a Benchmark chip only for benchmark collections", () => {
    renderWithRouter(
      <UniverseCard universe={{ ...BASE_UNIVERSE, collection_type: "benchmark" }} />,
    );

    expect(screen.getByText("Benchmark")).toBeInTheDocument();
  });

  it("does not show a Benchmark chip for a research universe", () => {
    renderWithRouter(<UniverseCard universe={BASE_UNIVERSE} />);

    expect(screen.queryByText("Benchmark")).not.toBeInTheDocument();
  });

  it("shows 'Not yet verified' when last_verified_at is null", () => {
    renderWithRouter(<UniverseCard universe={{ ...BASE_UNIVERSE, last_verified_at: null }} />);

    expect(screen.getByText("Not yet verified")).toBeInTheDocument();
  });

  it("uses singular 'issuer' when the count is exactly one", () => {
    renderWithRouter(<UniverseCard universe={{ ...BASE_UNIVERSE, issuer_count: 1 }} />);

    expect(screen.getByText("1 issuer")).toBeInTheDocument();
  });

  it("navigates to Credit Universe filtered by this universe when clicked", async () => {
    renderWithRouter(<UniverseCard universe={BASE_UNIVERSE} />);

    await userEvent.click(screen.getByText("Distressed Core"));

    expect(mockNavigate).toHaveBeenCalledWith("/?universe=universe-1");
  });
});
