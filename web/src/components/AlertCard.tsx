import { type ReactElement, useState } from "react";
import { Link as RouterLink } from "react-router";
import {
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Collapse,
  Link,
  Stack,
  Typography,
} from "@mui/material";
import BookmarkOutlinedIcon from "@mui/icons-material/BookmarkOutlined";
import type { AlertRow } from "../api/filingMonitor";
import { useAlertEvidence } from "../queries/useAlerts";
import { SeverityBadge } from "./SeverityBadge";
import { formatDate, formatDateTime } from "../lib/format";
import { SUGGESTED_ACCENT_COLOR } from "../theme";

interface AlertCardProps {
  alert: AlertRow;
  onAcknowledge?: (alertId: string) => void;
  onDismiss?: (alertId: string, reason?: string) => void;
}

/**
 * One evidence-backed alert. Renders whichever source-specific fields are
 * present on `primary_source_label`/`primary_source_url` rather than
 * hardcoding filing fields into the layout, so a future non-SEC alert
 * renders correctly without a component change (PLAN.md 24.9).
 */
export function AlertCard({ alert, onAcknowledge, onDismiss }: AlertCardProps): ReactElement {
  const [expanded, setExpanded] = useState(false);
  const evidenceQuery = useAlertEvidence(expanded ? alert.id : undefined);

  return (
    <Card
      variant="outlined"
      sx={{ borderLeft: 4, borderLeftColor: `${severityColor(alert.severity)}.main` }}
    >
      <CardContent>
        <Stack direction="row" justifyContent="space-between" alignItems="flex-start" spacing={2}>
          <Box>
            <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
              <SeverityBadge severity={alert.severity} />
              <Chip
                label={alert.ai_assisted ? "AI-assisted" : "Deterministic"}
                size="small"
                variant="outlined"
                sx={
                  alert.ai_assisted
                    ? { color: SUGGESTED_ACCENT_COLOR, borderColor: SUGGESTED_ACCENT_COLOR }
                    : undefined
                }
              />
              {alert.is_backfill && <Chip label="Historical" size="small" color="default" />}
              <Chip label={alert.status} size="small" variant="outlined" />
              <Chip label={alert.category.replace(/_/g, " ")} size="small" variant="outlined" />
            </Stack>
            <Typography variant="subtitle1" fontWeight={600} sx={{ mt: 1 }}>
              {alert.headline}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
              {alert.explanation}
            </Typography>
          </Box>
        </Stack>

        <Stack
          direction="row"
          spacing={1}
          alignItems="center"
          flexWrap="wrap"
          useFlexGap
          sx={{ mt: 1.5 }}
        >
          <Link component={RouterLink} to={`/issuers/${alert.issuer_id}`} underline="hover">
            <Typography variant="body2" fontWeight={600}>
              {alert.issuer_legal_name}
              {alert.issuer_ticker ? ` (${alert.issuer_ticker})` : ""}
            </Typography>
          </Link>
          {alert.universe_names.map((name) => (
            <Chip key={name} label={name} size="small" variant="outlined" />
          ))}
          {alert.watchlist_names.map((name) => (
            <Chip
              key={name}
              icon={<BookmarkOutlinedIcon />}
              label={name}
              size="small"
              variant="filled"
              color="primary"
            />
          ))}
        </Stack>

        <Stack
          direction="row"
          spacing={2}
          alignItems="center"
          flexWrap="wrap"
          useFlexGap
          sx={{ mt: 1 }}
        >
          <Typography variant="caption" color="text.secondary">
            {alert.primary_source_url ? (
              <Link href={alert.primary_source_url} target="_blank" rel="noopener noreferrer">
                {alert.primary_source_label}
              </Link>
            ) : (
              alert.primary_source_label
            )}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            As of {formatDate(alert.as_of_date)}
          </Typography>
          {alert.confidence !== null && (
            <Typography variant="caption" color="text.secondary">
              Confidence {(alert.confidence * 100).toFixed(0)}%
            </Typography>
          )}
          <Typography variant="caption" color="text.secondary">
            Triggered {formatDateTime(alert.triggered_at)}
          </Typography>
        </Stack>

        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ mt: 1.5 }}>
          <Button size="small" onClick={() => setExpanded((e) => !e)}>
            {expanded ? "Hide evidence" : "Why was this flagged?"}
          </Button>
          {alert.status === "new" && onAcknowledge && (
            <Button size="small" onClick={() => onAcknowledge(alert.id)}>
              Acknowledge
            </Button>
          )}
          {alert.status !== "dismissed" && onDismiss && (
            <Button size="small" color="inherit" onClick={() => onDismiss(alert.id)}>
              Dismiss
            </Button>
          )}
        </Stack>

        <Collapse in={expanded} unmountOnExit>
          <Box sx={{ mt: 1.5, pl: 1, borderLeft: 2, borderColor: "divider" }}>
            {evidenceQuery.isLoading && (
              <Typography variant="caption" color="text.secondary">
                Loading evidence…
              </Typography>
            )}
            {evidenceQuery.isError && (
              <Typography variant="caption" color="error">
                Could not load evidence.
              </Typography>
            )}
            {evidenceQuery.data?.evidence.map((item) => (
              <Box key={item.id} sx={{ mb: 1.5 }}>
                <Stack direction="row" spacing={1} alignItems="center">
                  <Chip label={item.evidence_type} size="small" variant="outlined" />
                  {item.source_item && (
                    <Typography variant="caption" color="text.secondary">
                      {item.source_item}
                    </Typography>
                  )}
                  <Typography variant="caption" color="text.secondary">
                    rule: {item.matched_rule}
                  </Typography>
                </Stack>
                <Typography variant="body2" sx={{ mt: 0.5, fontStyle: "italic" }}>
                  “{item.evidence_excerpt}”
                </Typography>
              </Box>
            ))}
          </Box>
        </Collapse>
      </CardContent>
    </Card>
  );
}

function severityColor(severity: AlertRow["severity"]): "error" | "warning" | "info" {
  if (severity === "high") return "error";
  if (severity === "medium") return "warning";
  return "info";
}
