import type { ReactElement } from "react";
import { Link as RouterLink } from "react-router";
import {
  Alert,
  Box,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Link,
  Stack,
  Typography,
} from "@mui/material";
import { ConvictionBadge } from "../components/ConvictionBadge";
import { ThesisStatusBadge } from "../components/ThesisStatusBadge";
import { formatDateTime } from "../lib/format";
import { useAllResearchNotes } from "../queries/useResearchNotes";

/**
 * Research Notes workspace — a cross-issuer index over the same
 * `research_note` data Issuer Detail's "Analyst Research Notes" section
 * already shows, so an analyst can find a note without first navigating to
 * its issuer. Deliberately an index page, not an editor: no create action
 * lives here (writing a note still starts from Issuer Detail, where the
 * issuer context is already established) and no note content is edited or
 * rendered in full — clicking through to `ResearchNotePage` remains the
 * only place a note's structured content, version history, and audit
 * trail are shown.
 */
export function ResearchNotesWorkspacePage(): ReactElement {
  const notesQuery = useAllResearchNotes();
  const notes = notesQuery.data?.notes ?? [];

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h4" gutterBottom>
          Research Notes
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Every analyst-authored investment thesis across every issuer, in one place. Open a note to
          read its full case, version history, and audit trail.
        </Typography>
      </Box>

      {notesQuery.isLoading && (
        <Box sx={{ py: 8, textAlign: "center" }}>
          <CircularProgress />
        </Box>
      )}

      {notesQuery.isError && <Alert severity="error">Could not load research notes.</Alert>}

      {!notesQuery.isLoading && !notesQuery.isError && notes.length === 0 && (
        <Alert severity="info">
          No research notes yet. Open an issuer and use "Write Research Note" to record the first
          one.
        </Alert>
      )}

      <Stack spacing={1.5}>
        {notes.map((note) => (
          <Card key={note.id} variant="outlined">
            <CardContent>
              <Stack
                direction="row"
                spacing={1}
                alignItems="center"
                flexWrap="wrap"
                useFlexGap
                sx={{ mb: 0.5 }}
              >
                <Link
                  component={RouterLink}
                  to={`/issuers/${note.issuer_id}`}
                  underline="hover"
                  variant="subtitle2"
                >
                  {note.issuer_legal_name}
                </Link>
                {note.issuer_ticker && (
                  <Chip label={note.issuer_ticker} size="small" variant="outlined" />
                )}
              </Stack>
              <Typography variant="subtitle1">
                <Link
                  component={RouterLink}
                  to={`/research-notes/${note.id}`}
                  underline="hover"
                  color="inherit"
                >
                  {note.title}
                </Link>
              </Typography>
              <Stack
                direction="row"
                spacing={1}
                alignItems="center"
                flexWrap="wrap"
                useFlexGap
                sx={{ mt: 1 }}
              >
                <ThesisStatusBadge status={note.thesis_status} />
                {note.conviction && <ConvictionBadge conviction={note.conviction} />}
                {note.is_demo && (
                  <Chip
                    label="Demo Research Note"
                    size="small"
                    variant="outlined"
                    color="secondary"
                  />
                )}
                <Typography variant="caption" color="text.secondary">
                  Version {note.current_version_number} · updated {formatDateTime(note.updated_at)}
                </Typography>
              </Stack>
            </CardContent>
          </Card>
        ))}
      </Stack>
    </Stack>
  );
}
