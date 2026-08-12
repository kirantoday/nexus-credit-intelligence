import { type KeyboardEvent, type ReactElement, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router";
import {
  Box,
  ClickAwayListener,
  Dialog,
  DialogContent,
  IconButton,
  InputAdornment,
  List,
  ListItemButton,
  ListItemText,
  ListSubheader,
  Paper,
  Popper,
  TextField,
  Typography,
} from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import SearchIcon from "@mui/icons-material/Search";
import type { SearchResultItem } from "../api/search";
import { searchResultLabel, searchResultPath } from "../lib/searchResult";
import { useDebouncedValue } from "../lib/useDebouncedValue";
import { useIsMobile } from "../lib/useIsMobile";
import { useSearch } from "../queries/useSearch";

const TYPEAHEAD_LIMIT = 5;

type KeyboardItem = { kind: "result"; item: SearchResultItem } | { kind: "see-all" };

function flattenResults(
  data: ReturnType<typeof useSearch>["data"],
): { key: string; heading: string; items: SearchResultItem[] }[] {
  if (!data) return [];
  const sections: { key: string; heading: string; items: SearchResultItem[] }[] = [];
  if (data.exact_matches.length > 0) {
    sections.push({ key: "exact", heading: "Exact Matches", items: data.exact_matches });
  }
  for (const group of data.groups) {
    sections.push({
      key: group.entity_type,
      heading: searchResultLabel(
        group.results[0] ?? ({ entity_type: group.entity_type } as SearchResultItem),
      ),
      items: group.results,
    });
  }
  return sections;
}

/** Global Universal Search entry point in the app header (PLAN.md 4.13, 8;
 * Milestone 12A). Desktop: a debounced typeahead dropdown, grouped by
 * entity type. Mobile: a search icon opening a simpler full-screen dialog
 * — never a desktop-sized dropdown forced into a constrained header. */
export function GlobalSearch(): ReactElement {
  const isMobile = useIsMobile();
  const [inputValue, setInputValue] = useState("");
  const [open, setOpen] = useState(false);
  const [mobileDialogOpen, setMobileDialogOpen] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const anchorRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  const debounced = useDebouncedValue(inputValue, 300);
  const searchQuery = useSearch(debounced, TYPEAHEAD_LIMIT);

  const sections = useMemo(() => flattenResults(searchQuery.data), [searchQuery.data]);
  const flatItems = useMemo(() => sections.flatMap((s) => s.items), [sections]);
  const keyboardItems: KeyboardItem[] = useMemo(() => {
    const items: KeyboardItem[] = flatItems.map((item) => ({ kind: "result", item }));
    if (inputValue.trim()) items.push({ kind: "see-all" });
    return items;
  }, [flatItems, inputValue]);

  function reset(): void {
    setInputValue("");
    setOpen(false);
    setMobileDialogOpen(false);
    setHighlightedIndex(-1);
  }

  function goToResult(item: SearchResultItem): void {
    reset();
    navigate(searchResultPath(item));
  }

  function seeAllResults(): void {
    const q = inputValue.trim();
    reset();
    if (q) navigate(`/search?q=${encodeURIComponent(q)}`);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>): void {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      if (keyboardItems.length > 0) {
        setOpen(true);
        setHighlightedIndex((i) => Math.min(i + 1, keyboardItems.length - 1));
      }
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setHighlightedIndex((i) => Math.max(i - 1, -1));
    } else if (event.key === "Enter") {
      event.preventDefault();
      const selected = keyboardItems[highlightedIndex];
      if (selected?.kind === "result") {
        goToResult(selected.item);
      } else {
        seeAllResults();
      }
    } else if (event.key === "Escape") {
      setOpen(false);
      setMobileDialogOpen(false);
    }
  }

  const resultsBody = (
    <>
      {searchQuery.isLoading && (
        <Box sx={{ px: 2, py: 1.5 }}>
          <Typography variant="body2" color="text.secondary">
            Searching…
          </Typography>
        </Box>
      )}
      {searchQuery.isError && (
        <Box sx={{ px: 2, py: 1.5 }}>
          <Typography variant="body2" color="error">
            Could not load search results.
          </Typography>
        </Box>
      )}
      {!searchQuery.isLoading &&
        !searchQuery.isError &&
        debounced.trim() &&
        flatItems.length === 0 && (
          <Box sx={{ px: 2, py: 1.5 }}>
            <Typography variant="body2" color="text.secondary">
              No results for "{debounced}".
            </Typography>
          </Box>
        )}
      <List dense disablePadding role="listbox" aria-label="Search results">
        {sections.map((section) => (
          <li key={section.key}>
            <ul style={{ padding: 0, margin: 0 }}>
              <ListSubheader component="div" sx={{ lineHeight: "32px" }}>
                {section.heading}
              </ListSubheader>
              {section.items.map((item) => {
                const index = flatItems.indexOf(item);
                return (
                  <ListItemButton
                    key={`${item.entity_type}-${item.entity_id}`}
                    role="option"
                    aria-selected={index === highlightedIndex}
                    selected={index === highlightedIndex}
                    onMouseDown={(e) => {
                      e.preventDefault();
                      goToResult(item);
                    }}
                    onMouseEnter={() => setHighlightedIndex(index)}
                  >
                    <ListItemText
                      primary={item.title}
                      secondary={item.snippet}
                      slotProps={{
                        primary: { noWrap: true },
                        secondary: { noWrap: true },
                      }}
                    />
                  </ListItemButton>
                );
              })}
            </ul>
          </li>
        ))}
      </List>
      {inputValue.trim() && (
        <ListItemButton
          role="option"
          aria-selected={keyboardItems[highlightedIndex]?.kind === "see-all"}
          selected={keyboardItems[highlightedIndex]?.kind === "see-all"}
          onMouseDown={(e) => {
            e.preventDefault();
            seeAllResults();
          }}
          onMouseEnter={() => setHighlightedIndex(keyboardItems.length - 1)}
        >
          <ListItemText primary={`See all results for "${inputValue.trim()}"`} />
        </ListItemButton>
      )}
    </>
  );

  if (isMobile) {
    return (
      <>
        <IconButton
          color="inherit"
          aria-label="Search Nexus"
          onClick={() => setMobileDialogOpen(true)}
        >
          <SearchIcon />
        </IconButton>
        <Dialog
          fullScreen
          open={mobileDialogOpen}
          onClose={() => setMobileDialogOpen(false)}
          aria-label="Search Nexus"
        >
          <Box
            sx={{
              display: "flex",
              alignItems: "center",
              gap: 1,
              p: 1.5,
              borderBottom: 1,
              borderColor: "divider",
            }}
          >
            <TextField
              autoFocus
              fullWidth
              size="small"
              placeholder="Search issuers, alerts, notes…"
              value={inputValue}
              onChange={(e) => {
                setInputValue(e.target.value);
                setHighlightedIndex(-1);
              }}
              onKeyDown={handleKeyDown}
              slotProps={{
                htmlInput: { "aria-label": "Search Nexus" },
                input: {
                  startAdornment: (
                    <InputAdornment position="start">
                      <SearchIcon fontSize="small" />
                    </InputAdornment>
                  ),
                },
              }}
            />
            <IconButton aria-label="Close search" onClick={() => setMobileDialogOpen(false)}>
              <CloseIcon />
            </IconButton>
          </Box>
          <DialogContent sx={{ p: 0 }}>{resultsBody}</DialogContent>
        </Dialog>
      </>
    );
  }

  return (
    <ClickAwayListener onClickAway={() => setOpen(false)}>
      <Box ref={anchorRef} sx={{ position: "relative", width: 360 }}>
        <TextField
          size="small"
          fullWidth
          placeholder="Search issuers, alerts, notes…"
          value={inputValue}
          onChange={(e) => {
            setInputValue(e.target.value);
            setHighlightedIndex(-1);
            setOpen(true);
          }}
          onFocus={() => {
            if (inputValue.trim()) setOpen(true);
          }}
          onKeyDown={handleKeyDown}
          slotProps={{
            htmlInput: { "aria-label": "Search Nexus" },
            input: {
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon fontSize="small" sx={{ color: "inherit", opacity: 0.7 }} />
                </InputAdornment>
              ),
            },
          }}
          sx={{
            bgcolor: "rgba(255,255,255,0.15)",
            borderRadius: 1,
            input: { color: "inherit" },
            "& .MuiOutlinedInput-notchedOutline": { borderColor: "rgba(255,255,255,0.3)" },
          }}
        />
        <Popper
          open={open && debounced.trim().length > 0}
          anchorEl={anchorRef.current}
          placement="bottom-start"
          sx={{ zIndex: (theme) => theme.zIndex.modal, width: 420 }}
        >
          <Paper elevation={6} sx={{ mt: 0.5, maxHeight: 480, overflowY: "auto" }}>
            {resultsBody}
          </Paper>
        </Popper>
      </Box>
    </ClickAwayListener>
  );
}
