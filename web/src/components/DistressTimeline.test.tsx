import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DistressTimeline } from "./DistressTimeline";
import type { IssuerTimeline, TimelineEvent } from "../api/issuerTimeline";

function makeEvent(overrides: Partial<TimelineEvent> = {}): TimelineEvent {
  return {
    event_date: "2026-06-01",
    event_type: "chapter_11",
    title: "Chapter 11",
    short_summary: "8-K discloses Chapter 11 filing plans.",
    why_it_matters: "Deterministic rule matching flagged this signal.",
    severity: "high",
    confidence: 0.95,
    primary_source: {
      provider: "sec_edgar",
      label: "8-K filed 2026-06-01",
      url: "https://sec.gov/x",
    },
    supporting_sources: [],
    is_historical_discovery: false,
    evidence_count: 1,
    ...overrides,
  };
}

function makeTimeline(overrides: Partial<IssuerTimeline> = {}): IssuerTimeline {
  return {
    issuer_id: "iss-1",
    events: [makeEvent()],
    total_events: 1,
    date_range_start: "2026-06-01",
    date_range_end: "2026-06-01",
    current_status: [],
    most_recent_event_title: "Chapter 11",
    ...overrides,
  };
}

describe("DistressTimeline", () => {
  it("shows the honest empty message when there are no qualifying events", () => {
    render(
      <DistressTimeline
        timeline={makeTimeline({
          events: [],
          total_events: 0,
          date_range_start: null,
          date_range_end: null,
          most_recent_event_title: null,
        })}
      />,
    );

    expect(
      screen.getByText(
        "Nexus has not identified enough material credit events to build a distress timeline for this issuer yet.",
      ),
    ).toBeInTheDocument();
  });

  it("renders events in the order given, with date, title, and summary", () => {
    const timeline = makeTimeline({
      events: [
        makeEvent({
          event_date: "2026-06-01",
          title: "Chapter 11",
          short_summary: "Chapter 11 filed.",
        }),
        makeEvent({
          event_date: "2026-02-17",
          title: "Covenant Breach",
          short_summary: "Early covenant breach.",
        }),
      ],
      total_events: 2,
    });

    render(<DistressTimeline timeline={timeline} />);

    const headings = screen.getAllByText(/CHAPTER 11|COVENANT BREACH/);
    expect(headings[0]).toHaveTextContent("CHAPTER 11");
    expect(headings[1]).toHaveTextContent("COVENANT BREACH");
    expect(screen.getByText("Chapter 11 filed.")).toBeInTheDocument();
    expect(screen.getByText("Early covenant breach.")).toBeInTheDocument();
  });

  it("renders the summary header with event count, date range, status, and most recent event", () => {
    const timeline = makeTimeline({
      total_events: 16,
      date_range_start: "2023-06-01",
      date_range_end: "2026-07-29",
      current_status: ["Chapter 11 / Bankruptcy", "Distressed Core"],
      most_recent_event_title: "Material Impairment",
    });

    render(<DistressTimeline timeline={timeline} />);

    expect(screen.getByText(/16 material events/)).toBeInTheDocument();
    expect(screen.getByText(/Chapter 11 \/ Bankruptcy \/ Distressed Core/)).toBeInTheDocument();
    expect(screen.getByText("Material Impairment")).toBeInTheDocument();
  });

  it("does not render a status line when current_status is empty", () => {
    render(<DistressTimeline timeline={makeTimeline({ current_status: [] })} />);

    expect(screen.queryByText(/Current status:/)).not.toBeInTheDocument();
  });

  it("renders a collapsed event's source badges and evidence count in the expanded detail", async () => {
    const user = userEvent.setup();
    const timeline = makeTimeline({
      events: [
        makeEvent({
          evidence_count: 2,
          primary_source: { provider: "sec_edgar", label: "8-K filed 2026-06-01", url: null },
          supporting_sources: [
            {
              provider: "courtlistener",
              label: "Docket entry #1",
              url: "https://courtlistener.com/x",
            },
          ],
        }),
      ],
    });

    render(<DistressTimeline timeline={timeline} />);

    expect(screen.getByText("SEC EDGAR")).toBeInTheDocument();
    expect(screen.getByText("CourtListener")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Why it matters" }));

    expect(
      screen.getByText("Deterministic rule matching flagged this signal."),
    ).toBeInTheDocument();
    expect(screen.getByText("Sources (2)")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "CourtListener" })).toHaveAttribute(
      "href",
      "https://courtlistener.com/x",
    );
  });

  it("filters to only high-severity events when the High severity chip is clicked", async () => {
    const user = userEvent.setup();
    const timeline = makeTimeline({
      events: [
        makeEvent({ title: "Chapter 11", severity: "high" }),
        makeEvent({ event_date: "2026-01-01", title: "Case Dismissed", severity: "low" }),
      ],
      total_events: 2,
    });

    render(<DistressTimeline timeline={timeline} />);

    expect(screen.getByText("CHAPTER 11")).toBeInTheDocument();
    expect(screen.getByText("CASE DISMISSED")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "High severity" }));

    expect(screen.getByText("CHAPTER 11")).toBeInTheDocument();
    expect(screen.queryByText("CASE DISMISSED")).not.toBeInTheDocument();
  });

  it("shows a Historical chip for backfilled events", () => {
    render(
      <DistressTimeline
        timeline={makeTimeline({ events: [makeEvent({ is_historical_discovery: true })] })}
      />,
    );

    expect(screen.getByText("Historical")).toBeInTheDocument();
  });
});
