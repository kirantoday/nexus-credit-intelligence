import { type ReactElement, useMemo, useState } from "react";
import { Link as RouterLink, useNavigate, useParams } from "react-router";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Divider,
  IconButton,
  Link,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import EditOutlinedIcon from "@mui/icons-material/EditOutlined";
import NotificationsNoneOutlinedIcon from "@mui/icons-material/NotificationsNoneOutlined";
import type { ColumnDef } from "@tanstack/react-table";
import { ApiError } from "../api/client";
import type { WatchlistIssuerRow } from "../api/watchlist";
import { DataTable } from "../components/DataTable";
import { SeverityBadge } from "../components/SeverityBadge";
import {
  useDeleteWatchlist,
  useRemoveIssuerFromWatchlist,
  useUpdateWatchlist,
  useWatchlist,
} from "../queries/useWatchlists";
import { formatDate } from "../lib/format";

function RenameWatchlistDialog({
  open,
  onClose,
  watchlistId,
  currentName,
  currentDescription,
}: {
  open: boolean;
  onClose: () => void;
  watchlistId: string;
  currentName: string;
  currentDescription: string;
}): ReactElement {
  const [name, setName] = useState(currentName);
  const [description, setDescription] = useState(currentDescription);
  const updateWatchlist = useUpdateWatchlist();

  function handleClose(): void {
    updateWatchlist.reset();
    onClose();
  }

  function handleSave(): void {
    const trimmed = name.trim();
    if (!trimmed) return;
    updateWatchlist.mutate(
      { watchlistId, name: trimmed, description: description.trim() },
      { onSuccess: () => handleClose() },
    );
  }

  return (
    <Dialog open={open} onClose={handleClose} fullWidth maxWidth="xs">
      <DialogTitle>Rename Watchlist</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          <TextField
            label="Name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            autoFocus
            fullWidth
          />
          <TextField
            label="Description"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            multiline
            minRows={2}
            fullWidth
          />
          {updateWatchlist.isError && (
            <Alert severity="error">Could not save changes. Please try again.</Alert>
          )}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose}>Cancel</Button>
        <Button
          variant="contained"
          disabled={!name.trim() || updateWatchlist.isPending}
          onClick={handleSave}
        >
          Save
        </Button>
      </DialogActions>
    </Dialog>
  );
}

