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
