import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { SyntheticDataBadge } from "./SyntheticDataBadge";

describe("SyntheticDataBadge", () => {
  it("renders nothing for real (non-synthetic) data", () => {
    const { container } = render(<SyntheticDataBadge isSynthetic={false} reason={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders a Synthetic chip for synthetic data", () => {
    render(<SyntheticDataBadge isSynthetic={true} reason="SYNTHETIC_DEMO_DATA" />);
    expect(screen.getByText("Synthetic")).toBeInTheDocument();
  });
});
