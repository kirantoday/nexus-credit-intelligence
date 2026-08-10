import type { ReactElement, ReactNode } from "react";
import { Link as RouterLink } from "react-router";
import {
  Box,
  Card,
  CardContent,
  Chip,
  Divider,
  Link,
  Paper,
  Stack,
  Typography,
} from "@mui/material";

function SectionHeading({ children }: { children: string }): ReactElement {
  return (
    <Typography variant="h5" gutterBottom>
      {children}
    </Typography>
  );
}

const WORKFLOW_STEPS = [
  "Market Context",
  "Credit Universe",
  "Research Universes",
  "Morning Research Brief",
  "Issuer Detail",
  "Distress Timeline",
  "Source Evidence",
];

function WorkflowFlow(): ReactElement {
  return (
    <Stack
      direction={{ xs: "column", sm: "row" }}
      spacing={1}
      alignItems={{ xs: "flex-start", sm: "center" }}
      flexWrap="wrap"
      useFlexGap
      sx={{ my: 2 }}
    >
      {WORKFLOW_STEPS.map((step, index) => (
        <Stack key={step} direction="row" alignItems="center" spacing={1}>
          <Chip label={step} size="small" variant="outlined" />
          {index < WORKFLOW_STEPS.length - 1 && (
            <Typography color="text.secondary" aria-hidden="true">
              →
            </Typography>
          )}
        </Stack>
      ))}
    </Stack>
  );
}

interface CapabilityCardProps {
  title: string;
  points: string[];
  linkTo?: string;
  linkLabel?: string;
}

function CapabilityCard({ title, points, linkTo, linkLabel }: CapabilityCardProps): ReactElement {
  return (
    <Card variant="outlined" sx={{ height: "100%" }}>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          {title}
        </Typography>
        <Stack component="ul" spacing={0.5} sx={{ pl: 2.5, m: 0 }}>
          {points.map((point) => (
            <Typography key={point} component="li" variant="body2" color="text.secondary">
              {point}
            </Typography>
          ))}
        </Stack>
        {linkTo && linkLabel && (
          <Box sx={{ mt: 1.5 }}>
            <Link component={RouterLink} to={linkTo} underline="hover" variant="body2">
              {linkLabel} →
            </Link>
          </Box>
        )}
      </CardContent>
    </Card>
  );
}

const CAPABILITIES: CapabilityCardProps[] = [
  {
    title: "Credit Universe",
    points: [
      "Real bonds and loans Nexus currently tracks",
      "Issuer- and instrument-level reference data",
      "Every value carries source provenance",
      "SOFR / HY OAS market context alongside the table",
    ],
    linkTo: "/",
    linkLabel: "Open Credit Universe",
  },
  {
    title: "Research Universes",
    points: [
      "Organizes issuers into research coverage categories",
      "Examples: Chapter 11 / Bankruptcy, Distressed Core, Going Concern, Refinancing Risk, Default / Covenant Stress",
      "Current/verified coverage is shown separately from system-suggested coverage",
    ],
    linkTo: "/research-universes",
    linkLabel: "Open Research Universes",
  },
  {
    title: "Morning Research Brief",
    points: [
      "What materially changed in the latest completed research cycle",
      "Compares the latest business day against the prior one",
      "Prioritized by issuer and severity",
      "Separates newly discovered historical intelligence from genuinely new developments",
    ],
    linkTo: "/research-brief",
    linkLabel: "Open Morning Research Brief",
  },
  {
    title: "Issuer Distress Timeline",
    points: [
      "Chronological view of an issuer's material credit events",
      "Reconstructs the path from early warning → deterioration → restructuring/default → bankruptcy/court → post-emergence",
      "Every event links back to its underlying source",
    ],
  },
  {
    title: "Source-Level Evidence",
    points: [
      "SEC filings",
      "Court records (dockets and docket entries)",
      "Security reference data",
      "Provenance and, where available, model confidence",
    ],
  },
];

interface DataSource {
  name: string;
  role: string;
}

const DATA_SOURCES: DataSource[] = [
  { name: "SEC EDGAR", role: "Company filings and filing-derived credit evidence." },
  { name: "CourtListener / RECAP", role: "Bankruptcy cases, dockets, and court events." },
  { name: "OpenFIGI", role: "Security identification and reference enrichment." },
  {
    name: "FRED",
    role: "Market context such as SOFR and the ICE BofA U.S. High Yield OAS.",
  },
  {
    name: "Anthropic",
    role: "AI-assisted review of selected evidence bundles where semantic judgment is required.",
  },
];

const AI_TASKS = [
  "Determine whether a distress event actually relates to the issuer or to a third party",
  "Interpret ambiguous filing or docket language",
  "Classify evidence into credit-relevant categories",
  "Generate concise, analyst-facing summaries",
  "Assess severity and confidence when deterministic rules alone are insufficient",
];

