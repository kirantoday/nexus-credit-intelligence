import type { ReactElement } from "react";
import { Chip } from "@mui/material";
import type { EvidenceSeverity } from "../api/filingMonitor";

const SEVERITY_COLOR: Record<EvidenceSeverity, "error" | "warning" | "info"> = {
  high: "error",
  medium: "warning",
  low: "info",
};

const SEVERITY_LABEL: Record<EvidenceSeverity, string> = {
  high: "High",
  medium: "Medium",
  low: "Low",
};

export function SeverityBadge({ severity }: { severity: EvidenceSeverity }): ReactElement {
  return (
    <Chip
      label={SEVERITY_LABEL[severity]}
      size="small"
      color={SEVERITY_COLOR[severity]}
      variant="filled"
    />
  );
}
