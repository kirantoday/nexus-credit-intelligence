"""Shared canonical enumerations (PLAN.md section 4).

Single source of truth for every enum-shaped value that appears across domain
objects, ORM models (as CHECK constraints), and future provider adapters. A
value is defined here once and reused everywhere else — never re-declared as a
bare string literal in a model, repository, or migration.

These are stored as Postgres `text` columns with a CHECK constraint, not native
Postgres ENUM types (PLAN.md section 4 explicitly types these fields `text`).
Native enum types make adding a new provider or classification a schema-altering
operation; a text column with a CHECK constraint is exactly as safe and is a
plain migration to extend.
"""

from __future__ import annotations

from enum import StrEnum


class ProviderName(StrEnum):
    """`provenance.provider` / `raw_provider_payload.provider` (PLAN.md 4.1, 4.4)."""

    SEC_EDGAR = "sec_edgar"
    FINRA_TRACE = "finra_trace"
    OPENFIGI = "openfigi"
    FRED = "fred"
    COURTLISTENER = "courtlistener"
    PACER = "pacer"
    ADMIN_UPLOAD = "admin_upload"
    SP_GLOBAL_LOAN_PRICING = "sp_global_loan_pricing"
    SP_GLOBAL_LOAN_REFERENCE = "sp_global_loan_reference"
    OCTUS = "octus"
    BLOOMBERG = "bloomberg"
    LSEG_LPC = "lseg_lpc"
    SYNTHETIC = "synthetic"
    AI_GENERATED = "ai_generated"


class OriginalSource(StrEnum):
    """`provenance.original_source` — only set when provider is `admin_upload` (ADR-007)."""

    PACER = "pacer"
    COURTLISTENER = "courtlistener"
    ISSUER_SITE = "issuer_site"
    OTHER = "other"


class TransformationType(StrEnum):
    """`provenance.transformation` (PLAN.md 4.1)."""

    REPORTED = "reported"
    CALCULATED = "calculated"


class DataClassification(StrEnum):
    """`provenance.classification` (PLAN.md 4.1) — what `policy_check` gates on."""

    PUBLIC = "public"
    LICENSED = "licensed"
    SYNTHETIC = "synthetic"
    AI_EXTRACTED = "ai_extracted"


class EntitlementAction(StrEnum):
    """Actions `policy_check` can gate (PLAN.md 4.8)."""

    DISPLAY = "display"
    EXPORT = "export"
    SEND_TO_LLM = "send_to_llm"
    CREATE_EMBEDDING = "create_embedding"
    PROMPT_INCLUSION = "prompt_inclusion"
    DOCUMENT_DOWNLOAD = "document_download"
    API_EXPOSE = "api_expose"


class EnvironmentName(StrEnum):
    """`data_entitlement.environment` — mirrors `Settings.environment`'s literal values.

    Kept as an independent enum rather than importing `app.config.Settings` here:
    entitlement scoping is a domain concept that outlives any one process's
    config object, and this avoids coupling the domain layer to app startup
    config for four fixed string values.
    """

    LOCAL = "local"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class FormType(StrEnum):
    """`financial_fact.form_type` (PLAN.md 4.5) — SEC filing form types."""

    FORM_10K = "10-K"
    FORM_10Q = "10-Q"
    FORM_8K = "8-K"
    FORM_6K = "6-K"
    FORM_20F = "20-F"


class InstrumentType(StrEnum):
    """`security.instrument_type` (PLAN.md 4.5)."""

    BOND = "bond"
    LOAN = "loan"
    EQUITY = "equity"


class Seniority(StrEnum):
    """`security.seniority` (PLAN.md 4.5)."""

    FIRST_LIEN = "first_lien"
    SECOND_LIEN = "second_lien"
    SENIOR_UNSECURED = "senior_unsecured"
    SUBORDINATED = "subordinated"
    PREFERRED = "preferred"
    COMMON = "common"


class CapitalStructureInstrumentType(StrEnum):
    """`capital_structure_position.instrument_type` (PLAN.md 4.6).

    Distinct from `Seniority`: this names the *instrument* (a loan vs. a
    bond, both possibly first-lien), while `seniority` names the *ranking
    class* — a first-lien term loan and first-lien notes share
    `seniority = first_lien` but are different rows here because they are
    different instruments with different holders/documentation.
    """

    REVOLVER = "revolver"
    FIRST_LIEN_LOAN = "first_lien_loan"
    FIRST_LIEN_NOTES = "first_lien_notes"
    SECOND_LIEN = "second_lien"
    UNSECURED = "unsecured"
    SUBORDINATED = "subordinated"
    PREFERRED_EQUITY = "preferred_equity"
    COMMON_EQUITY = "common_equity"


