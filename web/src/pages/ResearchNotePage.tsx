import { type ReactElement, useState } from "react";
import { Link as RouterLink, useNavigate, useParams } from "react-router";
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Divider,
  Link,
  List,
  ListItem,
  ListItemText,
  Paper,
  Stack,
  Typography,
} from "@mui/material";
import ArchiveOutlinedIcon from "@mui/icons-material/ArchiveOutlined";
import EditOutlinedIcon from "@mui/icons-material/EditOutlined";
import HistoryOutlinedIcon from "@mui/icons-material/HistoryOutlined";
import { ApiError } from "../api/client";
import type { EvidenceRef, ResearchNote, ResearchNoteVersion } from "../api/researchNote";
import { ConvictionBadge } from "../components/ConvictionBadge";
import { ThesisStatusBadge } from "../components/ThesisStatusBadge";
import {
  useArchiveResearchNote,
  useResearchNote,
  useResearchNoteAuditEvents,
  useResearchNoteVersion,
  useResearchNoteVersions,
} from "../queries/useResearchNotes";
import { formatDateTime } from "../lib/format";

const AUDIT_EVENT_LABEL: Record<string, string> = {
  research_note_created: "Note created",
  research_note_updated: "Note updated",
  research_note_archived: "Note archived",
};

interface NoteSectionContent {
  title: string;
  thesis_status: ResearchNote["thesis_status"];
  conviction: ResearchNote["conviction"];
  bull_case: string | null;
  base_case: string | null;
  bear_case: string | null;
  catalysts: string | null;
  risks: string | null;
  invalidation_conditions: string | null;
  evidence_refs: EvidenceRef[] | null;
}

function toSectionContent(source: ResearchNote | ResearchNoteVersion): NoteSectionContent {
  return {
    title: source.title,
    thesis_status: source.thesis_status,
    conviction: source.conviction,
    bull_case: source.bull_case,
    base_case: source.base_case,
    bear_case: source.bear_case,
    catalysts: source.catalysts,
    risks: source.risks,
    invalidation_conditions: source.invalidation_conditions,
    evidence_refs: source.evidence_refs,
  };
}

function CaseSection({ heading, body }: { heading: string; body: string | null }): ReactElement {
  return (
    <Box>
      <Typography variant="subtitle2" gutterBottom>
        {heading}
      </Typography>
      <Typography
        variant="body2"
        color={body ? "text.primary" : "text.secondary"}
        sx={{ whiteSpace: "pre-wrap" }}
      >
        {body || "Not recorded."}
      </Typography>
    </Box>
  );
}

