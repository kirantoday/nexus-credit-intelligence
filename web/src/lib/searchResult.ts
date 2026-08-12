import type { SearchEntityType, SearchResultItem } from "../api/search";

/**
 * Where a search result navigates to — centralized so `GlobalSearch` and
 * `SearchPage` never disagree (Milestone 12A). Every entity type routes to
 * an existing, already-built page; Universal Search adds no new detail
 * pages of its own.
 */
export function searchResultPath(item: SearchResultItem): string {
  switch (item.entity_type) {
    case "issuer":
      return `/issuers/${item.entity_id}`;
    case "security":
    case "alert_event":
    case "sec_filing":
      // No dedicated instrument/alert/filing detail page exists — all
      // three surface within Issuer Detail's own sections.
      return item.issuer_id ? `/issuers/${item.issuer_id}` : "/";
    case "court_docket":
    case "court_docket_entry":
      // Both land on Issuer Detail's "What happened in court?" section —
      // a docket_entry's issuer_id is resolved via its parent docket.
      return item.issuer_id ? `/issuers/${item.issuer_id}` : "/";
    case "collection":
      return item.collection_type === "watchlist"
        ? `/watchlists/${item.entity_id}`
        : `/?universe=${item.entity_id}`;
    case "research_note":
      return `/research-notes/${item.entity_id}`;
  }
}

const ENTITY_TYPE_LABEL: Record<SearchEntityType, string> = {
  issuer: "Issuer",
  security: "Security",
  alert_event: "Distress Development",
  court_docket: "Court Docket",
  court_docket_entry: "Court Docket Entry",
  collection: "Research Universe",
  research_note: "Research Note",
  sec_filing: "SEC Filing",
};

/** `collection` covers Research Universes, Watchlists, and Benchmarks
 * alike (ADR-016) — label by the result's own `collection_type`, not a
 * flat "Collection" that would blur three distinct product concepts. */
export function searchResultLabel(item: SearchResultItem): string {
  if (item.entity_type === "collection") {
    if (item.collection_type === "watchlist") return "Watchlist";
    if (item.collection_type === "benchmark") return "Benchmark";
    return "Research Universe";
  }
  return ENTITY_TYPE_LABEL[item.entity_type];
}

export const SEARCH_GROUP_ORDER: SearchEntityType[] = [
  "issuer",
  "security",
  "alert_event",
  "court_docket",
  "court_docket_entry",
  "collection",
  "research_note",
  "sec_filing",
];