# --- Milestone 6.5: Research Universes + Overnight Distress Filing Monitor ---


class CollectionType(StrEnum):
    """`collection.collection_type` (PLAN.md 24.1).

    Research Universes and Watchlists are distinct, coexisting product
    concepts that share one generalized table (ADR-016) rather than a
    dedicated `watchlist` table. `benchmark` is its own type (not just a
    research_universe with a flag) so the Investment Grade Benchmarks group
    can be queried and rendered as visually separate by construction.
    """

    RESEARCH_UNIVERSE = "research_universe"
    WATCHLIST = "watchlist"
    BENCHMARK = "benchmark"


class CollectionScope(StrEnum):
    """`collection.scope` (PLAN.md 24.1)."""

    ORGANIZATION = "organization"
    PERSONAL = "personal"
    TEAM = "team"


class CollectionVisibility(StrEnum):
    """`collection.visibility` (PLAN.md 24.1)."""

    PUBLIC = "public"
    PRIVATE = "private"
    TEAM = "team"


class CurationMethod(StrEnum):
    """`collection.curation_method` (PLAN.md 24.1)."""

    MANUAL_CURATED = "manual_curated"
    SYSTEM_SEEDED = "system_seeded"
    USER_CREATED = "user_created"


class VerificationStatus(StrEnum):
    """`collection.verification_status` / `collection_membership.verification_status`."""

    VERIFIED = "verified"
    PARTIAL = "partial"
    UNVERIFIED = "unverified"


class CollectionPriority(StrEnum):
    """`collection.priority` (PLAN.md 24.1) — reserved for future Morning Research

    Brief prioritization; not used for sorting logic in Milestone 6.5.
    """

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EvidenceType(StrEnum):
    """`research_evidence.evidence_type` (PLAN.md 24.3).

    Distress-signal values populated by this milestone's SEC filing monitor.
    The table/column are provider-agnostic (ADR-018); this allowed-value set
    grows via an ordinary migration when a future evidence type is needed,
    exactly how `ProviderName` already grows.
    """

    BANKRUPTCY_OR_RECEIVERSHIP = "bankruptcy_or_receivership"
    CHAPTER_11 = "chapter_11"
    CHAPTER_7 = "chapter_7"
    DEFAULT_OR_MISSED_PAYMENT = "default_or_missed_payment"
    COVENANT_BREACH = "covenant_breach"
    DEBT_ACCELERATION = "debt_acceleration"
    GOING_CONCERN = "going_concern"
    SUBSTANTIAL_DOUBT = "substantial_doubt"
    LIQUIDITY_WARNING = "liquidity_warning"
    RESTRUCTURING_ADVISOR = "restructuring_advisor"
    RESTRUCTURING_SUPPORT_AGREEMENT = "restructuring_support_agreement"
    EXCHANGE_OFFER = "exchange_offer"
    LIABILITY_MANAGEMENT_TRANSACTION = "liability_management_transaction"
    DEBT_AMENDMENT = "debt_amendment"
    MATURITY_EXTENSION = "maturity_extension"
    REFINANCING = "refinancing"
    DIP_FINANCING = "dip_financing"
    EMERGENCY_FINANCING = "emergency_financing"
    MATERIAL_ASSET_SALE = "material_asset_sale"
    DELISTING_NOTICE = "delisting_notice"
    WORKFORCE_REDUCTION = "workforce_reduction"
    FACILITY_CLOSURE = "facility_closure"
    MATERIAL_IMPAIRMENT = "material_impairment"
    AUDITOR_RESIGNATION = "auditor_resignation"
    ADVERSE_AUDIT_DEVELOPMENT = "adverse_audit_development"
    STRATEGIC_ALTERNATIVES = "strategic_alternatives"

    # Docket-specific values added in Milestone 7 (ADR-018's documented
    # forward path) — real docket-entry language patterns confirmed live
    # against CourtListener's actual RECAP data before being encoded here
    # (see BUILD_LOG.md), not guessed at.
    PLAN_CONFIRMED = "plan_confirmed"
    CASE_DISMISSED = "case_dismissed"
    CASE_CONVERTED = "case_converted"
    TRUSTEE_APPOINTED = "trustee_appointed"
    CLAIMS_BAR_DATE_SET = "claims_bar_date_set"
    RELIEF_FROM_STAY_MOTION = "relief_from_stay_motion"


