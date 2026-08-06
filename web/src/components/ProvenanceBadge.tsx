import type { ReactElement } from "react";
import { Chip, Tooltip } from "@mui/material";
import type { FreshnessTier, ProviderName } from "../api/creditUniverse";
import { formatDate, formatDateTime } from "../lib/format";

const FRESHNESS_COLOR: Record<FreshnessTier, "success" | "info" | "default"> = {
  live: "success",
  cached: "info",
  stale: "default",
};

const PROVIDER_LABEL: Record<ProviderName, string> = {
  sec_edgar: "SEC EDGAR",
  finra_trace: "FINRA TRACE",
  openfigi: "OpenFIGI",
  fred: "FRED",
  courtlistener: "CourtListener",
  pacer: "PACER",
  admin_upload: "Admin Upload",
  sp_global_loan_pricing: "S&P Global Loan Pricing",
  sp_global_loan_reference: "S&P Global Loan Reference",
  octus: "Octus",
  bloomberg: "Bloomberg",
  lseg_lpc: "LSEG LPC",
  synthetic: "Synthetic",
  ai_generated: "AI Generated",
};

interface ProvenanceBadgeProps {
  provider: ProviderName;
  asOfDate: string;
  retrievedAt: string;
  freshness: FreshnessTier;
}

/**
 * Every displayed value must have provenance (CLAUDE.md) — this is the
 * inline, always-visible surface for it: hovering shows source, as-of date,
 * and retrieval time; the chip color itself signals freshness at a glance,
 * without needing to open a separate lineage view.
 */
export function ProvenanceBadge({
  provider,
  asOfDate,
  retrievedAt,
  freshness,
}: ProvenanceBadgeProps): ReactElement {
  return (
    <Tooltip
      title={`Source: ${PROVIDER_LABEL[provider]} · As of ${formatDate(asOfDate)} · Retrieved ${formatDateTime(retrievedAt)}`}
    >
      <Chip label={freshness} size="small" color={FRESHNESS_COLOR[freshness]} variant="outlined" />
    </Tooltip>
  );
}
