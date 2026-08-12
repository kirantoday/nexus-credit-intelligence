import { type ReactElement, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router";
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Divider,
  IconButton,
  MenuItem,
  Paper,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import { ApiError } from "../api/client";
import type {
  AccessClassification,
  Conviction,
  EvidenceRef,
  ThesisStatus,
} from "../api/researchNote";
import {
  useCreateResearchNote,
  useResearchNote,
  useUpdateResearchNote,
} from "../queries/useResearchNotes";

const THESIS_STATUS_OPTIONS: { value: ThesisStatus; label: string }[] = [
  { value: "draft", label: "Draft" },
  { value: "active", label: "Active" },
  { value: "monitoring", label: "Monitoring" },
  { value: "invalidated", label: "Invalidated" },
  { value: "resolved", label: "Resolved" },
];

const CONVICTION_OPTIONS: { value: Conviction | ""; label: string }[] = [
  { value: "", label: "Not set" },
  { value: "low", label: "Low" },
  { value: "medium", label: "Medium" },
  { value: "high", label: "High" },
];

const ACCESS_CLASSIFICATION_OPTIONS: { value: AccessClassification; label: string }[] = [
  { value: "standard", label: "Standard" },
  { value: "restricted", label: "Restricted" },
];

const EVIDENCE_TABLE_OPTIONS = [
  { value: "research_evidence", label: "Research evidence" },
  { value: "sec_filing", label: "SEC filing" },
  { value: "alert_event", label: "Alert" },
  { value: "docket_document", label: "Court document" },
];

interface DraftEvidenceRef extends EvidenceRef {
  key: string;
}

interface FormState {
  title: string;
  thesisStatus: ThesisStatus;
  conviction: Conviction | "";
  bullCase: string;
  baseCase: string;
  bearCase: string;
  catalysts: string;
  risks: string;
  invalidationConditions: string;
  accessClassification: AccessClassification;
  authorUserId: string;
  evidenceRefs: DraftEvidenceRef[];
}

const EMPTY_FORM: FormState = {
  title: "",
  thesisStatus: "draft",
  conviction: "",
  bullCase: "",
  baseCase: "",
  bearCase: "",
  catalysts: "",
  risks: "",
  invalidationConditions: "",
  accessClassification: "standard",
  authorUserId: "",
  evidenceRefs: [],
};

export function ResearchNoteEditorPage(): ReactElement {
  const params = useParams<{ issuerId?: string; noteId?: string }>();
  const navigate = useNavigate();
  const isEditMode = params.noteId !== undefined;

  const existingNoteQuery = useResearchNote(isEditMode ? params.noteId : undefined);
  const createMutation = useCreateResearchNote();
  const updateMutation = useUpdateResearchNote();

  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [newEvidenceTable, setNewEvidenceTable] = useState(EVIDENCE_TABLE_OPTIONS[0]!.value);
  const [newEvidenceId, setNewEvidenceId] = useState("");
  const [newEvidenceLabel, setNewEvidenceLabel] = useState("");
  const [hydrated, setHydrated] = useState(!isEditMode);

  useEffect(() => {
    if (!isEditMode || !existingNoteQuery.data || hydrated) return;
    const note = existingNoteQuery.data;
    setForm({
      title: note.title,
      thesisStatus: note.thesis_status,
      conviction: note.conviction ?? "",
      bullCase: note.bull_case ?? "",
      baseCase: note.base_case ?? "",
      bearCase: note.bear_case ?? "",
      catalysts: note.catalysts ?? "",
      risks: note.risks ?? "",
      invalidationConditions: note.invalidation_conditions ?? "",
      accessClassification: note.access_classification,
      authorUserId: note.author_user_id ?? "",
      evidenceRefs: (note.evidence_refs ?? []).map((ref, idx) => ({ ...ref, key: `${idx}` })),
    });
    setHydrated(true);
  }, [isEditMode, existingNoteQuery.data, hydrated]);

  if (isEditMode && existingNoteQuery.isLoading) {
    return (
      <Box sx={{ py: 8, textAlign: "center" }}>
        <CircularProgress />
      </Box>
    );
  }

  if (isEditMode && (existingNoteQuery.isError || !existingNoteQuery.data)) {
    const notFound =
      existingNoteQuery.error instanceof ApiError && existingNoteQuery.error.status === 404;
    return (
      <Alert severity={notFound ? "warning" : "error"}>
        {notFound ? "This research note doesn't exist." : "Could not load this research note."}
      </Alert>
    );
  }

  if (isEditMode && existingNoteQuery.data?.is_archived) {
    return <Alert severity="warning">Archived notes are read-only and cannot be edited.</Alert>;
  }

  const issuerId = isEditMode ? existingNoteQuery.data!.issuer_id : params.issuerId!;
  const mutation = isEditMode ? updateMutation : createMutation;

  function addEvidenceRef(): void {
    if (!newEvidenceId.trim()) return;
    setForm((f) => ({
      ...f,
      evidenceRefs: [
        ...f.evidenceRefs,
        {
          key: crypto.randomUUID(),
          entity_table: newEvidenceTable,
          entity_id: newEvidenceId.trim(),
          label: newEvidenceLabel.trim() || null,
        },
      ],
    }));
    setNewEvidenceId("");
    setNewEvidenceLabel("");
  }

  function removeEvidenceRef(key: string): void {
    setForm((f) => ({ ...f, evidenceRefs: f.evidenceRefs.filter((r) => r.key !== key) }));
  }

  function handleSubmit(): void {
    const fields = {
      title: form.title.trim(),
      thesis_status: form.thesisStatus,
      conviction: form.conviction === "" ? null : form.conviction,
      bull_case: form.bullCase.trim() || null,
      base_case: form.baseCase.trim() || null,
      bear_case: form.bearCase.trim() || null,
      catalysts: form.catalysts.trim() || null,
      risks: form.risks.trim() || null,
      invalidation_conditions: form.invalidationConditions.trim() || null,
      access_classification: form.accessClassification,
      evidence_refs: form.evidenceRefs.map((ref): EvidenceRef => ({
        entity_table: ref.entity_table,
        entity_id: ref.entity_id,
        label: ref.label,
      })),
    };

    if (isEditMode) {
      updateMutation.mutate(
        { noteId: params.noteId!, ...fields, edited_by: form.authorUserId.trim() || null },
        { onSuccess: (note) => navigate(`/research-notes/${note.id}`) },
      );
    } else {
      createMutation.mutate(
        {
          issuer_id: issuerId,
          author_user_id: form.authorUserId.trim() || null,
          is_demo: false,
          ...fields,
        },
        { onSuccess: (note) => navigate(`/research-notes/${note.id}`) },
      );
    }
  }

  return (
    <Stack spacing={3} sx={{ maxWidth: 820, mx: "auto" }}>
      <Typography variant="h4">
        {isEditMode ? "Edit Research Note" : "Write Research Note"}
      </Typography>

      <Paper variant="outlined" sx={{ p: 2 }}>
        <Stack spacing={2.5}>
          <TextField
            label="Title"
            value={form.title}
            onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
            required
            fullWidth
          />

          <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
            <TextField
              select
              label="Thesis Status"
              value={form.thesisStatus}
              onChange={(e) =>
                setForm((f) => ({ ...f, thesisStatus: e.target.value as ThesisStatus }))
              }
              fullWidth
            >
              {THESIS_STATUS_OPTIONS.map((opt) => (
                <MenuItem key={opt.value} value={opt.value}>
                  {opt.label}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              select
              label="Conviction"
              value={form.conviction}
              onChange={(e) =>
                setForm((f) => ({ ...f, conviction: e.target.value as Conviction | "" }))
              }
              fullWidth
            >
              {CONVICTION_OPTIONS.map((opt) => (
                <MenuItem key={opt.value || "none"} value={opt.value}>
                  {opt.label}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              select
              label="Access Classification"
              value={form.accessClassification}
              onChange={(e) =>
                setForm((f) => ({
                  ...f,
                  accessClassification: e.target.value as AccessClassification,
                }))
              }
              fullWidth
            >
              {ACCESS_CLASSIFICATION_OPTIONS.map((opt) => (
                <MenuItem key={opt.value} value={opt.value}>
                  {opt.label}
                </MenuItem>
              ))}
            </TextField>
          </Stack>

          <TextField
            label="Your name (optional)"
            helperText="Attributed to this note's audit trail — Nexus doesn't require sign-in yet."
            value={form.authorUserId}
            onChange={(e) => setForm((f) => ({ ...f, authorUserId: e.target.value }))}
            fullWidth
          />

          <Divider />

          <TextField
            label="Base Case"
            value={form.baseCase}
            onChange={(e) => setForm((f) => ({ ...f, baseCase: e.target.value }))}
            multiline
            minRows={2}
            fullWidth
          />
          <TextField
            label="Bull Case"
            value={form.bullCase}
            onChange={(e) => setForm((f) => ({ ...f, bullCase: e.target.value }))}
            multiline
            minRows={2}
            fullWidth
          />
          <TextField
            label="Bear Case"
            value={form.bearCase}
            onChange={(e) => setForm((f) => ({ ...f, bearCase: e.target.value }))}
            multiline
            minRows={2}
            fullWidth
          />
          <TextField
            label="Catalysts"
            value={form.catalysts}
            onChange={(e) => setForm((f) => ({ ...f, catalysts: e.target.value }))}
            multiline
            minRows={2}
            fullWidth
          />
          <TextField
            label="Key Risks"
            value={form.risks}
            onChange={(e) => setForm((f) => ({ ...f, risks: e.target.value }))}
            multiline
            minRows={2}
            fullWidth
          />
          <TextField
            label="Invalidation Conditions"
            helperText="What would prove this thesis wrong?"
            value={form.invalidationConditions}
            onChange={(e) => setForm((f) => ({ ...f, invalidationConditions: e.target.value }))}
            multiline
            minRows={2}
            fullWidth
          />

          <Divider />

          <Box>
            <Typography variant="subtitle2" gutterBottom>
              Sources / Evidence
            </Typography>
            <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1 }}>
              Reference an existing Nexus record by ID — the note points at it, it never copies its
              content.
            </Typography>
            <Stack spacing={1}>
              {form.evidenceRefs.map((ref) => (
                <Stack key={ref.key} direction="row" spacing={1} alignItems="center">
                  <Typography variant="body2" sx={{ flexGrow: 1 }}>
                    {ref.label ? `${ref.label} — ` : ""}
                    {ref.entity_table} · {ref.entity_id}
                  </Typography>
                  <IconButton
                    size="small"
                    onClick={() => removeEvidenceRef(ref.key)}
                    aria-label="Remove evidence reference"
                  >
                    <DeleteOutlineIcon fontSize="small" />
                  </IconButton>
                </Stack>
              ))}
              <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
                <TextField
                  select
                  size="small"
                  label="Type"
                  value={newEvidenceTable}
                  onChange={(e) => setNewEvidenceTable(e.target.value)}
                  sx={{ minWidth: 180 }}
                >
                  {EVIDENCE_TABLE_OPTIONS.map((opt) => (
                    <MenuItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </MenuItem>
                  ))}
                </TextField>
                <TextField
                  size="small"
                  label="Record ID"
                  value={newEvidenceId}
                  onChange={(e) => setNewEvidenceId(e.target.value)}
                  fullWidth
                />
                <TextField
                  size="small"
                  label="Label (optional)"
                  value={newEvidenceLabel}
                  onChange={(e) => setNewEvidenceLabel(e.target.value)}
                  fullWidth
                />
                <Button
                  variant="outlined"
                  size="small"
                  onClick={addEvidenceRef}
                  disabled={!newEvidenceId.trim()}
                >
                  Add
                </Button>
              </Stack>
            </Stack>
          </Box>

          {mutation.isError && (
            <Alert severity="error">
              Could not save this research note.{" "}
              {mutation.error instanceof Error ? mutation.error.message : ""}
            </Alert>
          )}

          <Stack direction="row" spacing={1} justifyContent="flex-end">
            <Button
              onClick={() =>
                navigate(isEditMode ? `/research-notes/${params.noteId}` : `/issuers/${issuerId}`)
              }
            >
              Cancel
            </Button>
            <Button
              variant="contained"
              onClick={handleSubmit}
              disabled={!form.title.trim() || mutation.isPending}
            >
              {isEditMode ? "Save Changes" : "Create Research Note"}
            </Button>
          </Stack>
        </Stack>
      </Paper>
    </Stack>
  );
}
