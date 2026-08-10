import type { ReactElement, ReactNode } from "react";
import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { AboutPage } from "./AboutPage";

function renderWithRouter(ui: ReactElement): void {
  function Wrapper({ children }: { children: ReactNode }) {
    return <MemoryRouter initialEntries={["/about"]}>{children}</MemoryRouter>;
  }
  render(ui, { wrapper: Wrapper });
}

describe("AboutPage", () => {
  it("renders the page headline and honestly positions Nexus as a prototype", () => {
    renderWithRouter(<AboutPage />);

    expect(screen.getByRole("heading", { name: "Nexus Credit Intelligence" })).toBeInTheDocument();
    expect(
      screen.getByText("From fragmented credit data to an evidence-backed distress narrative."),
    ).toBeInTheDocument();
    expect(screen.getByText("Working prototype")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Nexus is an evolving research platform for distressed-credit and leveraged-finance professionals — not a finished, fully automated product.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText(/production-ready/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/^complete$/i)).not.toBeInTheDocument();
  });

  it("renders the workflow flow and current capability cards", () => {
    renderWithRouter(<AboutPage />);

    expect(screen.getByText("Market Context")).toBeInTheDocument();
    expect(screen.getByText("Source Evidence")).toBeInTheDocument();

    expect(screen.getByRole("heading", { name: "Credit Universe" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Research Universes" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Morning Research Brief" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Issuer Distress Timeline" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Source-Level Evidence" })).toBeInTheDocument();
  });

  it("renders the data sources actually used by the running application", () => {
    renderWithRouter(<AboutPage />);

    expect(screen.getByText("SEC EDGAR")).toBeInTheDocument();
    expect(screen.getByText("CourtListener / RECAP")).toBeInTheDocument();
    expect(screen.getByText("OpenFIGI")).toBeInTheDocument();
    expect(screen.getByText("FRED")).toBeInTheDocument();
    expect(screen.getByText("Anthropic")).toBeInTheDocument();
  });

  it("renders the AI usage section with the actual Haiku/Sonnet routing policy, without overclaiming", () => {
    renderWithRouter(<AboutPage />);

    expect(screen.getByRole("heading", { name: "How Nexus Uses AI" })).toBeInTheDocument();
    expect(screen.getByText(/Claude Haiku/)).toBeInTheDocument();
    expect(screen.getByText(/Claude Sonnet/)).toBeInTheDocument();
    expect(
      screen.getByText(/never through Haiku, because accuracy matters more than cost/),
    ).toBeInTheDocument();
    expect(screen.getByText(/does not make investment decisions/)).toBeInTheDocument();
  });

  it("renders the AI governance and cost-control section", () => {
    renderWithRouter(<AboutPage />);

    expect(
      screen.getByRole("heading", { name: "AI Governance & Cost Control" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "AI is treated as a governed research tool, not an unlimited background expense.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText(/Hard per-run limits/)).toBeInTheDocument();
    expect(screen.getByText(/zero-AI mode/)).toBeInTheDocument();
  });

  it("distinguishes Available Today from Planned Next and Future Direction", () => {
    renderWithRouter(<AboutPage />);

    const available = screen.getByRole("list", { name: "Available Today items" });
    const planned = screen.getByRole("list", { name: "Planned Next items" });
    const future = screen.getByRole("list", { name: "Future Direction items" });

    expect(within(available).getByText("Credit Universe")).toBeInTheDocument();
    expect(within(planned).getByText("Watchlists")).toBeInTheDocument();
    expect(within(future).getByText("An AI Research Assistant")).toBeInTheDocument();

    // No not-yet-built ("Soon") feature is accidentally presented as available today.
    expect(within(available).queryByText("Watchlists")).not.toBeInTheDocument();
    expect(within(available).queryByText(/Alerts/)).not.toBeInTheDocument();
    expect(within(available).queryByText("Universal search")).not.toBeInTheDocument();
    expect(within(available).queryByText(/Research Assistant/)).not.toBeInTheDocument();
  });

  it("links to live product sections", () => {
    renderWithRouter(<AboutPage />);

    expect(screen.getByRole("link", { name: "Open Credit Universe →" })).toHaveAttribute(
      "href",
      "/",
    );
    expect(screen.getByRole("link", { name: "Open Research Universes →" })).toHaveAttribute(
      "href",
      "/research-universes",
    );
    expect(screen.getByRole("link", { name: "Open Morning Research Brief →" })).toHaveAttribute(
      "href",
      "/research-brief",
    );
    expect(screen.getByRole("link", { name: "Find Trinseo in Credit Universe →" })).toHaveAttribute(
      "href",
      "/?q=Trinseo",
    );
    expect(
      screen.getByRole("link", { name: "Find Diebold Nixdorf in Credit Universe →" }),
    ).toHaveAttribute("href", "/?q=Diebold");
  });
});
