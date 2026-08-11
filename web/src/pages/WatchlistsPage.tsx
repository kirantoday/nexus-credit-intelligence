import { type ReactElement, useState } from "react";
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import { WatchlistCard } from "../components/WatchlistCard";
import { useCreateWatchlist, useWatchlists } from "../queries/useWatchlists";

function NewWatchlistDialog({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}): ReactElement {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const createWatchlist = useCreateWatchlist();

  function handleClose(): void {
    setName("");
    setDescription("");
    createWatchlist.reset();
    onClose();
  }

  function handleCreate(): void {
    const trimmed = name.trim();
    if (!trimmed) return;
    createWatchlist.mutate(
      { name: trimmed, description: description.trim() },
      { onSuccess: () => handleClose() },
    );
  }

  return (
    <Dialog open={open} onClose={handleClose} fullWidth maxWidth="xs">
      <DialogTitle>New Watchlist</DialogTitle>
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
            label="Description (optional)"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            multiline
            minRows={2}
            fullWidth
          />
          {createWatchlist.isError && (
            <Alert severity="error">Could not create this Watchlist. Please try again.</Alert>
          )}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose}>Cancel</Button>
        <Button
          variant="contained"
          disabled={!name.trim() || createWatchlist.isPending}
          onClick={handleCreate}
        >
          Create
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export function WatchlistsPage(): ReactElement {
  const { data, isLoading, isError, error } = useWatchlists();
  const [dialogOpen, setDialogOpen] = useState(false);

  const watchlists = data?.watchlists ?? [];

  return (
    <Stack spacing={3}>
      <Stack
        direction="row"
        justifyContent="space-between"
        alignItems="flex-start"
        flexWrap="wrap"
        spacing={1}
      >
        <Box>
          <Typography variant="h4" gutterBottom>
            Watchlists
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Which issuers do you personally care about, and what's changed? Your own tracking lists,
            separate from the organization's curated Research Universes.
          </Typography>
        </Box>
        <Button variant="contained" startIcon={<AddIcon />} onClick={() => setDialogOpen(true)}>
          New Watchlist
        </Button>
      </Stack>

      {isLoading && (
        <Box sx={{ py: 8, textAlign: "center" }}>
          <CircularProgress />
        </Box>
      )}

      {isError && (
        <Alert severity="error">
          Could not load Watchlists: {error instanceof Error ? error.message : "unknown error"}
        </Alert>
      )}

      {!isLoading && !isError && watchlists.length === 0 && (
        <Alert severity="info">
          No Watchlists yet. Create one to start tracking issuers you care about.
        </Alert>
      )}

      <Stack direction="row" flexWrap="wrap" useFlexGap spacing={2}>
        {watchlists.map((watchlist) => (
          <Box key={watchlist.id} sx={{ width: { xs: "100%", sm: 360 } }}>
            <WatchlistCard watchlist={watchlist} />
          </Box>
        ))}
      </Stack>

      <NewWatchlistDialog open={dialogOpen} onClose={() => setDialogOpen(false)} />
    </Stack>
  );
}