function DeleteWatchlistDialog({
  open,
  onClose,
  watchlistId,
  watchlistName,
}: {
  open: boolean;
  onClose: () => void;
  watchlistId: string;
  watchlistName: string;
}): ReactElement {
  const navigate = useNavigate();
  const deleteWatchlist = useDeleteWatchlist();

  function handleDelete(): void {
    deleteWatchlist.mutate(watchlistId, {
      onSuccess: () => navigate("/watchlists"),
    });
  }

  return (
    <Dialog open={open} onClose={onClose}>
      <DialogTitle>Delete "{watchlistName}"?</DialogTitle>
      <DialogContent>
        <DialogContentText>
          This removes the Watchlist and its tracking list only. The issuers themselves, their
          evidence, alerts, and Distress Timelines are never affected.
        </DialogContentText>
        {deleteWatchlist.isError && (
          <Alert severity="error" sx={{ mt: 2 }}>
            Could not delete this Watchlist. Please try again.
          </Alert>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button color="error" disabled={deleteWatchlist.isPending} onClick={handleDelete}>
          Delete
        </Button>
      </DialogActions>
    </Dialog>
  );
}

function RemoveIssuerButton({
  watchlistId,
  issuerId,
}: {
  watchlistId: string;
  issuerId: string;
}): ReactElement {
  const removeIssuer = useRemoveIssuerFromWatchlist();
  return (
    <Tooltip title="Remove from Watchlist">
      <IconButton
        size="small"
        aria-label="Remove from Watchlist"
        onClick={(event) => {
          event.stopPropagation();
          removeIssuer.mutate({ watchlistId, issuerId });
        }}
      >
        <DeleteOutlineIcon fontSize="small" />
      </IconButton>
    </Tooltip>
  );
}

function MobileIssuerCard({
  row,
  watchlistId,
}: {
  row: WatchlistIssuerRow;
  watchlistId: string;
}): ReactElement {
  return (
    <Card variant="outlined">
      <CardContent sx={{ p: 1.5, "&:last-child": { pb: 1.5 } }}>
        <Stack direction="row" justifyContent="space-between" alignItems="flex-start">
          <Link component={RouterLink} to={`/issuers/${row.issuer_id}`} underline="hover">
            <Typography variant="body2" fontWeight={600}>
              {row.issuer_legal_name}
            </Typography>
          </Link>
          <RemoveIssuerButton watchlistId={watchlistId} issuerId={row.issuer_id} />
        </Stack>
        {row.current_status.length > 0 && (
          <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap sx={{ mt: 0.5 }}>
            {row.current_status.map((status) => (
              <Chip key={status} label={status} size="small" variant="outlined" />
            ))}
          </Stack>
        )}
        <Divider sx={{ my: 1 }} />
        {row.latest_development_headline ? (
          <Stack spacing={0.5}>
            <Stack direction="row" spacing={1} alignItems="center">
              {row.severity && <SeverityBadge severity={row.severity} />}
              <Typography variant="body2">{row.latest_development_headline}</Typography>
            </Stack>
            <Typography variant="caption" color="text.secondary">
              {formatDate(row.latest_development_date)}
              {row.new_developments_count > 0 && ` · ${row.new_developments_count} new this cycle`}
            </Typography>
          </Stack>
        ) : (
          <Typography variant="body2" color="text.secondary">
            No developments on file yet.
          </Typography>
        )}
        <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>
          {row.securities_count} securit{row.securities_count === 1 ? "y" : "ies"} on file
        </Typography>
      </CardContent>
    </Card>
  );
}

export function WatchlistDetailPage(): ReactElement {
  const { watchlistId } = useParams<{ watchlistId: string }>();
  const watchlistQuery = useWatchlist(watchlistId);
  const [renameOpen, setRenameOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);

  const columns = useMemo<ColumnDef<WatchlistIssuerRow, unknown>[]>(
    () => [
      {
        id: "issuer",
        header: "Issuer",
        accessorFn: (row) => row.issuer_legal_name,
        cell: ({ row }) => (
          <Link component={RouterLink} to={`/issuers/${row.original.issuer_id}`} underline="hover">
            {row.original.issuer_legal_name}
          </Link>
        ),
      },
      {
        id: "current_status",
        header: "Current status",
        accessorFn: (row) => row.current_status.join(", "),
        cell: ({ row }) => (
          <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
            {row.original.current_status.length === 0 ? (
              <Typography variant="caption" color="text.secondary">
                —
              </Typography>
            ) : (
              row.original.current_status.map((status) => (
                <Chip key={status} label={status} size="small" variant="outlined" />
              ))
            )}
          </Stack>
        ),
      },
      {
        id: "latest_development",
        header: "Latest development",
        accessorFn: (row) => row.latest_development_headline ?? "",
        cell: ({ row }) =>
          row.original.latest_development_headline ?? (
            <Typography variant="caption" color="text.secondary">
              No developments on file yet.
            </Typography>
          ),
      },
      {
        id: "severity",
        header: "Severity",
        accessorFn: (row) => row.severity ?? "",
        cell: ({ row }) =>
          row.original.severity ? <SeverityBadge severity={row.original.severity} /> : "—",
      },
      {
        id: "development_date",
        header: "Development date",
        accessorFn: (row) => row.latest_development_date ?? "",
        cell: ({ row }) => formatDate(row.original.latest_development_date),
      },
      {
        id: "new_developments",
        header: "New developments",
        accessorFn: (row) => row.new_developments_count,
        cell: ({ row }) =>
          row.original.new_developments_count > 0 ? (
            <Chip label={row.original.new_developments_count} size="small" color="warning" />
          ) : (
            "0"
          ),
      },
      {
        id: "securities",
        header: "Securities",
        accessorFn: (row) => row.securities_count,
      },
      {
        id: "actions",
        header: "",
        enableSorting: false,
        cell: ({ row }) => (
          <RemoveIssuerButton
            watchlistId={watchlistId as string}
            issuerId={row.original.issuer_id}
          />
        ),
      },
    ],
    [watchlistId],
  );

  if (watchlistQuery.isLoading) {
    return (
      <Box sx={{ py: 8, textAlign: "center" }}>
        <CircularProgress />
      </Box>
    );
  }

  if (watchlistQuery.isError) {
    const notFound =
      watchlistQuery.error instanceof ApiError && watchlistQuery.error.status === 404;
    return (
      <Alert severity={notFound ? "warning" : "error"}>
        {notFound
          ? "This Watchlist doesn't exist."
          : `Could not load this Watchlist: ${watchlistQuery.error instanceof Error ? watchlistQuery.error.message : "unknown error"}`}
      </Alert>
    );
  }

  const detail = watchlistQuery.data;
  if (!detail) {
    return <Alert severity="warning">This Watchlist doesn't exist.</Alert>;
  }

  const { watchlist, issuers } = detail;

  return (
    <Stack spacing={3}>
      <Box>
        <Stack
          direction="row"
          justifyContent="space-between"
          alignItems="flex-start"
          flexWrap="wrap"
          spacing={1}
        >
          <Box>
            <Typography variant="h4">{watchlist.name}</Typography>
            {watchlist.description && (
              <Typography variant="body1" color="text.secondary" sx={{ mt: 0.5 }}>
                {watchlist.description}
              </Typography>
            )}
          </Box>
          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
            <Button
              size="small"
              component={RouterLink}
              to={`/alerts?watchlist=${watchlist.id}`}
              startIcon={<NotificationsNoneOutlinedIcon />}
              variant="outlined"
            >
              View Alerts
            </Button>
            <Button
              size="small"
              startIcon={<EditOutlinedIcon />}
              onClick={() => setRenameOpen(true)}
            >
              Rename
            </Button>
            <Button
              size="small"
              color="error"
              startIcon={<DeleteOutlineIcon />}
              onClick={() => setDeleteOpen(true)}
            >
              Delete
            </Button>
          </Stack>
        </Stack>
        <Stack direction="row" spacing={3} sx={{ mt: 2 }} flexWrap="wrap" useFlexGap>
          <Box>
            <Typography variant="h5" fontWeight={700} lineHeight={1.1}>
              {watchlist.issuer_count}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              issuer{watchlist.issuer_count === 1 ? "" : "s"}
            </Typography>
          </Box>
          <Box>
            <Typography
              variant="h5"
              fontWeight={700}
              lineHeight={1.1}
              color={watchlist.issuers_with_new_developments > 0 ? "warning.main" : "text.primary"}
            >
              {watchlist.issuers_with_new_developments}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              with new developments
            </Typography>
          </Box>
          <Box>
            <Typography
              variant="h5"
              fontWeight={700}
              lineHeight={1.1}
              color={watchlist.high_severity_count > 0 ? "error.main" : "text.primary"}
            >
              {watchlist.high_severity_count}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              high-severity
            </Typography>
          </Box>
          <Box>
            <Typography
              variant="h5"
              fontWeight={700}
              lineHeight={1.1}
              color={watchlist.new_alert_count > 0 ? "warning.main" : "text.primary"}
            >
              {watchlist.new_alert_count}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              new alerts
            </Typography>
          </Box>
        </Stack>
      </Box>

      <DataTable
        data={issuers}
        columns={columns}
        sorting={[]}
        onSortingChange={() => {}}
        isLoading={false}
        isError={false}
        emptyMessage="No issuers on this Watchlist yet. Add one from Issuer Detail."
        getRowId={(row) => row.issuer_id}
        renderMobileCard={(row) => (
          <MobileIssuerCard row={row} watchlistId={watchlistId as string} />
        )}
      />

      <Box>
        <Link component={RouterLink} to="/watchlists" underline="hover">
          ← Back to Watchlists
        </Link>
      </Box>

      <RenameWatchlistDialog
        open={renameOpen}
        onClose={() => setRenameOpen(false)}
        watchlistId={watchlist.id}
        currentName={watchlist.name}
        currentDescription={watchlist.description}
      />
      <DeleteWatchlistDialog
        open={deleteOpen}
        onClose={() => setDeleteOpen(false)}
        watchlistId={watchlist.id}
        watchlistName={watchlist.name}
      />
    </Stack>
  );
}