class EvidenceSeverity(StrEnum):
    """`research_evidence.severity` / `alert_event.severity`."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class DetectionMethod(StrEnum):
    """`research_evidence.detection_method` / `alert_event.detection_method`."""

    DETERMINISTIC = "deterministic"
    AI_ASSISTED = "ai_assisted"


class ReviewStatus(StrEnum):
    """`research_evidence.review_status`."""

    UNREVIEWED = "unreviewed"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class AlertStatus(StrEnum):
    """`alert_event.status` (PLAN.md 24.3).

    Only these three values are implemented and populated in Milestone 6.5.
    Stored as text+CHECK (not a native enum) specifically so a future
    milestone can extend the allowed set to the full
    new -> acknowledged -> investigating -> resolved -> false_positive
    lifecycle via an ordinary migration, without a redesign.
    """

    NEW = "new"
    ACKNOWLEDGED = "acknowledged"
    DISMISSED = "dismissed"


class FilingMonitorRunStatus(StrEnum):
    """`filing_monitor_run.status` (PLAN.md 24.5)."""

    RUNNING = "running"
    SUCCESS = "success"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"
    BASELINE_ESTABLISHED = "baseline_established"


class FilingMonitorRunMode(StrEnum):
    """`filing_monitor_run.mode` (PLAN.md 24.5)."""

    BASELINE = "baseline"
    DELTA = "delta"
    BACKFILL = "backfill"


class DocketDocumentAvailability(StrEnum):
    """`docket_document.availability` (PLAN.md 4.5, section 15).

    `RECAP_AVAILABLE` — a real RECAP copy exists and was retrieved via
    CourtListener; never set for a sealed document, regardless of what the
    API otherwise reports as "available" (section 22 — never fetch sealed
    material). `UNAVAILABLE_ADMIN_UPLOAD_NEEDED` — the document is known to
    exist (an entry references it) but no RECAP copy exists yet; a real
    PACER purchase would be required, which this build never performs.
    `ADMIN_UPLOADED` — reserved for a future admin-upload flow (PLAN.md
    section 9); not populated by this milestone's live ingestion.
    """

    RECAP_AVAILABLE = "recap_available"
    UNAVAILABLE_ADMIN_UPLOAD_NEEDED = "unavailable_admin_upload_needed"
    ADMIN_UPLOADED = "admin_uploaded"


# SEC form types the overnight monitor watches (PLAN.md 24.5). Filtering
# happens in the service layer, not a DB CHECK constraint — `sec_filing.form_type`
# stays free text because real SEC amendment suffixes vary too much for a
# fixed constraint to be worth the brittleness.
MONITORED_FORM_TYPES: frozenset[str] = frozenset(
    {
        "8-K",
        "8-K/A",
        "10-Q",
        "10-Q/A",
        "10-K",
        "10-K/A",
        "6-K",
        "6-K/A",
        "20-F",
        "20-F/A",
    }
)


# --- Milestone 7.5: SEC Market Discovery & Automatic Issuer Enrichment ---


class MarketDiscoveryResolutionOutcome(StrEnum):
    """`market_discovery_candidate.resolution_outcome` (PLAN.md 7.5).

    A discovered SEC full-text-search hit's identity resolution result.
    `MATCHED_EXISTING`/`VERIFIED_NEW` are the only outcomes that produce or
    reuse a canonical `issuer` row; `AMBIGUOUS`/`REJECTED`/`UNRESOLVED` never
    create or link one, mirroring `seed_research_universes._resolve_cik`'s
    "never silently guess" discipline (the Yellow/Yellowstone fix).
    """

    MATCHED_EXISTING = "matched_existing"
    VERIFIED_NEW = "verified_new"
    AMBIGUOUS = "ambiguous"
    REJECTED = "rejected"
    UNRESOLVED = "unresolved"


class EnrichmentStatus(StrEnum):
    """`issuer_enrichment_status.status` (PLAN.md 7.5 section 8).

    Distinguishes "no data exists" (`NO_DATA`) from "never checked"
    (no row at all, or `PENDING`) — the core requirement of the automatic
    enrichment orchestrator. `FAILED_RETRYABLE` drives `next_retry_at`;
    `FAILED_PERMANENT` does not retry without an explicit force.
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    NO_DATA = "no_data"
    AMBIGUOUS = "ambiguous"
    MANUAL_REVIEW_REQUIRED = "manual_review_required"
    FAILED_RETRYABLE = "failed_retryable"
    FAILED_PERMANENT = "failed_permanent"
    BLOCKED_ENTITLEMENT = "blocked_entitlement"
    UNAVAILABLE = "unavailable"
    UNSUPPORTED = "unsupported"


