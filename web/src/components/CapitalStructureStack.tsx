import { type ReactElement, useMemo, useState } from "react";
import {
  Alert,
  Box,
  Chip,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Typography,
} from "@mui/material";
import type { CapitalStructurePositionRow } from "../api/capitalStructure";
import { ProvenanceBadge } from "./ProvenanceBadge";
import { SyntheticDataBadge } from "./SyntheticDataBadge";
import { formatCompactCurrency, formatDate, formatPercent } from "../lib/format";

const INSTRUMENT_TYPE_LABEL: Record<CapitalStructurePositionRow["instrument_type"], string> = {
  revolver: "Revolver",
  first_lien_loan: "1st Lien Loan",
  first_lien_notes: "1st Lien Notes",
  second_lien: "2nd Lien",
  unsecured: "Unsecured",
  subordinated: "Subordinated",
  preferred_equity: "Preferred Equity",
  common_equity: "Common Equity",
};

type SortMode = "priority" | "maturity";

/**
 * "What debt exists, which instrument sits where, what's secured vs.
 * unsecured, what matures first" — one answer, in one view (Milestone 6
 * brief). Rows always render in priority order (`rank_order`, most senior
 * first) unless the analyst asks to see them by maturity instead — either
 * way, `rank_order` still governs the waterfall math, this toggle only
 * changes *display* order.
 *
 * Every `enterprise_value_coverage`/`illustrative_recovery` figure renders
 * with all four of PLAN.md section 7's mandatory labels — "calculated",
 * "scenario-based", "illustrative", "not a market fact" — every time it's
 * shown, plus the specific `recovery_scenario` text on hover.
 */
export function CapitalStructureStack({
  positions,
  isLoading,
  isError,
}: {
  positions: CapitalStructurePositionRow[];
  isLoading: boolean;
  isError: boolean;
}): ReactElement {
  const [sortMode, setSortMode] = useState<SortMode>("priority");

  const rows = useMemo(() => {
    if (sortMode === "priority") return positions;
    return [...positions].sort((a, b) => {
      if (a.maturity_date === null) return 1;
      if (b.maturity_date === null) return -1;
      return a.maturity_date.localeCompare(b.maturity_date);
    });
  }, [positions, sortMode]);

  if (isLoading) {
    return (
      <Typography variant="body2" color="text.secondary">
        Loading capital structure…
      </Typography>
    );
  }

  if (isError) {
    return <Alert severity="error">Could not load the capital structure.</Alert>;
  }

  if (positions.length === 0) {
    return (
      <Alert severity="info">
        No capital structure layers have been recorded for this issuer yet. See the Securities
        section below for what's known about its individual instruments.
      </Alert>
    );
  }

  return (
    <Stack spacing={1.5}>
      <ToggleButtonGroup
        size="small"
        exclusive
        value={sortMode}
        onChange={(_e, value: SortMode | null) => value !== null && setSortMode(value)}
      >
        <ToggleButton value="priority">Priority order</ToggleButton>
        <ToggleButton value="maturity">Maturity order</ToggleButton>
      </ToggleButtonGroup>

      <TableContainer component={Paper} variant="outlined">
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Layer</TableCell>
              <TableCell>Secured</TableCell>
              <TableCell align="right">Amount Outstanding</TableCell>
              <TableCell>Maturity</TableCell>
              <TableCell align="right">EV Coverage</TableCell>
              <TableCell align="right">Illustrative Recovery</TableCell>
              <TableCell>Source</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {rows.map((position) => (
              <TableRow key={position.position_id} hover>
                <TableCell>
                  <Typography variant="body2" fontWeight={600}>
                    {position.layer_name}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {INSTRUMENT_TYPE_LABEL[position.instrument_type]}
                    {position.seniority ? ` · ${position.seniority.replace(/_/g, " ")}` : ""}
                  </Typography>
                </TableCell>
                <TableCell>
                  <Chip
                    label={position.secured ? "Secured" : "Unsecured"}
                    size="small"
                    color={position.secured ? "success" : "default"}
                    variant="outlined"
                  />
                </TableCell>
                <TableCell align="right">
                  {formatCompactCurrency(position.amount_outstanding)}
                </TableCell>
                <TableCell>{formatDate(position.maturity_date)}</TableCell>
                <TableCell align="right">
                  {position.enterprise_value_coverage === null ? (
                    "—"
                  ) : (
                    <Tooltip title={position.recovery_scenario ?? ""}>
                      <span>{Number(position.enterprise_value_coverage).toFixed(2)}x</span>
                    </Tooltip>
                  )}
                </TableCell>
                <TableCell align="right">
                  {position.illustrative_recovery === null ? (
                    "—"
                  ) : (
                    <Tooltip title={position.recovery_scenario ?? ""}>
                      <span>{formatPercent(position.illustrative_recovery)}</span>
                    </Tooltip>
                  )}
                </TableCell>
                <TableCell>
                  <Stack direction="row" spacing={1} alignItems="center">
                    <ProvenanceBadge
                      provider={position.provider}
                      asOfDate={position.as_of_date}
                      retrievedAt={position.retrieved_at}
                      freshness={position.freshness}
                    />
                    <SyntheticDataBadge
                      isSynthetic={position.is_synthetic}
                      reason={position.synthetic_reason}
                    />
                  </Stack>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      {rows.some(
        (p) => p.enterprise_value_coverage !== null || p.illustrative_recovery !== null,
      ) && (
        <Box>
          <Chip
            label="Calculated · Scenario-based · Illustrative · Not a market fact"
            size="small"
            color="warning"
            variant="outlined"
          />
          <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 0.5 }}>
            EV coverage and illustrative recovery figures above are a modeled scenario, not observed
            market prices or an actual recovery outcome. Hover a value for the exact assumption it
            depends on.
          </Typography>
        </Box>
      )}
    </Stack>
  );
}
