import type { ReactElement } from "react";
import { Link as RouterLink, useParams } from "react-router";
import {
  Alert,
  Box,
  Chip,
  CircularProgress,
  Divider,
  Paper,
  Stack,
  Typography,
} from "@mui/material";
import { ResearchDocumentTypeBadge } from "../components/ResearchDocumentTypeBadge";
import { DocumentIntelligencePanel } from "../components/DocumentIntelligencePanel";
import { useResearchDocument } from "../queries/useResearchDocuments";
import { formatDate, formatDateTime } from "../lib/format";

/**
 * A single Research Document's detail view (Milestone 10C) — the new home
 * for Document Intelligence (Process/status/metrics/Inspect Chunks), since
 * neither `ResearchDocumentsSection` nor `ResearchDocumentsWorkspacePage`
 * had a per-document page before this milestone; both link here now.
 */
export function ResearchDocumentDetailPage(): ReactElement {
  const { documentId } = useParams<{ documentId: string }>();
  const documentQuery = useResearchDocument(documentId);

  if (documentQuery.isLoading) {
    return (
      <Box sx={{ py: 4, textAlign: "center" }}>
        <CircularProgress />
      </Box>
    );
  }

  if (documentQuery.isError || !documentQuery.data) {
    return <Alert severity="error">Could not load this research document.</Alert>;
  }

  const document = documentQuery.data;

  return (
    <Stack spacing={3} sx={{ maxWidth: 820, mx: "auto" }}>
      <Box>
        <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
          <Typography variant="h4" sx={{ mr: 1 }}>
            {document.title}
          </Typography>
          <ResearchDocumentTypeBadge documentType={document.document_type} />
          {document.confidentiality_classification === "restricted" && (
            <Chip label="Restricted" size="small" color="warning" variant="outlined" />
          )}
          {document.is_archived && <Chip label="Archived" size="small" variant="outlined" />}
        </Stack>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
          <RouterLink to={`/issuers/${document.issuer_id}`}>View issuer</RouterLink>
        </Typography>
        {document.description && (
          <Typography variant="body2" sx={{ mt: 1 }}>
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
      </Box>

      <Divider />

      <Paper variant="outlined" sx={{ p: 2 }}>
        <DocumentIntelligencePanel documentId={document.id} />
      </Paper>
    </Stack>
  );
}
