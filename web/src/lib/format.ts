/**
 * Formats a Decimal-as-string amount (e.g. "71340000000") as a compact,
 * human-readable currency figure (e.g. "$71.3B"). Values arrive as strings
 * from the API specifically to avoid binary-float precision loss (see
 * api/creditUniverse.ts) — this only widens to `number` for display
 * rounding, never for anything that needs exact precision.
 */
export function formatCompactCurrency(value: string | null): string {
  if (value === null) return "—";
  const num = Number(value);
  if (!Number.isFinite(num)) return "—";
  const abs = Math.abs(num);
  const sign = num < 0 ? "-" : "";
  if (abs >= 1_000_000_000) return `${sign}$${(abs / 1_000_000_000).toFixed(1)}B`;
  if (abs >= 1_000_000) return `${sign}$${(abs / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `${sign}$${(abs / 1_000).toFixed(1)}K`;
  return `${sign}$${abs.toFixed(0)}`;
}

export function formatPercent(value: string | null): string {
  if (value === null) return "—";
  const num = Number(value);
  if (!Number.isFinite(num)) return "—";
  return `${num.toFixed(2)}%`;
}

export function formatDate(value: string | null): string {
  if (value === null) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  // A date-only string (e.g. "2029-06-15", a maturity/as-of date, not a
  // timestamp) parses as UTC midnight. Formatting in the viewer's local
  // timezone would shift it to the previous day west of UTC — these are
  // calendar dates, not instants, so they're always rendered in UTC.
  return date.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

export function formatDateTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString("en-US", { dateStyle: "medium", timeStyle: "short" });
}

export function formatOrDash(value: string | null): string {
  return value ?? "—";
}
