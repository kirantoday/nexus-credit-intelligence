import type { ReactElement } from "react";
import { Link as RouterLink, useParams } from "react-router";
import {
  Alert,
  Box,
  Chip,
  CircularProgress,
  Link,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
} from "@mui/material";
import { ApiError } from "../api/client";
import type { IssuerActivityCategory, IssuerActivityItem } from "../api/issuer";
import type { IssuerUniverseMembership } from "../api/researchUniverse";
import { CapitalStructureStack } from "../components/CapitalStructureStack";
import { CourtDocketSection } from "../components/CourtDocketSection";
import { DistressTimeline } from "../components/DistressTimeline";
import { ProvenanceBadge } from "../components/ProvenanceBadge";
import { SyntheticDataBadge } from "../components/SyntheticDataBadge";
import { useCapitalStructure } from "../queries/useCapitalStructure";
import { useIssuerDetail } from "../queries/useIssuerDetail";
import { useIssuerTimeline } from "../queries/useIssuerTimeline";
import { formatCompactCurrency, formatDate } from "../lib/format";

const ACTIVITY_CATEGORY_LABEL: Record<IssuerActivityCategory, string> = {
  filing: "Filing",
  security_identified: "Security identified",
  capital_structure_update: "Capital structure",
};

const PROVIDER_DISPLAY_LABEL: Record<string, string> = {
  openfigi: "OpenFIGI",
  sec_edgar: "SEC EDGAR",
  courtlistener: "CourtListener",
};

interface DisplayActivityRow {
  key: string;
  occurred_on: string;
  category: IssuerActivityCategory;
  headline: string;
  source_url: string | null;
  count: number;
  /** Only set (and only rendered) when every grouped item shares one provider. */
  uniformProvider: string | null;
}

/**
 * `security_identified` rows are the one category where "occurred_on" is
 * genuinely a Nexus/data-coverage date (when OpenFIGI matched an
 * instrument), not an issuer credit event — a batch of five securities
 * matched the same day reads as five separate rows otherwise, which
 * overstates how much actually "changed." Collapses same-day
 * `security_identified` rows into one grouped row; every other category
 * (real filing/capital-structure dates) renders individually, unchanged.
 */
function groupRecentActivity(items: IssuerActivityItem[]): DisplayActivityRow[] {
  const rows: DisplayActivityRow[] = [];
  const groupIndexByKey = new Map<string, number>();

  for (const item of items) {
    if (item.category !== "security_identified") {
      rows.push({
        key: `${item.category}-${item.occurred_on}-${rows.length}`,
        occurred_on: item.occurred_on,
        category: item.category,
        headline: item.headline,
        source_url: item.source_url,
        count: 1,
        uniformProvider: item.provider,
      });
      continue;
    }

    const key = `security_identified-${item.occurred_on}`;
    const existingIndex = groupIndexByKey.get(key);
    if (existingIndex !== undefined) {
      const existing = rows[existingIndex];
      if (existing) {
        existing.count += 1;
        if (existing.uniformProvider !== item.provider) existing.uniformProvider = null;
      }
      continue;
    }
    groupIndexByKey.set(key, rows.length);
    rows.push({
      key,
      occurred_on: item.occurred_on,
      category: item.category,
      headline: item.headline,
      source_url: null,
      count: 1,
      uniformProvider: item.provider,
    });
  }

  return rows;
}

function groupedActivityHeadline(row: DisplayActivityRow): string {
  if (row.count <= 1) return row.headline;
  const providerLabel = row.uniformProvider
    ? (PROVIDER_DISPLAY_LABEL[row.uniformProvider] ?? row.uniformProvider)
    : null;
  return providerLabel
    ? `${row.count} securities identified through ${providerLabel}`
    : `${row.count} securities identified`;
}

function displayUniverseName(name: string): string {
  return name.replace(/^System-Detected: /, "");
}

