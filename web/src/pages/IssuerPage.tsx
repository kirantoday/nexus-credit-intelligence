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
import type { IssuerActivityCategory } from "../api/issuer";
import { CapitalStructureStack } from "../components/CapitalStructureStack";
import { CourtDocketSection } from "../components/CourtDocketSection";
import { ProvenanceBadge } from "../components/ProvenanceBadge";
import { SyntheticDataBadge } from "../components/SyntheticDataBadge";
import { useCapitalStructure } from "../queries/useCapitalStructure";
import { useIssuerDetail } from "../queries/useIssuerDetail";
import { formatCompactCurrency, formatDate } from "../lib/format";

const ACTIVITY_CATEGORY_LABEL: Record<IssuerActivityCategory, string> = {
  filing: "Filing",
  security_identified: "Security identified",
  capital_structure_update: "Capital structure",
};

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
        {issuer.financial_facts.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            No filings on file for this issuer yet.
          </Typography>
        ) : (
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Concept</TableCell>
                  <TableCell align="right">Value</TableCell>
                  <TableCell>Filing</TableCell>
                  <TableCell>Filed</TableCell>
                  <TableCell>Source</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {issuer.financial_facts.map((fact) => (
                  <TableRow key={fact.financial_fact_id} hover>
                    <TableCell>
                      <Typography variant="body2">{fact.concept}</Typography>
                      <Typography variant="caption" color="text.secondary">
                        FY{fact.fiscal_year} {fact.fiscal_period}
                      </Typography>
                    </TableCell>
                    <TableCell align="right">
                      {Number(fact.value).toLocaleString()} {fact.unit}
                    </TableCell>
                    <TableCell>
                      {fact.source_url ? (
                        <Link href={fact.source_url} target="_blank" rel="noopener noreferrer">
                          {fact.form_type} ({fact.accession_no})
                        </Link>
                      ) : (
                        `${fact.form_type} (${fact.accession_no})`
                      )}
                    </TableCell>
                    <TableCell>{formatDate(fact.filing_date)}</TableCell>
                    <TableCell>
                      <ProvenanceBadge
                        provider={fact.provider}
                        asOfDate={fact.as_of_date}
                        retrievedAt={fact.retrieved_at}
                        freshness={fact.freshness}
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
        <SectionHeading>What changed recently?</SectionHeading>
        {issuer.recent_activity.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            No recorded activity for this issuer yet.
          </Typography>
        ) : (
          <Stack spacing={1}>
            {issuer.recent_activity.map((item, index) => (
              <Stack
                key={`${item.category}-${index}`}
                direction="row"
                spacing={1.5}
                alignItems="baseline"
              >
                <Typography variant="caption" color="text.secondary" sx={{ minWidth: 90 }}>
                  {formatDate(item.occurred_on)}
                </Typography>
                <Chip
                  label={ACTIVITY_CATEGORY_LABEL[item.category]}
                  size="small"
                  variant="outlined"
                />
                {item.source_url ? (
                  <Link href={item.source_url} target="_blank" rel="noopener noreferrer">
                    <Typography variant="body2">{item.headline}</Typography>
                  </Link>
                ) : (
                  <Typography variant="body2">{item.headline}</Typography>
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
        {issuer.universe_memberships.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            Not currently a member of any Research Universe.
          </Typography>
        ) : (
          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
            {issuer.universe_memberships.map((membership) => (
              <Tooltip
                key={membership.collection_id}
                title={`${membership.rationale}${membership.rationale_as_of_date ? ` (as of ${formatDate(membership.rationale_as_of_date)})` : ""}`}
              >
                <Chip
                  component={RouterLink}
                  to={`/?universe=${membership.collection_id}`}
                  clickable
                  label={membership.name}
                  size="small"
                  variant="outlined"
                  color={membership.collection_type === "benchmark" ? "info" : "default"}
                />
              </Tooltip>
            ))}
          </Stack>
        )}
      </Paper>

      <Box>
        <Link component={RouterLink} to="/" underline="hover">
          ← Back to Credit Universe
        </Link>
      </Box>
    </Stack>
  );
}
