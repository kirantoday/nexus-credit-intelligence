import { apiFetch } from "./client";
import type {
  DataClassification,
  FreshnessTier,
  ProviderName,
  Seniority,
  TransformationType,
} from "./creditUniverse";

// Mirrors backend/app/core/types.py's CapitalStructureInstrumentType exactly.
export type CapitalStructureInstrumentType =
  | "revolver"
  | "first_lien_loan"
  | "first_lien_notes"
  | "second_lien"
  | "unsecured"
  | "subordinated"
  | "preferred_equity"
  | "common_equity";

/**
 * One layer of an issuer's capital structure (backend/app/schemas/capital_structure.py).
 * `enterprise_value_coverage`/`illustrative_recovery` are `null` unless this
 * platform has modeled a scenario for this layer — when either is present,
 * `recovery_scenario` is always present too (enforced server-side), so the
 * UI can render PLAN.md section 7's mandatory four-part label every time.
 */
export interface CapitalStructurePositionRow {
  position_id: string;
  security_id: string | null;
  layer_name: string;
  rank_order: number;
  instrument_type: CapitalStructureInstrumentType;
  seniority: Seniority | null;
  lien_position: string | null;
  secured: boolean;
  guarantor_scope: string | null;
  amount_outstanding: string;
  currency: string;
  maturity_date: string | null;
  price: string | null;
  enterprise_value_coverage: string | null;
  illustrative_recovery: string | null;
  recovery_scenario: string | null;
  is_synthetic: boolean;
  synthetic_reason: string | null;
  provider: ProviderName;
  classification: DataClassification;
  transformation: TransformationType;
  as_of_date: string;
  retrieved_at: string;
  freshness: FreshnessTier;
}

export interface CapitalStructureResponse {
  issuer_id: string;
  issuer_legal_name: string;
  positions: CapitalStructurePositionRow[];
}

export async function fetchCapitalStructure(issuerId: string): Promise<CapitalStructureResponse> {
  return apiFetch<CapitalStructureResponse>(`/api/issuers/${issuerId}/capital-structure`);
}