/**
 * Splits an issuer's Research Universe memberships into what a CFO should
 * see as "current" vs. "suggested" — the underlying data/status is never
 * altered, only which bucket each membership renders in (PLAN.md CFO-demo
 * polish pass).
 *
 * A `partial` (system-suggested, unconfirmed) membership is always
 * "suggested," never "current" — reusing Milestone 7.5.1's verification
 * semantics rather than re-deriving them. A `verified` manually-curated
 * membership is always "current." A `verified` System-Detected: * one is
 * only shown as "current" (name prefix stripped) when this issuer has no
 * manually-curated verified membership at all — when curated coverage
 * exists, the system-detected duplicate of the same underlying
 * classification would just repeat it under an internal name.
 */
function splitUniverseMemberships(memberships: IssuerUniverseMembership[]): {
  current: IssuerUniverseMembership[];
  suggested: IssuerUniverseMembership[];
} {
  const verifiedCurated = memberships.filter(
    (m) => m.verification_status === "verified" && m.curation_method === "manual_curated",
  );
  const verifiedSystemDetected = memberships.filter(
    (m) => m.verification_status === "verified" && m.curation_method === "system_seeded",
  );
  const current = verifiedCurated.length > 0 ? verifiedCurated : verifiedSystemDetected;
  const suggested = memberships.filter((m) => m.verification_status === "partial");
  return { current, suggested };
}

function SectionHeading({ children }: { children: string }): ReactElement {
  return (
    <Typography variant="h6" gutterBottom>
      {children}
    </Typography>
  );
}

