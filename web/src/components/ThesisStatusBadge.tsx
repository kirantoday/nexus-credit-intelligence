import type { ReactElement } from "react";
import { Chip } from "@mui/material";
import type { ThesisStatus } from "../api/researchNote";

const STATUS_COLOR: Record<ThesisStatus, "default" | "primary" | "warning" | "error" | "success"> =
  {
    draft: "default",
    active: "primary",
    monitoring: "warning",
    invalidated: "error",
    resolved: "success",
  };

const STATUS_LABEL: Record<ThesisStatus, string> = {
  draft: "Draft",
  active: "Active",
  monitoring: "Monitoring",
  invalidated: "Invalidated",
  resolved: "Resolved",
};

export function ThesisStatusBadge({ status }: { status: ThesisStatus }): ReactElement {
  return (
    <Chip label={STATUS_LABEL[status]} size="small" color={STATUS_COLOR[status]} variant="filled" />
  );
}
