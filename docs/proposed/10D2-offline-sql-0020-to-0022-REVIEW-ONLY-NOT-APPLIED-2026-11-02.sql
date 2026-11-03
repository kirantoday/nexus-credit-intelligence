-- ============================================================================
-- REVIEW ONLY -- NOT APPLIED -- DO NOT RUN AGAINST ANY DATABASE
-- Rendered offline on 2026-11-02 by `alembic ... --sql` (no connection; socket
-- connects were blocked in the wrapper). Source: backend/alembic/drafts/0021
-- and 0022 (copied to a scratch script dir; repo files untouched).
-- Offline SQL is NOT proof of live compatibility or safe rollback.
-- vector(1024) is a PROVISIONAL width -- an unresolved decision blocks 0022.
-- ============================================================================

-- ########## UPGRADE 0020 -> 0022 ##########
BEGIN;

-- Running upgrade 0020 -> 0021

CREATE TABLE nexus.public_document_approval (
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    research_document_id UUID NOT NULL,
    approved_raw_payload_checksum TEXT NOT NULL,
    source_url TEXT NOT NULL,
    source_sha256 TEXT,
    converter_name TEXT,
    converter_version TEXT,
    page_reference_basis TEXT NOT NULL,
    approval_basis TEXT NOT NULL,
    approved_by TEXT NOT NULL,
    approved_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL,
    revoked_at TIMESTAMP WITH TIME ZONE,
    revoked_by TEXT,
    PRIMARY KEY (id),
    CONSTRAINT ck_public_document_approval_page_reference_basis CHECK (page_reference_basis IN ('original', 'converted_pdf')),
    CONSTRAINT ck_public_document_approval_checksum_format CHECK (approved_raw_payload_checksum ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_public_document_approval_source_sha256_format CHECK (source_sha256 IS NULL OR source_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_public_document_approval_derived_requires_lineage CHECK (page_reference_basis = 'original' OR (source_sha256 IS NOT NULL AND converter_name IS NOT NULL AND converter_version IS NOT NULL)),
    CONSTRAINT ck_public_document_approval_revocation_pair CHECK ((revoked_at IS NULL) = (revoked_by IS NULL)),
    CONSTRAINT ck_public_document_approval_basis CHECK (length(approval_basis) > 0),
    FOREIGN KEY(research_document_id) REFERENCES nexus.research_document (id)
);

CREATE INDEX ix_public_document_approval_research_document_id ON nexus.public_document_approval (research_document_id);

CREATE UNIQUE INDEX ux_public_document_approval_one_active ON nexus.public_document_approval (research_document_id) WHERE revoked_at IS NULL;

UPDATE nexus.alembic_version SET version_num='0021' WHERE nexus.alembic_version.version_num = '0020';

-- Running upgrade 0021 -> 0022

CREATE TABLE nexus.document_embedding_job (
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    research_document_id UUID NOT NULL,
    document_extraction_id UUID NOT NULL,
    embedding_provider TEXT NOT NULL,
    embedding_model TEXT NOT NULL,
    embedding_model_version TEXT NOT NULL,
    dimension INTEGER NOT NULL,
    status TEXT DEFAULT 'pending' NOT NULL,
    attempt_count INTEGER DEFAULT 0 NOT NULL,
    error_classification TEXT,
    error_message TEXT,
    status_note TEXT,
    chunk_total INTEGER,
    chunks_embedded INTEGER DEFAULT 0 NOT NULL,
    chunks_replaced INTEGER DEFAULT 0 NOT NULL,
    provenance_id UUID,
    requested_by TEXT,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT ck_document_embedding_job_status CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'blocked_ineligible')),
    CONSTRAINT ck_document_embedding_job_error_classification CHECK (error_classification IS NULL OR error_classification IN ('transient', 'deterministic')),
    CONSTRAINT ck_document_embedding_job_dimension CHECK (dimension > 0),
    CONSTRAINT ck_document_embedding_job_attempt_count CHECK (attempt_count >= 0),
    FOREIGN KEY(research_document_id) REFERENCES nexus.research_document (id),
    FOREIGN KEY(document_extraction_id) REFERENCES nexus.document_extraction (id),
    FOREIGN KEY(provenance_id) REFERENCES nexus.provenance (id)
);

