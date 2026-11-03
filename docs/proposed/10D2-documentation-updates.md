# Milestone 10D.2 — proposed documentation updates

Status: **proposals only.** No edit has been made to `PLAN.md`, `BUILD_LOG.md`,
`ARCHITECTURE_DECISIONS.md`, or `CLAUDE.md`. Apply after ADR-021 is accepted.
`BUILD_LOG.md` and `ARCHITECTURE_DECISIONS.md` are append-only.

## ARCHITECTURE_DECISIONS.md
Append `docs/proposed/ADR-021-document-embeddings.md` (Status -> Accepted).

## PLAN.md
- **4.9 `embedding`**: replace the polymorphic table with a pointer to the
  FK-linked `document_chunk_embedding` / `document_embedding_job` /
  `public_document_approval` / `embedding_call_log` design and ADR-021, keeping
  the rule that every embedding carries provenance (`ai_extracted`) and that
  creation requires an eligibility pass (here: the allowlist).
- **Milestone Status, row 13**: split into "Gated embeddings / document retrieval
  (Milestone 10D)" and "AI Research Assistant (Milestone 13)". Mark 10D.2
  *implemented locally; migrations unapplied*.
- **Project Status / Current Milestone**: currently still reads Milestone 10B and
  never mentions 10C. Add 10C (Document Intelligence) and 10D progress.
- **Technical Debt**: add
  - TD-033 `LLMProvider.create_embeddings` stub is now superseded by
    `EmbeddingProvider`; remove the stub or keep it — decision pending.
  - TD-034 `app.db.vector_type` is a stopgap in-house column type; revisit the
    `pgvector` package when 10D.3 needs vector operators.
  - TD-035 `research_document` download/metadata routes expose content without
    authorization (extends TD-027); decision in
    `10D-endpoint-remediation-plan.md` section 3.
- **Known Issues**: add KI-005 *Python 3.12 is not installed on the primary
  development machine; project tests/lint/type-check could not be run during
  10D.2.* (resolve by the setup steps in the 10D.2 report).
- **Next Immediate Goal**: finalize provider/model, then request the database
  approval plan.

## BUILD_LOG.md
Append a "Milestone 10D.2 — local embedding pipeline (migrations unapplied)"
entry: scope, files, the persistence-failure classification gap found and fixed
by the unit tests, test results with the Python 3.14 caveat, and the explicit
list of things not done (no migration, no DB test, no provider call, no
commit).

## CLAUDE.md
- "Current Project State" still says Milestone 2 has not started. Replace with a
  pointer to PLAN.md's Project Status (stale since Milestone 3).
- Add under Provenance and Entitlement Rules: *Content may be sent to an
  external embedding vendor, or returned by retrieval, only for documents in the
  server-controlled `public_document_approval` allowlist; a client-supplied
  `confidentiality_classification` is never sufficient on its own.*
- Add under Testing Rules: *Integration tests that touch tables created by the
  10D migrations require the explicit `NEXUS_ALLOW_EMBEDDING_DB_TESTS=1`
  opt-in.*

## README.md
Add `EMBEDDINGS_ENABLED` (default false) and the other `EMBEDDING_*` variables
to the environment table, noting that only the local/test `fake` provider exists.
