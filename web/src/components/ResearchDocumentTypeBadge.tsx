import type { ReactElement } from "react";
import { Chip } from "@mui/material";
import type { ResearchDocumentType } from "../api/researchDocument";

const TYPE_LABEL: Record<ResearchDocumentType, string> = {
  credit_agreement: "Credit Agreement",
  amendment: "Amendment",
  earnings_presentation: "Earnings Presentation",
  investor_presentation: "Investor Presentation",
  restructuring_presentation: "Restructuring Presentation",
  lender_presentation: "Lender Presentation",
  bankruptcy_court_document: "Bankruptcy/Court Document",
  financial_model_analysis: "Financial Model/Analysis",
  internal_research_memo: "Internal Research Memo",
  other: "Other",
};

export function ResearchDocumentTypeBadge({
  documentType,
}: {
  documentType: ResearchDocumentType;
}): ReactElement {
  return <Chip label={TYPE_LABEL[documentType]} size="small" variant="outlined" color="primary" />;
}