CREATE INDEX ix_document_embedding_job_status ON nexus.document_embedding_job (status);

CREATE INDEX ix_document_embedding_job_document_extraction_id ON nexus.document_embedding_job (document_extraction_id);

CREATE INDEX ix_document_embedding_job_research_document_id ON nexus.document_embedding_job (research_document_id);

CREATE UNIQUE INDEX ux_document_embedding_job_one_active_per_target ON nexus.document_embedding_job (document_extraction_id, embedding_model, embedding_model_version) WHERE status IN ('pending', 'processing');

CREATE TABLE nexus.document_chunk_embedding (
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    chunk_id UUID NOT NULL,
    job_id UUID NOT NULL,
    embedding_model TEXT NOT NULL,
    embedding_model_version TEXT NOT NULL,
    dimension INTEGER NOT NULL,
    content_fingerprint TEXT NOT NULL,
    embedding vector(1024) NOT NULL,
    provenance_id UUID NOT NULL,
    revision INTEGER DEFAULT 1 NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT ck_document_chunk_embedding_fingerprint_format CHECK (content_fingerprint ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_document_chunk_embedding_dim CHECK (vector_dims(embedding) = dimension),
    CONSTRAINT ck_document_chunk_embedding_revision CHECK (revision >= 1),
    FOREIGN KEY(chunk_id) REFERENCES nexus.document_chunk (id),
    FOREIGN KEY(job_id) REFERENCES nexus.document_embedding_job (id),
    FOREIGN KEY(provenance_id) REFERENCES nexus.provenance (id)
);

CREATE UNIQUE INDEX ux_document_chunk_embedding_chunk_model ON nexus.document_chunk_embedding (chunk_id, embedding_model, embedding_model_version);

CREATE INDEX ix_document_chunk_embedding_job_id ON nexus.document_chunk_embedding (job_id);

CREATE TABLE nexus.embedding_call_log (
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    job_id UUID,
    purpose TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    model_version TEXT,
    batch_size INTEGER NOT NULL,
    input_tokens INTEGER,
    estimated_cost_usd NUMERIC(12, 6),
    latency_ms INTEGER,
    success BOOLEAN NOT NULL,
    retry_count INTEGER DEFAULT 0 NOT NULL,
    error_classification TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT ck_embedding_call_log_purpose CHECK (purpose IN ('document', 'query')),
    CONSTRAINT ck_embedding_call_log_batch_size CHECK (batch_size > 0),
    FOREIGN KEY(job_id) REFERENCES nexus.document_embedding_job (id)
);

CREATE INDEX ix_embedding_call_log_job_id ON nexus.embedding_call_log (job_id);

UPDATE nexus.alembic_version SET version_num='0022' WHERE nexus.alembic_version.version_num = '0021';

COMMIT;



-- ########## DOWNGRADE 0022 -> 0020 (DESTRUCTIVE: drops tables and their data) ##########
BEGIN;

-- Running downgrade 0022 -> 0021

DROP INDEX nexus.ix_embedding_call_log_job_id;

DROP TABLE nexus.embedding_call_log;

DROP INDEX nexus.ix_document_chunk_embedding_job_id;

DROP INDEX nexus.ux_document_chunk_embedding_chunk_model;

DROP TABLE nexus.document_chunk_embedding;

DROP INDEX nexus.ux_document_embedding_job_one_active_per_target;

DROP INDEX nexus.ix_document_embedding_job_research_document_id;

DROP INDEX nexus.ix_document_embedding_job_document_extraction_id;

DROP INDEX nexus.ix_document_embedding_job_status;

DROP TABLE nexus.document_embedding_job;

UPDATE nexus.alembic_version SET version_num='0021' WHERE nexus.alembic_version.version_num = '0022';

-- Running downgrade 0021 -> 0020

DROP INDEX nexus.ux_public_document_approval_one_active;

DROP INDEX nexus.ix_public_document_approval_research_document_id;

DROP TABLE nexus.public_document_approval;

UPDATE nexus.alembic_version SET version_num='0020' WHERE nexus.alembic_version.version_num = '0021';

COMMIT;
