import { type ReactElement, useState } from "react";
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Collapse,
  Link,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from "@mui/material";
import type { CourtDocketRow } from "../api/courtDocket";
import { useCourtDocketDetail } from "../queries/useCourtDockets";
import { formatDate } from "../lib/format";

const _RECENT_ENTRY_LIMIT = 10;

/**
 * One real, linked CourtListener docket embedded in Issuer Detail — "What
 * happened in court?" (PLAN.md Product Philosophy). Never fetches or
 * displays sealed material; a docket entry's own `document_available`
 * already reflects that (PLAN.md section 22).
 *
 * The case summary (parties, court, chapter, filing date, entry count) is
 * always visible — a CFO-level first read. Raw docket entries are real,
 * often-operational RECAP data (many with no description on file) that
 * would otherwise dump a wall of rows on first load, so they're fetched
 * and rendered only once the analyst asks to see them.
 */
function DocketCard({ docket }: { docket: CourtDocketRow }): ReactElement {
  const [expanded, setExpanded] = useState(false);
  const detailQuery = useCourtDocketDetail(expanded ? docket.id : undefined);
  const entries = detailQuery.data?.entries ?? [];
  const recentEntries = [...entries]
    .sort((a, b) => (b.entry_date ?? "").localeCompare(a.entry_date ?? ""))
    .slice(0, _RECENT_ENTRY_LIMIT);

  return (
    <Box sx={{ border: 1, borderColor: "divider", borderRadius: 1, p: 2 }}>
      <Stack direction="row" justifyContent="space-between" alignItems="flex-start" flexWrap="wrap">
        <Box>
          <Typography variant="subtitle1" fontWeight={600}>
            {docket.case_name}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {docket.docket_number} · {docket.court}
            {docket.date_filed ? ` · filed ${formatDate(docket.date_filed)}` : ""}
          </Typography>
        </Box>
        <Stack direction="row" spacing={1} alignItems="center">
          {docket.chapter && <Chip label={`Chapter ${docket.chapter}`} size="small" />}
          <Link href={docket.courtlistener_url} target="_blank" rel="noopener noreferrer">
            <Typography variant="caption">View on CourtListener</Typography>
          </Link>
        </Stack>
      </Stack>

      <Stack direction="row" spacing={2} alignItems="center" sx={{ mt: 1.5 }}>
        <Typography variant="caption" color="text.secondary">
          {docket.entry_count} docket entr{docket.entry_count === 1 ? "y" : "ies"} on file
        </Typography>
        <Button size="small" onClick={() => setExpanded((e) => !e)}>
          {expanded ? "Hide docket entries" : "View docket entries"}
        </Button>
      </Stack>

      <Collapse in={expanded} unmountOnExit>
        {detailQuery.isLoading && (
          <Box sx={{ py: 2, textAlign: "center" }}>
            <CircularProgress size={20} />
          </Box>
        )}
        {detailQuery.isError && (
          <Typography variant="caption" color="error">
            Could not load docket entries.
          </Typography>
        )}
        {!detailQuery.isLoading && !detailQuery.isError && (
          <>
            <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1.5 }}>
              {docket.entry_count > recentEntries.length
                ? `Showing ${recentEntries.length} most recent`
                : "All docket entries"}
            </Typography>
            <TableContainer sx={{ mt: 1 }}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Filed</TableCell>
                    <TableCell>Entry</TableCell>
                    <TableCell>Description</TableCell>
                    <TableCell>Document</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {recentEntries.map((entry) => (
                    <TableRow key={entry.id} hover>
                      <TableCell sx={{ whiteSpace: "nowrap" }}>
                        {formatDate(entry.entry_date)}
                      </TableCell>
                      <TableCell>{entry.entry_number ?? "—"}</TableCell>
                      <TableCell>
                        <Typography variant="body2" sx={{ maxWidth: 480 }}>
                          {entry.description}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        {entry.document_available ? (
                          <Chip label="Available" size="small" color="success" variant="outlined" />
                        ) : (
                          <Chip label="Not on RECAP" size="small" variant="outlined" />
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </>
        )}
      </Collapse>
    </Box>
  );
}

export function CourtDocketSection({ dockets }: { dockets: CourtDocketRow[] }): ReactElement {
  if (dockets.length === 0) {
    return (
      <Typography variant="body2" color="text.secondary">
        No court docket on file for this issuer.
      </Typography>
    );
  }
  return (
    <Stack spacing={2}>
      {dockets.map((docket) => (
        <DocketCard key={docket.id} docket={docket} />
      ))}
    </Stack>
  );
}
