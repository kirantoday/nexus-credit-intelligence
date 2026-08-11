import { type ReactElement, useMemo, useState } from "react";
import { Box, Button, Chip, Collapse, Link, Stack, Typography } from "@mui/material";
import type { IssuerTimeline, TimelineEvent, TimelineSource } from "../api/issuerTimeline";
import { SeverityBadge } from "./SeverityBadge";
import { formatDate } from "../lib/format";

const SOURCE_LABEL: Record<string, string> = {
  sec_edgar: "SEC EDGAR",
  courtlistener: "CourtListener",
};

function sourceLabel(provider: string): string {
  return SOURCE_LABEL[provider] ?? provider;
}

function SourceLink({ source }: { source: TimelineSource }): ReactElement {
  const label = sourceLabel(source.provider);
  return source.url ? (
    <Link href={source.url} target="_blank" rel="noopener noreferrer" underline="hover">
      <Typography variant="caption">{label}</Typography>
    </Link>
  ) : (
    <Typography variant="caption" color="text.secondary">
      {label}
    </Typography>
  );
}

function SourceBadge({ provider }: { provider: string }): ReactElement {
  return (
    <Chip
      label={sourceLabel(provider)}
      size="small"
      variant="outlined"
      sx={{ color: "text.secondary", borderColor: "divider" }}
    />
  );
}

function TimelineEventCard({
  event,
  isLast,
}: {
  event: TimelineEvent;
  isLast: boolean;
}): ReactElement {
  const [expanded, setExpanded] = useState(false);
  const distinctSourceProviders = Array.from(
    new Set([event.primary_source.provider, ...event.supporting_sources.map((s) => s.provider)]),
  );

  return (
    <Stack direction="row" spacing={{ xs: 1, sm: 2 }}>
      <Stack alignItems="center" sx={{ width: 14, flexShrink: 0 }}>
        <Box
          sx={{
            width: 14,
            height: 14,
            borderRadius: "50%",
            bgcolor: `${severityColor(event.severity)}.main`,
            boxShadow: (t) => `0 0 0 3px ${t.palette.background.paper}`,
            mt: 0.5,
          }}
        />
        {!isLast && <Box sx={{ width: 2, flexGrow: 1, bgcolor: "divider", mt: 0.5 }} />}
      </Stack>
      <Box sx={{ flex: 1, pb: 3.5, minWidth: 0 }}>
        <Typography variant="body2" fontWeight={700} color="text.primary">
          {formatDate(event.event_date)}
        </Typography>
        <Stack
          direction="row"
          spacing={1}
          alignItems="center"
          flexWrap="wrap"
          useFlexGap
          sx={{ mt: 0.25 }}
        >
          <SeverityBadge severity={event.severity} />
          <Typography variant="subtitle2" fontWeight={700}>
            {event.title.toUpperCase()}
          </Typography>
          {event.is_historical_discovery && (
            <Chip label="Historical" size="small" variant="outlined" />
          )}
        </Stack>
        <Typography variant="body2" sx={{ mt: 0.5 }}>
          {event.short_summary}
        </Typography>

        <Stack
          direction="row"
          spacing={1.5}
          alignItems="center"
          flexWrap="wrap"
          useFlexGap
          sx={{ mt: 1 }}
        >
          {distinctSourceProviders.map((provider) => (
            <SourceBadge key={provider} provider={provider} />
          ))}
          {event.confidence !== null && (
            <Typography variant="caption" color="text.secondary">
              Confidence {(event.confidence * 100).toFixed(0)}%
            </Typography>
          )}
          <Button size="small" onClick={() => setExpanded((e) => !e)}>
            {expanded ? "Hide detail" : "Why it matters"}
          </Button>
        </Stack>

        <Collapse in={expanded} unmountOnExit>
          <Box
            sx={{
              mt: 1,
              p: 1.5,
              pl: 2,
              borderLeft: 3,
              borderColor: `${severityColor(event.severity)}.main`,
              bgcolor: "background.default",
              borderRadius: 1,
            }}
          >
            <Typography variant="caption" fontWeight={600} color="text.secondary" display="block">
              Why it matters
            </Typography>
            <Typography variant="body2" sx={{ mt: 0.5 }}>
              {event.why_it_matters}
            </Typography>
            <Stack spacing={0.5} sx={{ mt: 1.5 }}>
              <Typography variant="caption" fontWeight={600} color="text.secondary">
                Sources ({event.evidence_count})
              </Typography>
              <SourceLink source={event.primary_source} />
              {event.supporting_sources.map((source, index) => (
                <SourceLink key={`${source.provider}-${index}`} source={source} />
              ))}
            </Stack>
          </Box>
        </Collapse>
      </Box>
    </Stack>
  );
}

function severityColor(severity: TimelineEvent["severity"]): "error" | "warning" | "info" {
  if (severity === "high") return "error";
  if (severity === "medium") return "warning";
  return "info";
}

type SeverityFilter = "all" | "high";

interface DistressTimelineProps {
  timeline: IssuerTimeline;
}

/**
 * Distress Timeline (PLAN.md Milestone 7.5.4) — a chronological narrative of
 * an issuer's material credit events, built entirely from already-persisted,
 * already-classified alerts. Deliberately light on controls: the default
 * view (all events, no filter) is already the useful one.
 */
export function DistressTimeline({ timeline }: DistressTimelineProps): ReactElement {
  const [severityFilter, setSeverityFilter] = useState<SeverityFilter>("all");

  const filteredEvents = useMemo(
    () =>
      severityFilter === "high"
        ? timeline.events.filter((e) => e.severity === "high")
        : timeline.events,
    [timeline.events, severityFilter],
  );

  if (timeline.events.length === 0) {
    return (
      <Typography variant="body2" color="text.secondary">
        Nexus has not identified enough material credit events to build a distress timeline for this
        issuer yet.
      </Typography>
    );
  }

  return (
    <Stack spacing={2}>
      <Box>
        <Typography variant="body2">
          {timeline.total_events} material event{timeline.total_events === 1 ? "" : "s"} ·{" "}
          {formatDate(timeline.date_range_start)} → {formatDate(timeline.date_range_end)}
        </Typography>
        {timeline.current_status.length > 0 && (
          <Typography variant="body2" sx={{ mt: 0.5 }}>
            <Typography component="span" fontWeight={600}>
              Current status:
            </Typography>{" "}
            {timeline.current_status.join(" / ")}
          </Typography>
        )}
        {timeline.most_recent_event_title && (
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            <Typography component="span" fontWeight={600}>
              Most recent material event:
            </Typography>{" "}
            {timeline.most_recent_event_title}
          </Typography>
        )}
      </Box>

      <Stack direction="row" spacing={1}>
        <Chip
          label="All"
          size="small"
          clickable
          onClick={() => setSeverityFilter("all")}
          color={severityFilter === "all" ? "primary" : "default"}
          variant={severityFilter === "all" ? "filled" : "outlined"}
        />
        <Chip
          label="High severity"
          size="small"
          clickable
          onClick={() => setSeverityFilter("high")}
          color={severityFilter === "high" ? "primary" : "default"}
          variant={severityFilter === "high" ? "filled" : "outlined"}
        />
      </Stack>

      {filteredEvents.length === 0 ? (
        <Typography variant="body2" color="text.secondary">
          No events match this filter.
        </Typography>
      ) : (
        <Box>
          {filteredEvents.map((event, index) => (
            <TimelineEventCard
              key={`${event.event_date}-${event.event_type}`}
              event={event}
              isLast={index === filteredEvents.length - 1}
            />
          ))}
        </Box>
      )}
    </Stack>
  );
}
