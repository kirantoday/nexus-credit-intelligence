import type { ReactElement } from "react";
import { Link as RouterLink } from "react-router";
import {
  Alert,
  Box,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  IconButton,
  Link,
  Stack,
  Tooltip,
  Typography,
} from "@mui/material";
import VisibilityOutlinedIcon from "@mui/icons-material/VisibilityOutlined";
import DownloadOutlinedIcon from "@mui/icons-material/DownloadOutlined";
import { ResearchDocumentTypeBadge } from "../components/ResearchDocumentTypeBadge";
import { formatDate, formatDateTime } from "../lib/format";
import {
  useAllResearchDocuments,
  useResearchDocumentDownloadUrl,
} from "../queries/useResearchDocuments";
import type { ResearchDocumentSummary } from "../api/researchDocument";

/**
 * Research Documents workspace — a cross-issuer index over the same
 * `research_document` data Issuer Detail's "Research Documents" section
 * already shows, so an analyst can find a document without first
 * navigating to its issuer (avoiding the discoverability gap Research
 * Notes originally had, Milestone 10A). Deliberately a simple index, not a
 * new dashboard: title, issuer, type, dates, classification, and
 * view/download/navigate actions — no upload action lives here (uploading
 * still starts from Issuer Detail, where the issuer context is already
 * established).
 */
export function ResearchDocumentsWorkspacePage(): ReactElement {
  const documentsQuery = useAllResearchDocuments();
  const documents = documentsQuery.data?.documents ?? [];

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h4" gutterBottom>
          Research Documents
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Every uploaded research document across every issuer, in one place.
        </Typography>
      </Box>

      {documentsQuery.isLoading && (
        <Box sx={{ py: 8, textAlign: "center" }}>
          <CircularProgress />
        </Box>
      )}

      {documentsQuery.isError && <Alert severity="error">Could not load research documents.</Alert>}

      {!documentsQuery.isLoading && !documentsQuery.isError && documents.length === 0 && (
        <Alert severity="info">
          No research documents yet. Open an issuer and use "Upload Document" to add the first one.
        </Alert>
      )}

      <Stack spacing={1.5}>
        {documents.map((document) => (
          <ResearchDocumentWorkspaceCard key={document.id} document={document} />
        ))}
      </Stack>
    </Stack>
  );
}

function ResearchDocumentWorkspaceCard({
  document,
}: {
  document: ResearchDocumentSummary;
}): ReactElement {
  const downloadUrlMutation = useResearchDocumentDownloadUrl();

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

  return (
    <Card variant="outlined">
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
            to={`/issuers/${document.issuer_id}`}
            underline="hover"
            variant="subtitle2"
          >
            {document.issuer_legal_name}
          </Link>
          {document.issuer_ticker && (
            <Chip label={document.issuer_ticker} size="small" variant="outlined" />
          )}
        </Stack>

        <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
          <Typography variant="subtitle1" sx={{ mr: 1 }}>
            <RouterLink to={`/research-documents/${document.id}`}>{document.title}</RouterLink>
          </Typography>
          <ResearchDocumentTypeBadge documentType={document.document_type} />
          {document.confidentiality_classification === "restricted" && (
            <Chip label="Restricted" size="small" color="warning" variant="outlined" />
          )}
          {document.is_archived && <Chip label="Archived" size="small" variant="outlined" />}
        </Stack>

        <Typography variant="caption" color="text.secondary" component="div" sx={{ mt: 0.5 }}>
          {document.document_date && `Document date ${formatDate(document.document_date)} · `}
          uploaded {formatDateTime(document.created_at)}
          {document.uploaded_by && ` by ${document.uploaded_by}`}
        </Typography>

        <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
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
        </Stack>
      </CardContent>
    </Card>
  );
}