export function ResearchNotePage(): ReactElement {
  const { noteId } = useParams<{ noteId: string }>();
  const navigate = useNavigate();
  const [viewedVersion, setViewedVersion] = useState<number | null>(null);

  const noteQuery = useResearchNote(noteId);
  const versionsQuery = useResearchNoteVersions(noteId);
  const auditEventsQuery = useResearchNoteAuditEvents(noteId);
  const historicalVersionQuery = useResearchNoteVersion(noteId, viewedVersion ?? undefined);
  const archiveMutation = useArchiveResearchNote();

  if (noteQuery.isLoading) {
    return (
      <Box sx={{ py: 8, textAlign: "center" }}>
        <CircularProgress />
      </Box>
    );
  }

  if (noteQuery.isError || !noteQuery.data) {
    const notFound = noteQuery.error instanceof ApiError && noteQuery.error.status === 404;
    return (
      <Alert severity={notFound ? "warning" : "error"}>
        {notFound ? "This research note doesn't exist." : "Could not load this research note."}
      </Alert>
    );
  }

  const note = noteQuery.data;
  const versions = versionsQuery.data?.versions ?? [];
  const auditEvents = auditEventsQuery.data?.events ?? [];
  const isViewingHistorical =
    viewedVersion !== null && viewedVersion !== note.current_version_number;
  const content: NoteSectionContent =
    isViewingHistorical && historicalVersionQuery.data
      ? toSectionContent(historicalVersionQuery.data)
      : toSectionContent(note);

  function handleArchive(): void {
    if (!noteId) return;
    archiveMutation.mutate({ noteId });
  }

  return (
    <Stack spacing={3}>
      <Box>
        <Link component={RouterLink} to={`/issuers/${note.issuer_id}`} underline="hover">
          ← Back to Issuer
        </Link>
      </Box>

      {isViewingHistorical && (
        <Alert
          severity="info"
          action={
            <Button color="inherit" size="small" onClick={() => setViewedVersion(null)}>
              Back to current
            </Button>
          }
        >
          Viewing historical Version {viewedVersion} — read-only. This does not reflect the note's
          current content.
        </Alert>
      )}

      <Stack
        direction="row"
        justifyContent="space-between"
        alignItems="flex-start"
        flexWrap="wrap"
        spacing={2}
      >
        <Box>
          <Typography variant="h4" gutterBottom>
            {content.title}
          </Typography>
          <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
            <ThesisStatusBadge status={content.thesis_status} />
            {content.conviction && <ConvictionBadge conviction={content.conviction} />}
            {note.is_demo && (
              <Chip label="Demo Research Note" size="small" color="secondary" variant="outlined" />
            )}
            {note.is_archived && <Chip label="Archived" size="small" variant="outlined" />}
            {!isViewingHistorical && (
              <Typography variant="caption" color="text.secondary">
                Version {note.current_version_number} · updated {formatDateTime(note.updated_at)}
              </Typography>
            )}
          </Stack>
        </Box>
        {!note.is_archived && !isViewingHistorical && (
          <Stack direction="row" spacing={1}>
            <Button
              size="small"
              variant="outlined"
              startIcon={<EditOutlinedIcon />}
              onClick={() => navigate(`/research-notes/${note.id}/edit`)}
            >
              Edit
            </Button>
            <Button
              size="small"
              variant="outlined"
              color="warning"
              startIcon={<ArchiveOutlinedIcon />}
              onClick={handleArchive}
              disabled={archiveMutation.isPending}
            >
              Archive
            </Button>
          </Stack>
        )}
      </Stack>

      <Stack direction={{ xs: "column", md: "row" }} spacing={3} alignItems="flex-start">
        <Box sx={{ flex: "1 1 65%", width: "100%" }}>
          <Paper variant="outlined" sx={{ p: 2 }}>
            <Stack spacing={2.5}>
              <CaseSection heading="Base Case" body={content.base_case} />
              <Divider />
              <CaseSection heading="Bull Case" body={content.bull_case} />
              <Divider />
              <CaseSection heading="Bear Case" body={content.bear_case} />
              <Divider />
              <CaseSection heading="Catalysts" body={content.catalysts} />
              <Divider />
              <CaseSection heading="Key Risks" body={content.risks} />
              <Divider />
              <CaseSection
                heading="Invalidation Conditions"
                body={content.invalidation_conditions}
              />
              <Divider />
              <Box>
                <Typography variant="subtitle2" gutterBottom>
                  Sources / Evidence
                </Typography>
                {content.evidence_refs && content.evidence_refs.length > 0 ? (
                  <List dense disablePadding>
                    {content.evidence_refs.map((ref, idx) => (
                      <ListItem key={`${ref.entity_table}-${ref.entity_id}-${idx}`} disableGutters>
                        <ListItemText
                          primary={ref.label || `${ref.entity_table} record`}
                          secondary={`${ref.entity_table} · ${ref.entity_id}`}
                        />
                      </ListItem>
                    ))}
                  </List>
                ) : (
                  <Typography variant="body2" color="text.secondary">
                    No evidence referenced.
                  </Typography>
                )}
              </Box>
            </Stack>
          </Paper>
        </Box>

        <Box sx={{ flex: "1 1 35%", width: "100%" }}>
          <Stack spacing={2}>
            <Paper variant="outlined" sx={{ p: 2 }}>
              <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
                <HistoryOutlinedIcon fontSize="small" />
                <Typography variant="subtitle1">Version History</Typography>
              </Stack>
              {versionsQuery.isLoading && <CircularProgress size={20} />}
              {versionsQuery.isError && (
                <Alert severity="error">Could not load version history.</Alert>
              )}
              <List dense disablePadding>
                {versions.map((version) => (
                  <ListItem
                    key={version.id}
                    disableGutters
                    sx={{
                      cursor: "pointer",
                      borderRadius: 1,
                      bgcolor:
                        (viewedVersion ?? note.current_version_number) === version.version_number
                          ? "action.selected"
                          : undefined,
                      px: 1,
                    }}
                    onClick={() =>
                      setViewedVersion(
                        version.version_number === note.current_version_number
                          ? null
                          : version.version_number,
                      )
                    }
                  >
                    <ListItemText
                      primary={
                        <Stack direction="row" spacing={1} alignItems="center">
                          <Typography variant="body2" fontWeight={600}>
                            Version {version.version_number}
                          </Typography>
                          {version.version_number === note.current_version_number && (
                            <Chip label="Current" size="small" variant="outlined" color="primary" />
                          )}
                        </Stack>
                      }
                      secondary={`${formatDateTime(version.edited_at)} · ${version.thesis_status}${version.conviction ? ` · ${version.conviction} conviction` : ""}`}
                    />
                  </ListItem>
                ))}
              </List>
            </Paper>

            <Paper variant="outlined" sx={{ p: 2 }}>
              <Typography variant="subtitle1" gutterBottom>
                Audit Trail
              </Typography>
              {auditEventsQuery.isLoading && <CircularProgress size={20} />}
              {auditEventsQuery.isError && (
                <Alert severity="error">Could not load audit trail.</Alert>
              )}
              <List dense disablePadding>
                {auditEvents.map((event) => (
                  <ListItem key={event.id} disableGutters>
                    <ListItemText
                      primary={AUDIT_EVENT_LABEL[event.event_type] ?? event.event_type}
                      secondary={`${formatDateTime(event.occurred_at)} · ${event.user_id ?? "system"}`}
                    />
                  </ListItem>
                ))}
              </List>
            </Paper>
          </Stack>
        </Box>
      </Stack>
    </Stack>
  );
}
