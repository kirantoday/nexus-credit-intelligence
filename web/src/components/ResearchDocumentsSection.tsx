import { type ReactElement, useState } from "react";
import { Link as RouterLink } from "react-router";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  IconButton,
  Stack,
  Tooltip,
  Typography,
} from "@mui/material";
import UploadFileOutlinedIcon from "@mui/icons-material/UploadFileOutlined";
import VisibilityOutlinedIcon from "@mui/icons-material/VisibilityOutlined";
import DownloadOutlinedIcon from "@mui/icons-material/DownloadOutlined";
import ArchiveOutlinedIcon from "@mui/icons-material/ArchiveOutlined";
import { ResearchDocumentTypeBadge } from "./ResearchDocumentTypeBadge";
import {
  useArchiveResearchDocument,
  useResearchDocumentDownloadUrl,
  useResearchDocuments,
} from "../queries/useResearchDocuments";
import { formatDate, formatDateTime } from "../lib/format";
import type { ResearchDocument } from "../api/researchDocument";

/**
 * "Research Documents" — the uploaded-artifact layer beneath Analyst
 * Research Notes on Issuer Detail (Milestone 10B). A compact card list,
 * matching `ResearchNotesSection`'s established shape: enough to see what
 * exists and act on it (view/download/archive), full upload is a
 * deliberate click-through to its own page.
 */
export function ResearchDocumentsSection({ issuerId }: { issuerId: string }): ReactElement {
  const documentsQuery = useResearchDocuments(issuerId);
  const documents = documentsQuery.data?.documents ?? [];

  return (
    <Box>
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1.5 }}>
        <Typography variant="h6">Research Documents</Typography>
        <Button
          size="small"
          variant="contained"
          startIcon={<UploadFileOutlinedIcon />}
          component={RouterLink}
          to={`/issuers/${issuerId}/research-documents/new`}
        >
          Upload Document
        </Button>
      </Stack>

      {documentsQuery.isLoading && (
        <Box sx={{ py: 2, textAlign: "center" }}>
          <CircularProgress size={24} />
        </Box>
      )}

      {documentsQuery.isError && <Alert severity="error">Could not load research documents.</Alert>}

      {!documentsQuery.isLoading && !documentsQuery.isError && documents.length === 0 && (
        <Typography variant="body2" color="text.secondary">
          No research documents yet for this issuer — upload a credit agreement, presentation, or
          internal memo with "Upload Document."
        </Typography>
      )}

      <Stack spacing={1.5}>
        {documents.map((document) => (
          <ResearchDocumentCard key={document.id} document={document} />
        ))}
      </Stack>
    </Box>
  );
}

function ResearchDocumentCard({ document }: { document: ResearchDocument }): ReactElement {
  const downloadUrlMutation = useResearchDocumentDownloadUrl();
  const archiveMutation = useArchiveResearchDocument();
  const [archived, setArchived] = useState(document.is_archived);

  function handleOpen(forceDownload: boolean): void {
    downloadUrlMutation.mutate(
      { documentId: document.id, forceDownload },
      {
        onSuccess: (result) => {
          window.open(result.signed_url, "_blank", "noopener,noreferrer");
        },
      },
    );
  }

  function handleArchive(): void {
    archiveMutation.mutate({ documentId: document.id }, { onSuccess: () => setArchived(true) });
  }

  return (
    <Card variant="outlined">
      <CardContent>
        <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
          <Typography variant="subtitle1" sx={{ mr: 1 }}>
            <RouterLink to={`/research-documents/${document.id}`}>{document.title}</RouterLink>
          </Typography>
          <ResearchDocumentTypeBadge documentType={document.document_type} />
          {document.confidentiality_classification === "restricted" && (
            <Chip label="Restricted" size="small" color="warning" variant="outlined" />
          )}
          {archived && <Chip label="Archived" size="small" variant="outlined" />}
        </Stack>

        {document.description && (
          <Typography variant="body2" sx={{ mt: 0.5 }}>
            {document.description}
          </Typography>
        )}

        <Typography variant="caption" color="text.secondary" component="div" sx={{ mt: 0.5 }}>
          {document.original_filename}
          {document.document_date && ` · Document date ${formatDate(document.document_date)}`}
          {" · uploaded "}
          {formatDateTime(document.created_at)}
          {document.uploaded_by && ` by ${document.uploaded_by}`}
        </Typography>

        <Stack direction="row" spacing={1} sx={{ mt: 1.5 }}>
          <Tooltip title="View">
            <span>
              <IconButton
                size="small"
                onClick={() => handleOpen(false)}
                disabled={downloadUrlMutation.isPending}
                aria-label="View document"
              >
                <VisibilityOutlinedIcon fontSize="small" />
              </IconButton>
            </span>
          </Tooltip>
          <Tooltip title="Download">
            <span>
              <IconButton
                size="small"
                onClick={() => handleOpen(true)}
                disabled={downloadUrlMutation.isPending}
                aria-label="Download document"
              >
                <DownloadOutlinedIcon fontSize="small" />
              </IconButton>
            </span>
          </Tooltip>
          {!archived && (
            <Tooltip title="Archive">
              <span>
                <IconButton
                  size="small"
                  onClick={handleArchive}
                  disabled={archiveMutation.isPending}
                  aria-label="Archive document"
                >
                  <ArchiveOutlinedIcon fontSize="small" />
                </IconButton>
              </span>
            </Tooltip>
          )}
        </Stack>

        {downloadUrlMutation.isError && (
          <Alert severity="error" sx={{ mt: 1 }}>
            Could not open document.
          </Alert>
        )}
      </CardContent>
    </Card>
  );
}
