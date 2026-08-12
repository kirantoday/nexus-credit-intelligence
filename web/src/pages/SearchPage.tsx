import type { ReactElement } from "react";
import { Link as RouterLink, useSearchParams } from "react-router";
import {
  Alert,
  Box,
  Card,
  CardActionArea,
  CardContent,
  Chip,
  CircularProgress,
  Link,
  Paper,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import SearchIcon from "@mui/icons-material/Search";
import type { SearchResultItem } from "../api/search";
import { searchResultLabel, searchResultPath } from "../lib/searchResult";
import { formatDate } from "../lib/format";
import { useSearch } from "../queries/useSearch";

const PAGE_LIMIT = 10;

/** Groups whose full result set is also reachable via an existing,
 * already-filterable page — "see all" reuses that page rather than
 * Universal Search building its own second pagination story. Every other
 * group has no such destination (no dedicated alert/docket/note list
 * page filterable by free text), so it simply shows up to `PAGE_LIMIT`
 * results directly and stops there. */
function seeAllHref(entityType: string, query: string): string | null {
  if (entityType === "issuer" || entityType === "security") {
    return `/?q=${encodeURIComponent(query)}`;
  }
  return null;
}

function ResultCard({ item }: { item: SearchResultItem }): ReactElement {
  return (
    <Card variant="outlined">
      <CardActionArea component={RouterLink} to={searchResultPath(item)}>
        <CardContent>
          <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
            <Typography variant="subtitle1">{item.title}</Typography>
            {item.matched_field && (
              <Chip
                label={`Exact: ${item.matched_field}`}
                size="small"
                color="primary"
                variant="filled"
              />
            )}
          </Stack>
          {item.snippet && (
            <Typography variant="body2" color="text.secondary" noWrap>
              {item.snippet}
            </Typography>
          )}
          {item.context_date && (
            <Typography variant="caption" color="text.secondary">
              {formatDate(item.context_date)}
            </Typography>
          )}
        </CardContent>
      </CardActionArea>
    </Card>
  );
}

export function SearchPage(): ReactElement {
  const [searchParams, setSearchParams] = useSearchParams();
  const query = searchParams.get("q") ?? "";
  const searchQuery = useSearch(query, PAGE_LIMIT);

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h4" gutterBottom>
          Search
        </Typography>
        <TextField
          fullWidth
          placeholder="Search issuers, securities, alerts, court dockets, Research Notes…"
          value={query}
          onChange={(e) => setSearchParams(e.target.value ? { q: e.target.value } : {})}
          slotProps={{ input: { startAdornment: <SearchIcon sx={{ mr: 1, opacity: 0.6 }} /> } }}
        />
      </Box>

      {!query.trim() && (
        <Typography variant="body2" color="text.secondary">
          Enter a search term above — an issuer name, ticker, CIK, CUSIP, ISIN, FIGI, docket number,
          or a phrase like "going concern" or "covenant."
        </Typography>
      )}

      {searchQuery.isLoading && (
        <Box sx={{ py: 4, textAlign: "center" }}>
          <CircularProgress />
        </Box>
      )}

      {searchQuery.isError && <Alert severity="error">Could not load search results.</Alert>}

      {searchQuery.data &&
        query.trim() &&
        searchQuery.data.exact_matches.length === 0 &&
        searchQuery.data.groups.length === 0 && (
          <Typography variant="body2" color="text.secondary">
            No results for "{query}".
          </Typography>
        )}

      {searchQuery.data && searchQuery.data.exact_matches.length > 0 && (
        <Paper variant="outlined" sx={{ p: 2 }}>
          <Typography variant="h6" gutterBottom>
            Exact Matches
          </Typography>
          <Stack spacing={1.5}>
            {searchQuery.data.exact_matches.map((item) => (
              <ResultCard key={`${item.entity_type}-${item.entity_id}`} item={item} />
            ))}
          </Stack>
        </Paper>
      )}

      {searchQuery.data?.groups.map((group) => {
        const href = seeAllHref(group.entity_type, query);
        return (
          <Paper key={group.entity_type} variant="outlined" sx={{ p: 2 }}>
            <Stack
              direction="row"
              justifyContent="space-between"
              alignItems="center"
              sx={{ mb: 1.5 }}
            >
              <Typography variant="h6">
                {searchResultLabel(
                  group.results[0] ?? ({ entity_type: group.entity_type } as SearchResultItem),
                )}
              </Typography>
              {href && (
                <Link component={RouterLink} to={href} underline="hover">
                  <Typography variant="body2">See all in Credit Universe</Typography>
                </Link>
              )}
            </Stack>
            <Stack spacing={1.5}>
              {group.results.map((item) => (
                <ResultCard key={`${item.entity_type}-${item.entity_id}`} item={item} />
              ))}
            </Stack>
          </Paper>
        );
      })}
    </Stack>
  );
}
