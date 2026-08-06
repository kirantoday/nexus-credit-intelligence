import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { CapitalStructureStack } from "./CapitalStructureStack";
import type { CapitalStructurePositionRow } from "../api/capitalStructure";

function makePosition(
  overrides: Partial<CapitalStructurePositionRow>,
): CapitalStructurePositionRow {
  return {
    position_id: "pos-1",
    security_id: null,
    layer_name: "First Lien Term Loan B",
    rank_order: 1,
    instrument_type: "first_lien_loan",
    seniority: "first_lien",
    lien_position: null,
    secured: true,
    guarantor_scope: null,
    amount_outstanding: "320000000",
    currency: "USD",
    maturity_date: "2029-03-01",
    price: null,
    enterprise_value_coverage: null,
    illustrative_recovery: null,
    recovery_scenario: null,
    is_synthetic: true,
    synthetic_reason: "SYNTHETIC_DEMO_DATA",
    provider: "synthetic",
    classification: "synthetic",
    transformation: "reported",
    as_of_date: "2026-08-06",
    retrieved_at: "2026-08-06T12:00:00Z",
    freshness: "live",
    ...overrides,
  };
}

describe("CapitalStructureStack", () => {
  it("shows an info message when no layers have been recorded", () => {
    render(<CapitalStructureStack positions={[]} isLoading={false} isError={false} />);

    expect(screen.getByText(/No capital structure layers have been recorded/)).toBeInTheDocument();
  });

  it("shows an error message when the capital structure fails to load", () => {
    render(<CapitalStructureStack positions={[]} isLoading={false} isError={true} />);

    expect(screen.getByText("Could not load the capital structure.")).toBeInTheDocument();
  });

  it("renders each layer with its amount and secured/unsecured status", () => {
    render(
      <CapitalStructureStack
        positions={[
          makePosition({ position_id: "pos-1", layer_name: "First Lien Term Loan B" }),
          makePosition({
            position_id: "pos-2",
            layer_name: "Senior Unsecured Notes due 2031",
            instrument_type: "unsecured",
            seniority: "senior_unsecured",
            secured: false,
            amount_outstanding: "225000000",
            rank_order: 2,
          }),
        ]}
        isLoading={false}
        isError={false}
      />,
    );

    expect(screen.getByText("First Lien Term Loan B")).toBeInTheDocument();
    expect(screen.getByText("$320.0M")).toBeInTheDocument();
    expect(screen.getByText("Senior Unsecured Notes due 2031")).toBeInTheDocument();
    // "Secured" appears twice: once as the column header, once as row 1's
    // status chip. "Unsecured" appears once, as row 2's status chip (its
    // instrument-type caption text "Unsecured · senior unsecured" is a
    // single combined text node, not an exact "Unsecured" match).
    expect(screen.getAllByText("Secured")).toHaveLength(2);
    expect(screen.getByText("Unsecured")).toBeInTheDocument();
  });

  it("renders the mandatory four-part label whenever a recovery figure is present", () => {
    render(
      <CapitalStructureStack
        positions={[
          makePosition({
            enterprise_value_coverage: "1.78",
            illustrative_recovery: "100.00",
            recovery_scenario: "Illustrative base-case Enterprise Value of $650,000,000.",
          }),
        ]}
        isLoading={false}
        isError={false}
      />,
    );

    expect(
      screen.getByText("Calculated · Scenario-based · Illustrative · Not a market fact"),
    ).toBeInTheDocument();
    expect(screen.getByText("1.78x")).toBeInTheDocument();
    expect(screen.getByText("100.00%")).toBeInTheDocument();
  });

  it("omits the recovery label entirely when no layer has a recovery figure", () => {
    render(
      <CapitalStructureStack positions={[makePosition({})]} isLoading={false} isError={false} />,
    );

    expect(
      screen.queryByText("Calculated · Scenario-based · Illustrative · Not a market fact"),
    ).not.toBeInTheDocument();
  });
});
