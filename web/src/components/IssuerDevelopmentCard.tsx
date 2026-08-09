import type { ReactElement } from "react";
import { Link as RouterLink } from "react-router";
import { Box, Chip, Link, Stack, Typography } from "@mui/material";
import type { IssuerDevelopment } from "../api/filingMonitor";
import { AlertCard } from "./AlertCard";
import { SeverityBadge } from "./SeverityBadge";

interface IssuerDevelopmentCardProps {
  development: IssuerDevelopment;
  onAcknowledge?: (alertId: string) => void;
  onDismiss?: (alertId: string, reason?: string) => void;
}

/**
 * One issuer's material developments this period (PLAN.md Milestone 7.5.2
 * correction) — the brief's fundamental display unit, not an individual
 * alert. Research Universe membership *changes* (not routine membership)
 * are called out explicitly here, distinct from `AlertCard`'s own
 * universe-membership chips.
 */
export function IssuerDevelopmentCard({
  development,
  onAcknowledge,
  onDismiss,
}: IssuerDevelopmentCardProps): ReactElement {
  return (
    <Box>
      <Stack
        direction="row"
        spacing={1}
        alignItems="center"
        flexWrap="wrap"
        useFlexGap
        sx={{ mb: 1 }}
      >
        <SeverityBadge severity={development.max_severity} />
        <Link component={RouterLink} to={`/issuers/${development.issuer_id}`} underline="hover">
          <Typography variant="subtitle1" fontWeight={700}>
            {development.issuer_legal_name}
            {development.issuer_ticker ? ` (${development.issuer_ticker})` : ""}
          </Typography>
        </Link>
        {development.universe_changes.map((change) => (
          <Chip
            key={`${change.universe_name}-${change.change_type}`}
            label={
              change.change_type === "added"
                ? `+ Added to ${change.universe_name}`
                : `↑ ${change.universe_name} (${change.verification_status})`
            }
            size="small"
            color="primary"
            variant="outlined"
          />
        ))}
      </Stack>
      <Stack spacing={1.5}>
        {development.alerts.map((alert) => (
          <AlertCard
            key={alert.id}
            alert={alert}
            onAcknowledge={onAcknowledge}
            onDismiss={onDismiss}
          />
        ))}
      </Stack>
    </Box>
  );
}
