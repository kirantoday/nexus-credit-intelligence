import type { ReactElement } from "react";
import { Link as RouterLink } from "react-router";
import {
  Alert,
  Box,
  Button,
  Card,
  CardActionArea,
  CardContent,
  Chip,
  CircularProgress,
  Stack,
  Typography,
} from "@mui/material";
import EditNoteOutlinedIcon from "@mui/icons-material/EditNoteOutlined";
import { ConvictionBadge } from "./ConvictionBadge";
import { ThesisStatusBadge } from "./ThesisStatusBadge";
import { useResearchNotes } from "../queries/useResearchNotes";
import { formatDateTime } from "../lib/format";

/**
 * "Analyst Research Notes" — the analyst-authored layer beneath the
 * Distress Timeline on Issuer Detail (Milestone 10A). Never overwhelms the
 * timeline: a compact card list, not the full note content — reading a note
 * is a deliberate click-through, matching "a note should feel like an
 * investment-research artifact, not a generic text box."
 */
export function ResearchNotesSection({ issuerId }: { issuerId: string }): ReactElement {
  const notesQuery = useResearchNotes(issuerId);
  const notes = notesQuery.data?.notes ?? [];

  return (
    <Box>
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1.5 }}>
        <Typography variant="h6">Analyst Research Notes</Typography>
        <Button
          size="small"
          variant="contained"
          startIcon={<EditNoteOutlinedIcon />}
          component={RouterLink}
          to={`/issuers/${issuerId}/research-notes/new`}
        >
          Write Research Note
        </Button>
      </Stack>

      {notesQuery.isLoading && (
        <Box sx={{ py: 2, textAlign: "center" }}>
          <CircularProgress size={24} />
        </Box>
      )}

      {notesQuery.isError && <Alert severity="error">Could not load research notes.</Alert>}

      {!notesQuery.isLoading && !notesQuery.isError && notes.length === 0 && (
        <Typography variant="body2" color="text.secondary">
          No research notes yet for this issuer — record an investment thesis with "Write Research
          Note."
        </Typography>
      )}

      <Stack spacing={1.5}>
        {notes.map((note) => (
          <Card key={note.id} variant="outlined">
            <CardActionArea component={RouterLink} to={`/research-notes/${note.id}`}>
              <CardContent>
                <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
                  <Typography variant="subtitle1" sx={{ mr: 1 }}>
                    {note.title}
                  </Typography>
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
                </Stack>
                <Typography variant="caption" color="text.secondary">
                  Version {note.current_version_number} · updated {formatDateTime(note.updated_at)}
                </Typography>
              </CardContent>
            </CardActionArea>
          </Card>
        ))}
      </Stack>
    </Box>
  );
}