class CourtDocketLinkMatchOutcome(StrEnum):
    """`court_docket_link_attempt.match_outcome` (PLAN.md 7.5 section 10, ADR-020).

    `VERIFIED_DOCKET_MATCH` requires case-type consistency plus enough
    independent strong identity signals agreeing with no contradiction, on a
    unique best candidate (ADR-020) — jurisdiction/HQ correspondence is
    never a required signal. Anything short of that bar is
    `AMBIGUOUS_MANUAL_REVIEW`, never a guess.
    """

    VERIFIED_DOCKET_MATCH = "verified_docket_match"
    CHECKED_NO_RELEVANT_DOCKET = "checked_no_relevant_docket"
    AMBIGUOUS_MANUAL_REVIEW = "ambiguous_manual_review"
    UNAVAILABLE = "unavailable"
    RETRYABLE_FAILURE = "retryable_failure"


# Issuer-level enrichment providers the orchestrator dispatches per-issuer
# (PLAN.md 7.5 section 13) — distinct from market-level providers (FRED)
# which are never redundantly executed per issuer.
ISSUER_LEVEL_ENRICHMENT_PROVIDERS: frozenset[ProviderName] = frozenset(
    {ProviderName.SEC_EDGAR, ProviderName.COURTLISTENER, ProviderName.OPENFIGI}
)


# --- Milestone 7.5.3: AI cost control, observability, model routing ---


class AiRoute(StrEnum):
    """The model tier `app.ai.model_router` actually used (or chose not to
    use) for one evidence-review decision. `DETERMINISTIC` means no
    Anthropic call was made at all — not even Haiku."""

    DETERMINISTIC = "deterministic"
    HAIKU = "haiku"
    SONNET = "sonnet"


class AiOperation(StrEnum):
    """`ai_call_log.operation` — the AI task being performed, independent of
    which model handled it. New operations are added here, never inferred
    from a free-text string, so cost-by-operation reporting stays exact."""

    EVIDENCE_REVIEW = "evidence_review"
    RECLASSIFY_ISSUER_IS_SUBJECT = "reclassify_issuer_is_subject"


# --- Milestone 10A: Research Notes + Audit Trail ---


class ThesisStatus(StrEnum):
    """`research_note.thesis_status` / `research_note_version.thesis_status`
    (PLAN.md 4.10). `INVALIDATED` is the status an analyst sets when their
    own `invalidation_conditions` have actually been met — a deliberate
    analyst judgment call, never inferred automatically from other data."""

    DRAFT = "draft"
    ACTIVE = "active"
    MONITORING = "monitoring"
    INVALIDATED = "invalidated"
    RESOLVED = "resolved"


