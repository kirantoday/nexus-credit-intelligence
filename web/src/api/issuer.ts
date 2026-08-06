import { apiFetch } from "./client";
import type {
  DataClassification,
  FreshnessTier,
  InstrumentType,
  ProviderName,
  Seniority,
  TransformationType,
} from "./creditUniverse";

/**
 * One row of `IssuerDetail.securities` (backend/app/schemas/issuer.py).
 * Decimal fields arrive as strings — see api/creditUniverse.ts's docstring.
 */
export interface IssuerSecurityRow {
  security_id: string;
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
}

export type FormType = "10-K" | "10-Q" | "8-K" | "6-K" | "20-F";

export interface IssuerFinancialFactRow {
  financial_fact_id: string;
  concept: string;
  value: string;
  unit: string;
  fiscal_period: string;
  fiscal_year: number;
  form_type: FormType;
  filing_date: string;
  accession_no: string;
  provider: ProviderName;
  classification: DataClassification;
  as_of_date: string;
  retrieved_at: string;
  freshness: FreshnessTier;
  source_url: string | null;
}

export interface IssuerDataSource {
  provider: ProviderName;
  record_count: number;
  latest_retrieved_at: string;
}

export type IssuerActivityCategory = "filing" | "security_identified" | "capital_structure_update";

export interface IssuerActivityItem {
  occurred_on: string;
  category: IssuerActivityCategory;
  headline: string;
  provider: ProviderName;
  source_url: string | null;
  as_of_date: string;
}

export interface IssuerDetail {
  issuer_id: string;
  legal_name: string;
  cik: string | null;
  lei: string | null;
  ticker: string | null;
  sic: string | null;
  sector: string | null;
  is_synthetic: boolean;
  synthetic_reason: string | null;
  securities: IssuerSecurityRow[];
  financial_facts: IssuerFinancialFactRow[];
  data_sources: IssuerDataSource[];
  recent_activity: IssuerActivityItem[];
}

export async function fetchIssuerDetail(issuerId: string): Promise<IssuerDetail> {
  return apiFetch<IssuerDetail>(`/api/issuers/${issuerId}`);
}