const AI_ROUTING_STEPS = [
  "Deterministic rules and source matching run first — most evidence is filtered before any model is involved.",
  "Evidence bundles already reviewed are skipped before any AI call — nothing is re-billed on a re-run.",
  "Evidence that clears the deterministic floor but needs judgment goes to Claude Haiku, a faster and lower-cost model, first.",
  "High-impact categories — Chapter 11, bankruptcy or receivership, and plan confirmation — go directly to Claude Sonnet under the current routing policy, never through Haiku, because accuracy matters more than cost for these.",
  "If Haiku's confidence is too low, or its output can't be parsed, the bundle escalates to Sonnet for a second look.",
  "AI output never replaces provenance — the underlying filing or court evidence stays available and linked.",
];

const GOVERNANCE_POINTS = [
  "Deterministic-first processing: only evidence with genuine signal reaches a model at all.",
  "Idempotent, bundle-level review: an already-reviewed piece of evidence is never re-sent to a model on a later run.",
  "Centralized model routing (deterministic → Haiku → Sonnet when needed) — one policy, not scattered per-caller logic.",
  "High-impact cases receive more conservative treatment, not cheaper treatment.",
  "Hard per-run limits — maximum AI calls, maximum estimated cost, maximum premium-model calls — enforced before every call, not after.",
  "A zero-AI mode exists for pure discovery and measurement runs, at no AI cost.",
  "Every real AI call is logged: model, routing reason, token usage, estimated cost, latency, and success or failure.",
  "When a run reaches its budget, remaining evidence is deferred for a future run with fresh budget — never silently downgraded into a fabricated result.",
];

const AVAILABLE_TODAY = [
  "Credit Universe",
  "Research Universes",
  "Morning Research Brief",
  "Issuer Detail",
  "Distress Timeline",
  "SEC / court / security provenance",
  "Market Context (SOFR, HY OAS)",
  "AI-assisted evidence review with model routing and cost controls",
];

const PLANNED_NEXT = [
  "Watchlists",
  "Alerts and user-specific monitoring",
  "Universal search",
  "Research notes and audit events",
  "Richer capital structure data as licensed instrument-level sources become available",
];

const FUTURE_DIRECTION = [
  "A dedicated Research Workspace",
  "An AI Research Assistant",
  "Portfolio and scenario analysis",
  "Recovery and restructuring analytics",
  "Additional institutional data sources",
];

function RoadmapColumn({
  label,
  items,
  color,
}: {
  label: string;
  items: string[];
  color: "success" | "warning" | "default";
}): ReactElement {
  const borderColor = color === "default" ? "divider" : `${color}.main`;
  return (
    <Box
      sx={{
        flex: 1,
        minWidth: 220,
        pt: 1.5,
        borderTop: 3,
        borderTopColor: borderColor,
      }}
    >
      <Chip label={label} size="small" color={color} sx={{ mb: 1 }} />
      <Stack component="ul" aria-label={`${label} items`} spacing={0.5} sx={{ pl: 2.5, m: 0 }}>
        {items.map((item) => (
          <Typography key={item} component="li" variant="body2" color="text.secondary">
            {item}
          </Typography>
        ))}
      </Stack>
    </Box>
  );
}

function Section({ children }: { children: ReactNode }): ReactElement {
  return (
    <Box>
      {children}
      <Divider sx={{ mt: 3 }} />
    </Box>
  );
}

