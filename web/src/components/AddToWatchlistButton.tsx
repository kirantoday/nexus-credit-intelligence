import { type ReactElement, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Checkbox,
  CircularProgress,
  Divider,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import BookmarkAddOutlinedIcon from "@mui/icons-material/BookmarkAddOutlined";
import BookmarkOutlinedIcon from "@mui/icons-material/BookmarkOutlined";
import {
  useAddIssuerToWatchlist,
  useCreateWatchlist,
  useRemoveIssuerFromWatchlist,
  useWatchlists,
} from "../queries/useWatchlists";

/**
 * The single reusable "Add to Watchlist" interaction (PLAN.md Milestone 8
 * Phase 8) — a button that opens a menu of every existing Watchlist,
 * showing which already include this issuer, letting the analyst toggle
 * membership or create a new Watchlist inline. Built once; every page that
 * needs this workflow (Issuer Detail at minimum) renders this same
 * component rather than a page-specific reimplementation.
 */
export function AddToWatchlistButton({ issuerId }: { issuerId: string }): ReactElement {
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);
  const [newName, setNewName] = useState("");
  const watchlistsQuery = useWatchlists(issuerId);
  const addIssuer = useAddIssuerToWatchlist();
  const removeIssuer = useRemoveIssuerFromWatchlist();
  const createWatchlist = useCreateWatchlist();

  const open = Boolean(anchorEl);
  const watchlists = watchlistsQuery.data?.watchlists ?? [];
  const watchedCount = watchlists.filter((w) => w.contains_issuer).length;

  function handleClose(): void {
    setAnchorEl(null);
    setNewName("");
  }

  function handleToggle(watchlistId: string, alreadyAdded: boolean): void {
    if (alreadyAdded) {
      removeIssuer.mutate({ watchlistId, issuerId });
    } else {
      addIssuer.mutate({ watchlistId, issuerId });
    }
  }

  function handleCreateAndAdd(): void {
    const name = newName.trim();
    if (!name) return;
    createWatchlist.mutate(
      { name },
      {
        onSuccess: (created) => {
          addIssuer.mutate({ watchlistId: created.id, issuerId });
          setNewName("");
        },
      },
    );
  }

  return (
    <>
      <Button
        variant={watchedCount > 0 ? "contained" : "outlined"}
        size="small"
        startIcon={watchedCount > 0 ? <BookmarkOutlinedIcon /> : <BookmarkAddOutlinedIcon />}
        onClick={(event) => setAnchorEl(event.currentTarget)}
      >
        {watchedCount > 0
          ? `On ${watchedCount} Watchlist${watchedCount === 1 ? "" : "s"}`
          : "Add to Watchlist"}
      </Button>
      <Menu anchorEl={anchorEl} open={open} onClose={handleClose}>
        <Box sx={{ px: 2, py: 1, minWidth: 280 }}>
          <Typography variant="subtitle2">Add to Watchlist</Typography>
        </Box>
        <Divider />
        {watchlistsQuery.isLoading && (
          <Box sx={{ py: 2, textAlign: "center" }}>
            <CircularProgress size={20} />
          </Box>
        )}
        {watchlistsQuery.isError && (
          <Box sx={{ px: 2, py: 1 }}>
            <Alert severity="error" variant="outlined" sx={{ py: 0 }}>
              Could not load Watchlists.
            </Alert>
          </Box>
        )}
        {!watchlistsQuery.isLoading && watchlists.length === 0 && (
          <Box sx={{ px: 2, py: 1 }}>
            <Typography variant="body2" color="text.secondary">
              No Watchlists yet — create one below.
            </Typography>
          </Box>
        )}
        {watchlists.map((watchlist) => (
          <MenuItem
            key={watchlist.id}
            role="menuitemcheckbox"
            aria-checked={Boolean(watchlist.contains_issuer)}
            onClick={() => handleToggle(watchlist.id, Boolean(watchlist.contains_issuer))}
            dense
          >
            <ListItemIcon>
              <Checkbox
                edge="start"
                checked={Boolean(watchlist.contains_issuer)}
                tabIndex={-1}
                disableRipple
                size="small"
              />
            </ListItemIcon>
            <ListItemText primary={watchlist.name} />
          </MenuItem>
        ))}
        <Divider />
        <Stack direction="row" spacing={1} sx={{ px: 2, py: 1.5 }} alignItems="center">
          <TextField
            size="small"
            placeholder="New Watchlist name"
            value={newName}
            onChange={(event) => setNewName(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") handleCreateAndAdd();
            }}
            fullWidth
          />
          <Button
            size="small"
            variant="outlined"
            disabled={!newName.trim() || createWatchlist.isPending}
            onClick={handleCreateAndAdd}
          >
            Create
          </Button>
        </Stack>
      </Menu>
    </>
  );
}
