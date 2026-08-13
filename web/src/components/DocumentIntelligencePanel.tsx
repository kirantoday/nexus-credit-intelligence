import { type ReactElement } from "react";
import { Link as RouterLink } from "react-router";
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Divider,
  Stack,
  Typography,
} from "@mui/material";
import PlayArrowOutlinedIcon from "@mui/icons-material/PlayArrowOutlined";
import RefreshOutlinedIcon from "@mui/icons-material/RefreshOutlined";
import ManageSearchOutlinedIcon from "@mui/icons-material/ManageSearchOutlined";
import type { DocumentExtraction } from "../api/documentExtraction";
import { formatDateTime } from "../lib/format";
import {
  useCurrentExtraction,
  useExtractionHistory,
  useProcessDocument,
} from "../queries/useDocumentExtraction";

const STATUS_LABEL: Record<DocumentExtraction["status"], string> = {
  pending: "Pending",
  processing: "Processing",
  completed: "Processed",
  failed: "Failed",
  needs_ocr: "Needs OCR",
};

const STATUS_COLOR: Record<
  DocumentExtraction["status"],
  "default" | "warning" | "success" | "error" | "info"
> = {
  pending: "default",
  processing: "info",
  completed: "success",
  failed: "error",
  needs_ocr: "warning",
};

/**
 * Document Intelligence — extraction/chunking status and controls for one
 * Research Document (Milestone 10C). Embedded on `ResearchDocumentDetailPage`,
 * mirroring `ResearchDocumentsSection`'s established card shape rather than
 * introducing a new visual language.
 */
export function DocumentIntelligencePanel({ documentId }: { documentId: string }): ReactElement {
  const currentQuery = useCurrentExtraction(documentId);
  const historyQuery = useExtractionHistory(documentId);
  const processMutation = useProcessDocument();

  const current = currentQuery.data ?? null;
  const history = historyQuery.data?.extractions ?? [];
  const latest = history[0] ?? null;
  // The most recently *attempted* extraction, which may differ from the
  // current one (e.g. a reprocess still pending/processing/failed) —
  // that's the one whose live status this panel should reflect.
  const active = latest ?? current;

  const hasInFlight = active?.status === "pending" || active?.status === "processing";

  function handleProcess(): void {
    processMutation.mutate({ documentId });
  }

  return (
    <Box>
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1.5 }}>
        <Typography variant="h6">Document Intelligence</Typography>
        {!hasInFlight && (
          <Button
            size="small"
            variant="contained"
            startIcon={active ? <RefreshOutlinedIcon /> : <PlayArrowOutlinedIcon />}
            onClick={handleProcess}
            disabled={processMutation.isPending}
          >
            {active ? "Reprocess" : "Process Document"}
          </Button>
        )}
      </Stack>

      {(currentQuery.isLoading || historyQuery.isLoading) && (
        <Box sx={{ py: 2, textAlign: "center" }}>
          <CircularProgress size={24} />
        </Box>
      )}

      {processMutation.isError && (
        <Alert severity="error" sx={{ mb: 1.5 }}>
          Could not start processing. Please try again.
        </Alert>
      )}

      {!currentQuery.isLoading && !historyQuery.isLoading && !active && (
        <Stack spacing={1} alignItems="flex-start">
          <Typography variant="body2" color="text.secondary">
            Status: Not processed
          </Typography>
        </Stack>
      )}

      {active && (
        <Stack spacing={1.5}>
          <Stack direction="row" spacing={1} alignItems="center">
            <Typography variant="body2">Status:</Typography>
            <Chip
              label={STATUS_LABEL[active.status]}
              color={STATUS_COLOR[active.status]}
              size="small"
            />
            {hasInFlight && <CircularProgress size={14} />}
          </Stack>

          {active.status === "needs_ocr" && (
            <Alert severity="warning">
              Nexus detected that this document appears to require OCR. OCR processing is not
              enabled yet.
            </Alert>
          )}

          {active.status === "failed" && (
            <Alert severity="error">
              Extraction failed
              {active.error_classification ? ` (${active.error_classification})` : ""}. The
              previously processed version, if any, remains available below.
            </Alert>
          )}

          {active.status === "pending" && active.started_at === null && (
            <Typography variant="caption" color="text.secondary">
              Queued — the extraction worker checks for new work every few minutes.
            </Typography>
          )}
          {active.status === "processing" && active.started_at && (
            <Typography variant="caption" color="text.secondary">
              Started {formatDateTime(active.started_at)}
            </Typography>
          )}

          {current && current.status === "completed" && (
            <Box>
              <Divider sx={{ my: 1 }} />
              <Stack direction="row" spacing={3} flexWrap="wrap" useFlexGap>
                <Metric label="Pages" value={current.page_count} />
                <Metric label="Chunks" value={current.chunk_count} />
                <Metric label="Tables" value={current.table_count} />
              </Stack>
              <Typography variant="caption" color="text.secondary" component="div" sx={{ mt: 0.5 }}>
                {current.extractor_provider}/{current.extractor_version} · chunking{" "}
                {current.chunking_strategy_version}
                {current.completed_at && ` · processed ${formatDateTime(current.completed_at)}`}
              </Typography>
              <Button
                size="small"
                startIcon={<ManageSearchOutlinedIcon />}
                component={RouterLink}
                to={`/document-extractions/${current.id}/chunks`}
                sx={{ mt: 1 }}
              >
                Inspect Chunks
              </Button>
            </Box>
          )}

          {history.length > 1 && (
            <Box>
              <Divider sx={{ my: 1 }} />
              <Typography variant="caption" color="text.secondary" component="div" sx={{ mb: 0.5 }}>
                Extraction history
              </Typography>
              <Stack spacing={0.5}>
                {history.map((extraction) => (
                  <Stack key={extraction.id} direction="row" spacing={1} alignItems="center">
                    <Chip
                      label={STATUS_LABEL[extraction.status]}
                      color={STATUS_COLOR[extraction.status]}
                      size="small"
                      variant={extraction.is_current ? "filled" : "outlined"}
                    />
                    <Typography variant="caption" color="text.secondary">
                      {formatDateTime(extraction.created_at)}
                      {extraction.is_current && " · current"}
                    </Typography>
                  </Stack>
                ))}
              </Stack>
            </Box>
          )}
        </Stack>
      )}
    </Box>
  );
}

function Metric({ label, value }: { label: string; value: number | null }): ReactElement {
  return (
    <Box>
      <Typography variant="h6" component="div">
        {value ?? "—"}
      </Typography>
      <Typography variant="caption" color="text.secondary">
        {label}
      </Typography>
    </Box>
  );
}