export function AboutPage(): ReactElement {
  return (
    <Stack spacing={3} sx={{ maxWidth: 960 }}>
      <Box>
        <Stack direction="row" spacing={1.5} alignItems="center" flexWrap="wrap" useFlexGap>
          <Typography variant="h4">Nexus Credit Intelligence</Typography>
          <Chip label="Working prototype" size="small" variant="outlined" />
        </Stack>
        <Typography variant="subtitle1" color="text.secondary" sx={{ mt: 0.5 }}>
          From fragmented credit data to an evidence-backed distress narrative.
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
          Nexus is an evolving research platform for distressed-credit and leveraged-finance
          professionals — not a finished, fully automated product.
        </Typography>
      </Box>

      <Section>
        <SectionHeading>What Nexus Does</SectionHeading>
        <Typography variant="body2" color="text.secondary">
          Distressed-credit research requires analysts to piece together issuer information from
          multiple sources — SEC filings, court activity, security data, market conditions, and
          internal research signals. Nexus organizes those inputs around the issuer and surfaces the
          most relevant credit developments in one workflow.
        </Typography>
        <WorkflowFlow />
      </Section>

      <Section>
        <SectionHeading>Current Capabilities</SectionHeading>
        <Stack direction="row" flexWrap="wrap" useFlexGap spacing={2}>
          {CAPABILITIES.map((capability) => (
            <Box key={capability.title} sx={{ width: { xs: "100%", sm: 300 } }}>
              <CapabilityCard {...capability} />
            </Box>
          ))}
        </Stack>
      </Section>

      <Section>
        <SectionHeading>Data Sources</SectionHeading>
        <Stack spacing={1.5}>
          {DATA_SOURCES.map((source) => (
            <Stack
              key={source.name}
              direction={{ xs: "column", sm: "row" }}
              spacing={1.5}
              alignItems={{ sm: "center" }}
            >
              <Chip
                label={source.name}
                size="small"
                variant="outlined"
                sx={{ minWidth: 160, justifyContent: "flex-start" }}
              />
              <Typography variant="body2" color="text.secondary">
                {source.role}
              </Typography>
            </Stack>
          ))}
        </Stack>
      </Section>

      <Section>
        <SectionHeading>Research Coverage</SectionHeading>
        <Typography variant="body2" color="text.secondary">
          The current Nexus prototype includes SEC-derived research history beginning January 1,
          2026, with new activity incorporated through ongoing daily research cycles. Historical
          coverage is expanded through backfill/reconciliation while daily discovery captures newly
          available research activity.
        </Typography>
      </Section>

      <Section>
        <SectionHeading>How Nexus Uses AI</SectionHeading>
        <Paper
          variant="outlined"
          sx={{
            p: 2,
            bgcolor: "#EEF3F8",
            borderLeft: 3,
            borderLeftColor: "info.main",
          }}
        >
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
            Nexus does not send everything to a language model. Most evidence is filtered by
            deterministic rules first; AI is reserved for the cases that genuinely need semantic
            judgment, such as:
          </Typography>
          <Stack component="ul" spacing={0.5} sx={{ pl: 2.5, m: 0, mb: 2 }}>
            {AI_TASKS.map((task) => (
              <Typography key={task} component="li" variant="body2" color="text.secondary">
                {task}
              </Typography>
            ))}
          </Stack>
          <Typography variant="subtitle2" gutterBottom>
            Model routing
          </Typography>
          <Stack component="ol" spacing={0.5} sx={{ pl: 2.5, m: 0 }}>
            {AI_ROUTING_STEPS.map((step) => (
              <Typography key={step} component="li" variant="body2" color="text.secondary">
                {step}
              </Typography>
            ))}
          </Stack>
          <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 2 }}>
            AI in Nexus assists research interpretation. It does not make investment decisions,
            execute trades, or guarantee accuracy — every AI-assisted conclusion remains linked to
            its underlying evidence for analyst review.
          </Typography>
        </Paper>
      </Section>

      <Section>
        <SectionHeading>AI Governance &amp; Cost Control</SectionHeading>
        <Box
          sx={{
            mb: 1.5,
            px: 2,
            py: 1,
            borderLeft: 3,
            borderLeftColor: "primary.main",
            bgcolor: "background.default",
          }}
        >
          <Typography variant="body2" fontStyle="italic">
            AI is treated as a governed research tool, not an unlimited background expense.
          </Typography>
        </Box>
        <Stack component="ul" spacing={0.5} sx={{ pl: 2.5, m: 0 }}>
          {GOVERNANCE_POINTS.map((point) => (
            <Typography key={point} component="li" variant="body2" color="text.secondary">
              {point}
            </Typography>
          ))}
        </Stack>
      </Section>

      <Section>
        <SectionHeading>Evidence First</SectionHeading>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          Every material Nexus conclusion is meant to stay traceable to its underlying evidence. For
          each credit development, Nexus surfaces the source filing or docket, the event date,
          confidence where available, why the event matters, and its research classification.
        </Typography>
        <Typography variant="body2" color="text.secondary">
          AI-assisted interpretation is presented as interpretation, not as settled fact, when the
          underlying evidence is ambiguous. The same principle applies to Research Universe
          coverage: a system-suggested membership is always shown separately from a verified,
          current one, and is never presented as confirmed.
        </Typography>
      </Section>

      <Section>
        <SectionHeading>Available Today vs. What's Next</SectionHeading>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={3}>
          <RoadmapColumn label="Available Today" items={AVAILABLE_TODAY} color="success" />
          <RoadmapColumn label="Planned Next" items={PLANNED_NEXT} color="warning" />
          <RoadmapColumn label="Future Direction" items={FUTURE_DIRECTION} color="default" />
        </Stack>
      </Section>

      <Box>
        <SectionHeading>What This Looks Like in Practice</SectionHeading>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Two real issuers currently tracked in Credit Universe illustrate the distress progression
          Nexus reconstructs from source evidence:
        </Typography>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
          <Card variant="outlined" sx={{ flex: 1 }}>
            <CardContent>
              <Typography variant="subtitle1" gutterBottom>
                Trinseo PLC
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Covenant stress → going concern → delisting / capital-structure pressure →
                restructuring support agreement → Chapter&nbsp;11 → DIP financing
              </Typography>
              <Box sx={{ mt: 1.5 }}>
                <Link component={RouterLink} to="/?q=Trinseo" underline="hover" variant="body2">
                  Find Trinseo in Credit Universe →
                </Link>
              </Box>
            </CardContent>
          </Card>
          <Card variant="outlined" sx={{ flex: 1 }}>
            <CardContent>
              <Typography variant="subtitle1" gutterBottom>
                Diebold Nixdorf
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Chapter&nbsp;11 → bankruptcy court proceedings → plan confirmation → post-emergence
                developments
              </Typography>
              <Box sx={{ mt: 1.5 }}>
                <Link component={RouterLink} to="/?q=Diebold" underline="hover" variant="body2">
                  Find Diebold Nixdorf in Credit Universe →
                </Link>
              </Box>
            </CardContent>
          </Card>
        </Stack>
      </Box>
    </Stack>
  );
}
