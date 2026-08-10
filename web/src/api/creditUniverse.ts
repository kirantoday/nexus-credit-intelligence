import { apiFetch } from "./client";

// Mirrors backend/app/core/types.py exactly — the canonical, provider-neutral
// vocabulary. Never add a provider-specific value here.
export type InstrumentType = "bond" | "loan" | "equity";

export type Seniority =
  "first_lien" | "second_lien" | "senior_unsecured" | "subordinated" | "preferred" | "common";

export type ProviderName =
  | "sec_edgar"
  | "finra_trace"
  | "openfigi"
  | "fred"
  | "courtlistener"
  | "pacer"
  | "admin_upload"
  | "sp_global_loan_pricing"
  | "sp_global_loan_reference"
  | "octus"
  | "bloomberg"
  | "lseg_lpc"
  | "synthetic"
  | "ai_generated";

export type DataClassification = "public" | "licensed" | "synthetic" | "ai_extracted";

export type TransformationType = "reported" | "calculated";

export type FreshnessTier = "live" | "cached" | "stale";

/**
 * One Credit Universe row (backend/app/schemas/credit_universe.py).
 *
 * Decimal fields (`coupon`, `amount_outstanding`, `spread`) arrive as
 * strings, not numbers — Pydantic 2 serializes `Decimal` to a JSON string to
 * avoid binary-float precision loss, and this type follows that exactly
 * rather than widening it to `number` and losing precision on parse.
 */
export interface CreditUniverseRow {
  security_id: string;
  issuer_id: string;
  issuer_legal_name: string;
  issuer_ticker: string | null;
  issuer_sector: string | null;
  instrument_type: InstrumentType;
  description: string;
  seniority: Seniority | null;
  lien_position: string | null;
  secured: boolean | null;
  cusip: string | null;
  isin: string | null;
  figi: string | null;
  maturity_date: string | null;
  coupon: string | null;
  amount_outstanding: string | null;
  benchmark: string | null;
  spread: string | null;
  is_synthetic: boolean;
  synthetic_reason: string | null;
  provider: ProviderName;
  classification: DataClassification;
  transformation: TransformationType;
  as_of_date: string;
  retrieved_at: string;
  freshness: FreshnessTier;
  /**
   * The security's own `benchmark` (e.g. "SOFR") re-priced against a real,
   * live FRED observation — a plain reported fact, not blended with `spread`
   * into a new calculated number. `null` whenever `benchmark` isn't a series
   * this platform syncs (or the security has no benchmark at all).
   */
  benchmark_rate: string | null;
  benchmark_rate_as_of_date: string | null;
  benchmark_rate_provider: ProviderName | null;
}

export interface CreditUniversePage {
  rows: CreditUniverseRow[];
  total: number;
  page: number;
  page_size: number;
}

export type CreditUniverseSortField =
  "legal_name" | "instrument_type" | "maturity_date" | "amount_outstanding" | "coupon";

export type SortDirection = "asc" | "desc";

export interface CreditUniverseQuery {
  instrumentType?: InstrumentType;
  search?: string;
  /** Milestone 6.5 (PLAN.md 24.9) — filters to issuers that are members of
   * this Research Universe/Watchlist/Benchmark collection. */
  universeId?: string;
  sortBy?: CreditUniverseSortField;
  sortDir?: SortDirection;
  page?: number;
  pageSize?: number;
}

export async function fetchCreditUniverse(query: CreditUniverseQuery): Promise<CreditUniversePage> {
  const params = new URLSearchParams();
  if (query.instrumentType) params.set("instrument_type", query.instrumentType);
  if (query.search) params.set("search", query.search);
  if (query.universeId) params.set("universe_id", query.universeId);
  if (query.sortBy) params.set("sort_by", query.sortBy);
  if (query.sortDir) params.set("sort_dir", query.sortDir);
  params.set("page", String(query.page ?? 1));
  params.set("page_size", String(query.pageSize ?? 50));

  return apiFetch<CreditUniversePage>(`/api/credit-universe?${params.toString()}`);
}