export function IssuerPage(): ReactElement {
  const { issuerId } = useParams<{ issuerId: string }>();
  const issuerQuery = useIssuerDetail(issuerId);
  const capitalStructureQuery = useCapitalStructure(issuerId);
  const timelineQuery = useIssuerTimeline(issuerId);

  if (issuerQuery.isLoading) {
    return (
      <Box sx={{ py: 8, textAlign: "center" }}>
        <CircularProgress />
      </Box>
    );
  }

  if (issuerQuery.isError) {
    const notFound = issuerQuery.error instanceof ApiError && issuerQuery.error.status === 404;
    return (
      <Alert severity={notFound ? "warning" : "error"}>
        {notFound
          ? "This issuer doesn't exist."
          : `Could not load this issuer: ${issuerQuery.error instanceof Error ? issuerQuery.error.message : "unknown error"}`}
      </Alert>
    );
  }

  const issuer = issuerQuery.data;
  if (!issuer) {
    return <Alert severity="warning">This issuer doesn't exist.</Alert>;
  }

  const positions = capitalStructureQuery.data?.positions ?? [];
  const showFlatSecurities = positions.length === 0 && issuer.securities.length > 0;

  return (
    <Stack spacing={3}>
      <Box>
        <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
          <Typography variant="h4">{issuer.legal_name}</Typography>
          <SyntheticDataBadge isSynthetic={issuer.is_synthetic} reason={issuer.synthetic_reason} />
        </Stack>
        <Stack direction="row" spacing={1} sx={{ mt: 1 }} flexWrap="wrap">
          {issuer.ticker && <Chip label={`Ticker: ${issuer.ticker}`} size="small" />}
          {issuer.cik && <Chip label={`CIK: ${issuer.cik}`} size="small" />}
          {issuer.sector && <Chip label={issuer.sector} size="small" variant="outlined" />}
          {issuer.sic && <Chip label={`SIC ${issuer.sic}`} size="small" variant="outlined" />}
        </Stack>
      </Box>

      <Paper variant="outlined" sx={{ p: 2 }}>
        <SectionHeading>Distress Timeline</SectionHeading>
        {timelineQuery.isLoading && (
          <Typography variant="body2" color="text.secondary">
            Loading timeline…
          </Typography>
        )}
        {timelineQuery.isError && (
          <Alert severity="error">Could not load the distress timeline.</Alert>
        )}
        {timelineQuery.data && <DistressTimeline timeline={timelineQuery.data} />}
      </Paper>

      <Paper id="securities-section" variant="outlined" sx={{ p: 2 }}>
        <SectionHeading>
          What debt exists, where does it sit, and what's secured or unsecured?
        </SectionHeading>
        <CapitalStructureStack
          positions={positions}
          isLoading={capitalStructureQuery.isLoading}
          isError={capitalStructureQuery.isError}
        />
      </Paper>

      {showFlatSecurities && (
        <Paper variant="outlined" sx={{ p: 2 }}>
          <SectionHeading>Securities on file</SectionHeading>
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Instrument</TableCell>
                  <TableCell>Identifiers</TableCell>
                  <TableCell>Maturity</TableCell>
                  <TableCell align="right">Amount Outstanding</TableCell>
                  <TableCell>Source</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {issuer.securities.map((security) => (
                  <TableRow key={security.security_id} hover>
                    <TableCell>
                      <Typography variant="body2">{security.description}</Typography>
                      <Typography variant="caption" color="text.secondary">
                        {security.instrument_type}
                        {security.secured !== null
                          ? security.secured
                            ? " · secured"
                            : " · unsecured"
                          : ""}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="caption">
                        {security.cusip ?? security.isin ?? security.figi ?? "—"}
                      </Typography>
                    </TableCell>
                    <TableCell>{formatDate(security.maturity_date)}</TableCell>
                    <TableCell align="right">
                      {formatCompactCurrency(security.amount_outstanding)}
                    </TableCell>
                    <TableCell>
                      <Stack direction="row" spacing={1} alignItems="center">
                        <ProvenanceBadge
                          provider={security.provider}
                          asOfDate={security.as_of_date}
                          retrievedAt={security.retrieved_at}
                          freshness={security.freshness}
                        />
                        <SyntheticDataBadge
                          isSynthetic={security.is_synthetic}
                          reason={security.synthetic_reason}
                        />
                      </Stack>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Paper>
      )}

      <Paper variant="outlined" sx={{ p: 2 }}>
        <SectionHeading>What filings support this?</SectionHeading>
        {issuer.sec_filings.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            No SEC filings on file for this issuer yet.
          </Typography>
        ) : (
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Filing</TableCell>
                  <TableCell>Accession No.</TableCell>
                  <TableCell>Filed</TableCell>
                  <TableCell>Source</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {issuer.sec_filings.map((filing) => (
                  <TableRow key={filing.filing_id} hover>
                    <TableCell>
                      {filing.primary_document_url ? (
                        <Link
                          href={filing.primary_document_url}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          {filing.form_type}
                          {filing.is_amendment ? " (amended)" : ""}
                        </Link>
                      ) : (
                        `${filing.form_type}${filing.is_amendment ? " (amended)" : ""}`
                      )}
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" fontFamily="monospace">
                        {filing.accession_no}
                      </Typography>
                    </TableCell>
                    <TableCell>{formatDate(filing.filing_date)}</TableCell>
                    <TableCell>
                      <ProvenanceBadge
                        provider={filing.provider}
                        asOfDate={filing.as_of_date}
                        retrievedAt={filing.retrieved_at}
                        freshness={filing.freshness}
                      />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Paper>

      <Paper variant="outlined" sx={{ p: 2 }}>
        <SectionHeading>Recent data updates</SectionHeading>
        <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1.5 }}>
          When Nexus's own data coverage changed for this issuer — not necessarily when these events
          happened to the issuer itself. See the Distress Timeline above for material credit
          developments and their real event dates.
        </Typography>
        {issuer.recent_activity.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            No recorded data updates for this issuer yet.
          </Typography>
        ) : (
          <Stack spacing={1}>
            {groupRecentActivity(issuer.recent_activity).map((row) => (
              <Stack key={row.key} direction="row" spacing={1.5} alignItems="baseline">
                <Typography variant="caption" color="text.secondary" sx={{ minWidth: 90 }}>
                  {formatDate(row.occurred_on)}
                </Typography>
                <Chip
                  label={ACTIVITY_CATEGORY_LABEL[row.category]}
                  size="small"
                  variant="outlined"
                />
                {row.source_url ? (
                  <Link href={row.source_url} target="_blank" rel="noopener noreferrer">
                    <Typography variant="body2">{groupedActivityHeadline(row)}</Typography>
                  </Link>
                ) : (
                  <Typography variant="body2">{groupedActivityHeadline(row)}</Typography>
                )}
                {row.count > 1 && (
                  <Link href="#securities-section" underline="hover">
                    <Typography variant="caption">View securities</Typography>
                  </Link>
                )}
              </Stack>
            ))}
          </Stack>
        )}
      </Paper>

      <Paper variant="outlined" sx={{ p: 2 }}>
        <SectionHeading>What happened in court?</SectionHeading>
        <CourtDocketSection dockets={issuer.court_dockets} />
      </Paper>

      <Paper variant="outlined" sx={{ p: 2 }}>
        <SectionHeading>Where did this information come from?</SectionHeading>
        <Stack direction="row" spacing={2} flexWrap="wrap">
          {issuer.data_sources.map((source) => (
            <Box key={source.provider}>
              <Typography variant="body2" fontWeight={600}>
                {source.provider}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {source.record_count} record{source.record_count === 1 ? "" : "s"} · last updated{" "}
                {formatDate(source.latest_retrieved_at)}
              </Typography>
            </Box>
          ))}
        </Stack>
      </Paper>

      <Paper variant="outlined" sx={{ p: 2 }}>
        <SectionHeading>Which Research Universes is this issuer in?</SectionHeading>
        <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1.5 }}>
          Curated coverage decisions, each with a dated rationale — never itself an assertion of
          current distress, bankruptcy, rating, or refinancing risk. See the sections above for
          that, sourced from dated evidence.
        </Typography>
        {(() => {
          const { current, suggested } = splitUniverseMemberships(issuer.universe_memberships);
          if (current.length === 0 && suggested.length === 0) {
            return (
              <Typography variant="body2" color="text.secondary">
                Not currently a member of any Research Universe.
              </Typography>
            );
          }
          return (
            <Stack spacing={2}>
              {current.length > 0 && (
                <Box>
                  <Typography variant="subtitle2" gutterBottom>
                    Current Research Universes
                  </Typography>
                  <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                    {current.map((membership) => (
                      <Tooltip
                        key={membership.collection_id}
                        title={`${membership.rationale}${membership.rationale_as_of_date ? ` (as of ${formatDate(membership.rationale_as_of_date)})` : ""}`}
                      >
                        <Chip
                          component={RouterLink}
                          to={`/?universe=${membership.collection_id}`}
                          clickable
                          label={displayUniverseName(membership.name)}
                          size="small"
                          variant="filled"
                          color={membership.collection_type === "benchmark" ? "info" : "default"}
                        />
                      </Tooltip>
                    ))}
                  </Stack>
                </Box>
              )}
              {suggested.length > 0 && (
                <Box>
                  <Typography variant="subtitle2" gutterBottom>
                    Nexus suggested coverage
                  </Typography>
                  <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                    {suggested.map((membership) => (
                      <Tooltip
                        key={membership.collection_id}
                        title={`System-suggested, pending analyst confirmation — ${membership.rationale}${membership.rationale_as_of_date ? ` (as of ${formatDate(membership.rationale_as_of_date)})` : ""}`}
                      >
                        <Chip
                          component={RouterLink}
                          to={`/?universe=${membership.collection_id}`}
                          clickable
                          label={`${displayUniverseName(membership.name)} (suggested)`}
                          size="small"
                          variant="outlined"
                          sx={{ borderStyle: "dashed" }}
                        />
                      </Tooltip>
                    ))}
                  </Stack>
                </Box>
              )}
            </Stack>
          );
        })()}
      </Paper>

      <Box>
        <Link component={RouterLink} to="/" underline="hover">
          ← Back to Credit Universe
        </Link>
      </Box>
    </Stack>
  );
}
