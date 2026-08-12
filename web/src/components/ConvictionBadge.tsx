import type { ReactElement } from "react";
import { Chip } from "@mui/material";
import type { Conviction } from "../api/researchNote";

const CONVICTION_COLOR: Record<Conviction, "default" | "info" | "success"> = {
  low: "default",
  medium: "info",
  high: "success",
};

const CONVICTION_LABEL: Record<Conviction, string> = {
  low: "Low Conviction",
  medium: "Medium Conviction",
  high: "High Conviction",
};

export function ConvictionBadge({ conviction }: { conviction: Conviction }): ReactElement {
  return (
    <Chip
      label={CONVICTION_LABEL[conviction]}
      size="small"
      color={CONVICTION_COLOR[conviction]}
      variant="outlined"
    />
  );
}
