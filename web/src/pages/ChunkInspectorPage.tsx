import { type ChangeEvent, type ReactElement, useState } from "react";
import { useParams } from "react-router";
import {
  Alert,
  Box,
  Chip,
  CircularProgress,
  Divider,
  Paper,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import SearchOutlinedIcon from "@mui/icons-material/SearchOutlined";
import type { DocumentChunk } from "../api/documentExtraction";
import { useChunkSearch, useChunks, useExtraction } from "../queries/useDocumentExtraction";

const ELEMENT_TYPE_LABEL: Record<DocumentChunk["element_type"], string> = {
  text: "Text",
  heading: "Heading",
  table: "Table",
  list: "List",
};

/**
 * Chunk Inspector (Milestone 10C section 16) — an analyst/developer
 * inspection view for `chunking_v1`'s output, deliberately not an
 * end-user conversational RAG interface. Lexical search
 * (`search_document_chunks`) is internal to this page only, never
 * Universal Search.
 */
export function ChunkInspectorPage(): ReactElement {
  const { extractionId } = useParams<{ extractionId: string }>();
  const [query, setQuery] = useState("");

  const extractionQuery = useExtraction(extractionId);
  const chunksQuery = useChunks(extractionId);
  const searchQuery = useChunkSearch(extractionId, query);

  const isSearching = query.trim().length > 0;
  const chunks = isSearching ? (searchQuery.data?.chunks ?? []) : (chunksQuery.data?.chunks ?? []);
  const loading = isSearching ? searchQuery.isLoading : chunksQuery.isLoading;

  function handleQueryChange(event: ChangeEvent<HTMLInputElement>): void {
    setQuery(event.target.value);
  }

  return (
    <Stack spacing={3} sx={{ maxWidth: 960, mx: "auto" }}>
      <Typography variant="h4">Document Intelligence</Typography>

      {extractionQuery.data && (
        <Paper variant="outlined" sx={{ p: 2 }}>
          <Typography variant="subtitle1">Extraction</Typography>
          <Typography variant="body2" color="text.secondary">
            {extractionQuery.data.extractor_provider}/{extractionQuery.data.extractor_version}
          </Typography>
          <Stack direction="row" spacing={3} sx={{ mt: 1 }}>
            <Typography variant="body2">{extractionQuery.data.page_count ?? "—"} pages</Typography>
            <Typography variant="body2">
              {extractionQuery.data.chunk_count ?? "—"} chunks
            </Typography>
            <Typography variant="body2">
              {extractionQuery.data.table_count ?? "—"} tables
            </Typography>
          </Stack>
        </Paper>
      )}

      <TextField
        label="Search chunks"
        placeholder="e.g. covenant, restricted payments"
        value={query}
        onChange={handleQueryChange}
        fullWidth
        size="small"
        InputProps={{ startAdornment: <SearchOutlinedIcon fontSize="small" sx={{ mr: 1 }} /> }}
      />

      {loading && (
        <Box sx={{ py: 4, textAlign: "center" }}>
          <CircularProgress />
        </Box>
      )}

      {!loading && chunksQuery.isError && (
        <Alert severity="error">Could not load chunks for this extraction.</Alert>
      )}

      {!loading && isSearching && chunks.length === 0 && (
        <Typography variant="body2" color="text.secondary">
          No chunks match "{query}".
        </Typography>
      )}

      {!loading && !isSearching && chunks.length === 0 && !chunksQuery.isError && (
        <Typography variant="body2" color="text.secondary">
          This extraction has no chunks yet.
        </Typography>
      )}

      <Stack spacing={2}>
        {chunks.map((chunk) => (
          <ChunkCard key={chunk.id} chunk={chunk} />
        ))}
      </Stack>
    </Stack>
  );
}

function ChunkCard({ chunk }: { chunk: DocumentChunk }): ReactElement {
  const pages =
    chunk.page_start === null
      ? null
      : chunk.page_start === chunk.page_end
        ? `Page ${chunk.page_start}`
        : `Pages ${chunk.page_start}–${chunk.page_end}`;

  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
        <Typography variant="caption" color="text.secondary">
          Chunk {chunk.chunk_index}
        </Typography>
        <Chip label={ELEMENT_TYPE_LABEL[chunk.element_type]} size="small" variant="outlined" />
        {pages && (
          <Typography variant="caption" color="text.secondary">
            {pages}
          </Typography>
        )}
        {chunk.confidentiality_classification === "restricted" && (
          <Chip label="Restricted" size="small" color="warning" variant="outlined" />
        )}
      </Stack>

      {chunk.section_path && (
        <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 0.5 }}>
          {chunk.section_path}
        </Typography>
      )}

      <Divider sx={{ my: 1 }} />

      <Box
        component={chunk.element_type === "table" ? "pre" : "div"}
        sx={{
          whiteSpace: "pre-wrap",
          fontFamily: chunk.element_type === "table" ? "monospace" : "inherit",
          fontSize: chunk.element_type === "table" ? "0.8rem" : "0.875rem",
          m: 0,
        }}
      >
        {chunk.content}
      </Box>
    </Paper>
  );
}
