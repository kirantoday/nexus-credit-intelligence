import { apiFetch } from "./client";
import type { FreshnessTier, ProviderName } from "./creditUniverse";

/**
 * One Market Context observation (backend/app/schemas/market_context.py).
 *
 * `value` arrives as a string, not a number — same Decimal-as-JSON-string
 * convention as `CreditUniverseRow` (see that file's docstring).
 */
export interface MarketContextObservation {
  series_id: string;
  title: string;
  value: string;
  units: string;
  as_of_date: string;
  freshness: FreshnessTier;
  provider: ProviderName;
}

/**
 * `null` for a field whenever that FRED series hasn't been synced yet —
 * never a fabricated placeholder value.
 */
export interface MarketContext {
  sofr: MarketContextObservation | null;
  high_yield_oas: MarketContextObservation | null;
}

export async function fetchMarketContext(): Promise<MarketContext> {
  return apiFetch<MarketContext>("/api/market-context");
}
