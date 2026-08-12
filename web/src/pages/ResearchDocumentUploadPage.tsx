import { type ChangeEvent, type ReactElement, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { Alert, Box, Button, MenuItem, Paper, Stack, TextField, Typography } from "@mui/material";
import UploadFileOutlinedIcon from "@mui/icons-material/UploadFileOutlined";
import type {
  AccessClassification,
  OriginalSource,
  ResearchDocumentType,
} from "../api/researchDocument";
import { useUploadResearchDocument } from "../queries/useResearchDocuments";

const DOCUMENT_TYPE_OPTIONS: { value: ResearchDocumentType; label: string }[] = [
  { value: "credit_agreement", label: "Credit Agreement" },
  { value: "amendment", label: "Amendment" },
  { value: "earnings_presentation", label: "Earnings Presentation" },
  { value: "investor_presentation", label: "Investor Presentation" },
  { value: "restructuring_presentation", label: "Restructuring Presentation" },
  { value: "lender_presentation", label: "Lender Presentation" },
  { value: "bankruptcy_court_document", label: "Bankruptcy/Court Document" },
  { value: "financial_model_analysis", label: "Financial Model/Analysis" },
  { value: "internal_research_memo", label: "Internal Research Memo" },
  { value: "other", label: "Other" },
];

const CONFIDENTIALITY_OPTIONS: { value: AccessClassification; label: string }[] = [
  { value: "standard", label: "Standard" },
  { value: "restricted", label: "Restricted" },
];

const ORIGINAL_SOURCE_OPTIONS: { value: OriginalSource; label: string }[] = [
  { value: "issuer_site", label: "Issuer's website / investor relations" },
  { value: "courtlistener", label: "CourtListener / RECAP" },
  { value: "pacer", label: "PACER" },
  { value: "other", label: "Other" },
];

// Client-side UX hint only — the 25 MB / PDF-signature limits are enforced
// server-side and are the real security boundary (approved architecture,
// item 3).
const MAX_UPLOAD_SIZE_BYTES = 25 * 1024 * 1024;

interface FormState {
  file: File | null;
  documentType: ResearchDocumentType;
  title: string;
  description: string;
  documentDate: string;
  confidentialityClassification: AccessClassification;
  uploadedBy: string;
  originalSource: OriginalSource;
}

const EMPTY_FORM: FormState = {
  file: null,
  documentType: "credit_agreement",
  title: "",
  description: "",
  documentDate: "",
  confidentialityClassification: "standard",
  uploadedBy: "",
  originalSource: "other",
};

export function ResearchDocumentUploadPage(): ReactElement {
  const { issuerId } = useParams<{ issuerId: string }>();
  const navigate = useNavigate();
  const uploadMutation = useUploadResearchDocument();

  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [fileError, setFileError] = useState<string | null>(null);

  function handleFileChange(event: ChangeEvent<HTMLInputElement>): void {
    const file = event.target.files?.[0] ?? null;
    if (!file) {
      setForm((f) => ({ ...f, file: null }));
      return;
    }
    if (file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")) {
      setFileError("Only PDF files are supported.");
      setForm((f) => ({ ...f, file: null }));
      return;
    }
    if (file.size > MAX_UPLOAD_SIZE_BYTES) {
      setFileError("File exceeds the 25 MB upload limit.");
      setForm((f) => ({ ...f, file: null }));
      return;
    }
    setFileError(null);
    setForm((f) => ({ ...f, file, title: f.title || file.name.replace(/\.pdf$/i, "") }));
  }

  function handleSubmit(): void {
    if (!issuerId || !form.file) return;
    uploadMutation.mutate(
      {
        issuer_id: issuerId,
        document_type: form.documentType,
        title: form.title.trim(),
        description: form.description.trim() || null,
        document_date: form.documentDate || null,
        confidentiality_classification: form.confidentialityClassification,
        uploaded_by: form.uploadedBy.trim() || null,
        original_source: form.originalSource,
        file: form.file,
      },
      { onSuccess: () => navigate(`/issuers/${issuerId}`) },
    );
  }

  return (
    <Stack spacing={3} sx={{ maxWidth: 820, mx: "auto" }}>
      <Typography variant="h4">Upload Research Document</Typography>

      <Paper variant="outlined" sx={{ p: 2 }}>
        <Stack spacing={2.5}>
          <Box>
            <Button component="label" variant="outlined" startIcon={<UploadFileOutlinedIcon />}>
              {form.file ? form.file.name : "Choose PDF file"}
              <input type="file" accept="application/pdf,.pdf" hidden onChange={handleFileChange} />
            </Button>
            <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 0.5 }}>
              PDF only, up to 25 MB.
            </Typography>
            {fileError && (
              <Alert severity="error" sx={{ mt: 1 }}>
                {fileError}
              </Alert>
            )}
          </Box>

          <TextField
            label="Title"
            value={form.title}
            onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
            required
            fullWidth
          />

          <TextField
            label="Description (optional)"
            value={form.description}
            onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
            multiline
            minRows={2}
            fullWidth
          />

          <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
            <TextField
              select
              label="Document Type"
              value={form.documentType}
              onChange={(e) =>
                setForm((f) => ({ ...f, documentType: e.target.value as ResearchDocumentType }))
              }
              fullWidth
            >
              {DOCUMENT_TYPE_OPTIONS.map((opt) => (
                <MenuItem key={opt.value} value={opt.value}>
                  {opt.label}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              label="Document Date (optional)"
              type="date"
              value={form.documentDate}
              onChange={(e) => setForm((f) => ({ ...f, documentDate: e.target.value }))}
              InputLabelProps={{ shrink: true }}
              fullWidth
            />
            <TextField
              select
              label="Confidentiality"
              value={form.confidentialityClassification}
              onChange={(e) =>
                setForm((f) => ({
                  ...f,
                  confidentialityClassification: e.target.value as AccessClassification,
                }))
              }
              fullWidth
            >
              {CONFIDENTIALITY_OPTIONS.map((opt) => (
                <MenuItem key={opt.value} value={opt.value}>
                  {opt.label}
                </MenuItem>
              ))}
            </TextField>
          </Stack>

          <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
            <TextField
              select
              label="Where did this document come from?"
              value={form.originalSource}
              onChange={(e) =>
                setForm((f) => ({ ...f, originalSource: e.target.value as OriginalSource }))
              }
              fullWidth
            >
              {ORIGINAL_SOURCE_OPTIONS.map((opt) => (
                <MenuItem key={opt.value} value={opt.value}>
                  {opt.label}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              label="Your name (optional)"
              helperText="Attributed to this document's provenance and audit trail."
              value={form.uploadedBy}
              onChange={(e) => setForm((f) => ({ ...f, uploadedBy: e.target.value }))}
              fullWidth
            />
          </Stack>

          {uploadMutation.isError && (
            <Alert severity="error">
              Could not upload this document.{" "}
              {uploadMutation.error instanceof Error ? uploadMutation.error.message : ""}
            </Alert>
          )}

          <Stack direction="row" spacing={1} justifyContent="flex-end">
            <Button onClick={() => navigate(`/issuers/${issuerId}`)}>Cancel</Button>
            <Button
              variant="contained"
              onClick={handleSubmit}
              disabled={!form.file || !form.title.trim() || uploadMutation.isPending}
            >
              {uploadMutation.isPending ? "Uploading…" : "Upload Document"}
            </Button>
          </Stack>
        </Stack>
      </Paper>
    </Stack>
  );
}
