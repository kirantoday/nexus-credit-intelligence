import type { ReactElement } from "react";
import { Chip, Tooltip } from "@mui/material";

interface SyntheticDataBadgeProps {
  isSynthetic: boolean;
  reason: string | null;
}

/**
 * Marks a row/value as synthetic demo data (PLAN.md section 4.5's
 * `synthetic_flag` pattern) — renders nothing for real data, so it's safe to
 * drop into any row unconditionally.
 */
export function SyntheticDataBadge({
  isSynthetic,
  reason,
}: SyntheticDataBadgeProps): ReactElement | null {
  if (!isSynthetic) return null;
  return (
    <Tooltip title={reason ? `Synthetic demo data: ${reason}` : "Synthetic demo data"}>
      <Chip label="Synthetic" size="small" color="warning" variant="outlined" />
    </Tooltip>
  );
}