class Conviction(StrEnum):
    """`research_note.conviction` / `research_note_version.conviction`
    (PLAN.md 4.10)."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AccessClassification(StrEnum):
    """`research_note.access_classification` (PLAN.md 4.10).

    Deliberately distinct from `DataClassification` (`provenance.classification`,
    what `policy_check` gates): that concept governs *licensed external data*
    entitlements, while this one describes who within the firm should see an
    *analyst-authored* note. Captured now so the field exists and is visible
    in the UI; not enforced by any route dependency in this milestone —
    Milestone 10A ships with `AUTH_ENABLED=false` and no `user`/`role` tables,
    so there is no identity to enforce it against yet. Enforcement is future
    work for the real-auth milestone, not a Milestone 10A gap.
    """

    STANDARD = "standard"
    RESTRICTED = "restricted"


class AuditEventType(StrEnum):
    """Application-level enum for `audit_event.event_type` values this
    milestone actually emits. Unlike other CHECK-constrained enums in this
    file, `audit_event.event_type`/`entity_table` are left as unconstrained
    `text` columns in the schema (see `models/audit.py`) — PLAN.md 4.12
    already scopes future audited actions across many unrelated milestones
    (watchlist changes, alert-rule changes, entitlement changes, admin
    actions, AI queries touching restricted data), and constraining the
    column now to only the values Milestone 10A emits would force a
    migration every time a later milestone adds a new audited action. Same
    reasoning as `sec_filing.form_type` staying free text."""

    RESEARCH_NOTE_CREATED = "research_note_created"
    RESEARCH_NOTE_UPDATED = "research_note_updated"
    RESEARCH_NOTE_ARCHIVED = "research_note_archived"
    # --- Milestone 10B: Research Documents ---
    RESEARCH_DOCUMENT_UPLOADED = "research_document_uploaded"
    RESEARCH_DOCUMENT_METADATA_UPDATED = "research_document_metadata_updated"
    RESEARCH_DOCUMENT_ARCHIVED = "research_document_archived"
    # --- Milestone 10C: Document Intelligence ---
    DOCUMENT_EXTRACTION_REQUESTED = "document_extraction_requested"


# --- Milestone 12A: Universal Search ---


class SearchEntityType(StrEnum):
    """The searchable entity types Universal Search groups results by
    (PLAN.md 4.13/8; Milestone 12A). Deliberately excludes
    `research_evidence`, `research_note_version`, `audit_event`, and
    `docket_document` — see `app.repositories.search_repository`'s module
    docstring for why each is excluded."""

    ISSUER = "issuer"
    SECURITY = "security"
    ALERT_EVENT = "alert_event"
    COURT_DOCKET = "court_docket"
    COURT_DOCKET_ENTRY = "court_docket_entry"
    COLLECTION = "collection"
    RESEARCH_NOTE = "research_note"
    SEC_FILING = "sec_filing"
    RESEARCH_DOCUMENT = "research_document"


# --- Milestone 10B: Research Documents + Storage ---


class ResearchDocumentType(StrEnum):
    """`research_document.document_type` (PLAN.md 4.10; Milestone 10B).

    A restrained, distressed-credit-research-relevant taxonomy — not
    exhaustive by design (`OTHER` is the deliberate escape hatch). Text+CHECK
    per ADR-014: adding an eleventh type later is an ordinary migration, not
    a schema-altering `ALTER TYPE`.
    """

    CREDIT_AGREEMENT = "credit_agreement"
    AMENDMENT = "amendment"
    EARNINGS_PRESENTATION = "earnings_presentation"
    INVESTOR_PRESENTATION = "investor_presentation"
    RESTRUCTURING_PRESENTATION = "restructuring_presentation"
    LENDER_PRESENTATION = "lender_presentation"
    BANKRUPTCY_COURT_DOCUMENT = "bankruptcy_court_document"
    FINANCIAL_MODEL_ANALYSIS = "financial_model_analysis"
    INTERNAL_RESEARCH_MEMO = "internal_research_memo"
    OTHER = "other"


# --- Milestone 10C: Document Intelligence ---


class DocumentExtractionStatus(StrEnum):
    """`document_extraction.status` (Milestone 10C).

    `NEEDS_OCR` is a distinct, intentional terminal state — a scanned/
    image-only source that the extractor genuinely cannot read is not the
    same condition as a parser crash (`FAILED`), and must not be retried
    the same way. See `app.services.document_extraction_service`'s
    validation/heuristic docstring.
    """

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    NEEDS_OCR = "needs_ocr"


class DocumentExtractionSourceType(StrEnum):
    """`document_extraction.source_type` (Milestone 10C).

    A discriminator, not a polymorphic FK — mirrors `research_evidence.
    evidence_provider` (ADR-018): one real nullable per-source FK column
    exists today (`research_document_id`); a future SEC/court source adds
    its own nullable FK column and its own member here, never a generic
    `source_id` association.
    """

    RESEARCH_DOCUMENT = "research_document"


class DocumentExtractionErrorClass(StrEnum):
    """`document_extraction.error_classification` (Milestone 10C).

    Decides retry eligibility (PLAN.md's "do not repeat the unbounded-
    retry-assumption mistake" instruction, post-2026-08-13 incident):
    `TRANSIENT` (Storage/network hiccup) is retried up to the bounded
    attempt cap; `DETERMINISTIC` (corrupt/unsupported PDF, parser
    rejection) is never retried automatically — re-attempting it would
    reliably fail again and just burn worker cycles.
    """

    TRANSIENT = "transient"
    DETERMINISTIC = "deterministic"


class DocumentChunkElementType(StrEnum):
    """`document_chunk.element_type` (Milestone 10C) — a restrained set,
    not exhaustive by design (deliberately no `OTHER`/escape hatch: every
    chunk chunking_v1 produces is unambiguously one of these four)."""

    TEXT = "text"
    HEADING = "heading"
    TABLE = "table"
    LIST = "list"
