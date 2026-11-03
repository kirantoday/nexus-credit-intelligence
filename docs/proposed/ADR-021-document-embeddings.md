<!--
PROPOSED — not yet appended to ARCHITECTURE_DECISIONS.md.
That file is append-only and never rewritten, so this text lives here until
engineering accepts it; on acceptance it is appended verbatim (Status changed
to "Accepted"). PLAN.md section 4.9 and roadmap row 13 must be updated in the
same change — see 10D2-documentation-updates.md.
-->

## ADR-021: Document embeddings use a dedicated FK-linked table, an allowlist-gated eligibility model, and a dedicated cost ledger — departing from PLAN.md 4.9 and the Milestone 13 roadmap placement

**Date:** 2026-10-23
**Status:** Proposed

**Context**
PLAN.md 4.9 specifies a polymorphic `embedding(source_table, source_id, vector,
model, provenance_id)` table and the roadmap (row 13) places gated embeddings
inside Milestone 13 with the AI Research Assistant. Milestone 10C produced
canonical, citable `document_chunk` rows, which makes embeddings the next
dependency for hybrid retrieval, and the retrieval layer is wanted before the
Assistant so that it can be built and evaluated independently (Milestone
10D). Reviewing the repository for 10D surfaced constraints that the original
sketch did not address:

- There is no authentication. `research_document.confidentiality_classification`
  is a client-supplied upload field (`research_documents.py`), so
  `standard` cannot be treated as proof that a document is public.
- Chunk rows copy that classification at creation time and nothing updates
  them when the parent is reclassified or archived (`research_document_repository
  .apply_metadata_update` / `archive_document` never touch chunks).
- `ai_call_log` cannot represent embedding calls without altering CHECK
  constraints on a live shared table and misdescribing the route
  (`models/ai_call_log.py`, `core/types.py`), and `app.ai.pricing` returns no
  cost unless output tokens are known.
- A fixed-width pgvector column cannot be resized in place.

**Decision**

1. *Schema.* A dedicated `document_chunk_embedding` table with a real FK to
   `document_chunk`, unique on `(chunk_id, embedding_model,
   embedding_model_version)`, replacing the polymorphic design. This follows
   ADR-018's precedent of per-source FKs over generic `source_id` columns. A
   separate `document_embedding_job` table models the work lifecycle, mirroring
   `document_extraction` (claim with `FOR UPDATE SKIP LOCKED`, bounded attempts,
   transient/deterministic classification, stale reclaim). Its uniqueness is a
   *partial* unique index over `(extraction, model, version)` limited to
   `pending`/`processing`, so history is retained and a later re-embedding can
   be enqueued.
2. *Versioning and replacement.* Each stored vector records the SHA-256
   fingerprint of the exact embedded input (template version, input type, model
   id/version/dimension, and the title + section path + chunk content). Unchanged
   fingerprint: no provider call. Same model key with a changed fingerprint
   (for example an edited document title): replaced **in place by one guarded
   upsert, only after the new vector exists and validates**; a failed call
   leaves the previous vector untouched. A new model version is a different key,
   so vectors coexist; old versions are retired only by a separately approved
   action. Batches are persisted and committed independently so a failed job
   resumes without redoing finished work.
3. *Dimension contract.* `EMBEDDING_COLUMN_DIMENSION` (code), the configured
   `EMBEDDING_DIMENSION`, the provider's declared dimension, every returned
   vector's length, the column's `vector(N)` type, and
   `CHECK (vector_dims(embedding) = dimension)` must all agree, or the batch is
   rejected. N is a **draft pilot value of 1024**, justified only because both
   leading candidate vendors support it natively; the model/vendor is not
   selected by this ADR. The migration that fixes N is held as a draft until
   the provider decision is approved.
4. *Eligibility.* Embedding and (from 10D.3) retrieval are limited to documents
   in a server-controlled allowlist, `public_document_approval`, written only
   by an operator script. Eligibility is evaluated from the current authoritative
   rows — approval not revoked, document not archived, classification `standard`
   (necessary, never sufficient), stored-file checksum equal to the approved
   checksum, extraction current and completed — and never from a chunk's copied
   classification. It is enforced at enqueue, immediately before each external
   provider call, when passages are returned, and when citations are resolved.
   The `RetrievalScope` Protocol is the seam for real identity later; no
   all-access scope exists and no authentication is invented.
5. *Provenance.* One `provenance` record per job, using the same
   calculated/AI-generated/`ai_extracted` shape `alert_synthesis_service`
   already uses, with the source document's provenance as the calculation's
   input. Embedding rows reference it. Retrieval results cite the source
   document's own provenance, not the embedding's.
6. *Cost ledger.* A dedicated `embedding_call_log`, not `ai_call_log`.
   Unknown token usage or price is stored as NULL and is never treated as zero;
   a configured cost ceiling is refused when the price is unknown.
7. *Provider abstraction.* A dedicated `EmbeddingProvider` Protocol (document
   and query methods, declared model/version/dimension, token usage, structured
   errors). The existing reserved `LLMProvider.create_embeddings` stub is left
   unchanged; removing it is a separate decision. In this milestone only a
   deterministic fake exists and the factory refuses it outside local/test.
8. *Operations.* A separate, manually invoked worker entry point behind
   `EMBEDDINGS_ENABLED=false`, with an explicit token budget required per run.
   It never touches the extraction worker; embedding failure cannot affect
   extraction status. A Railway service or schedule is a separate approval.
9. *Retrieval index.* Exact cosine scans first. HNSW is added only when measured
   corpus size or latency justifies it and filtered recall has been validated.
10. *Exposure.* Existing content-returning routes are a release blocker for
    publicly enabling retrieval; see `10D-endpoint-remediation-plan.md`.

**Alternatives considered**
- *Polymorphic `embedding` per PLAN.md 4.9:* no referential integrity, no
  per-model uniqueness, and contradicts ADR-018. Rejected.
- *Embedding columns on `document_chunk`:* couples a mutable derived artifact
  to an immutable canonical table and forces one model per chunk. Rejected.
- *Extending `ai_call_log`:* see Context. Rejected.
- *Allowing `standard` documents:* a client-supplied label is not authorization.
  Rejected in favor of the allowlist.
- *Delete-then-insert replacement:* opens a window with no valid vector and
  loses the old one if the new call fails. Rejected.
- *The `pgvector` Python package vs. an in-house column type:* 10D.2 ships a
  minimal in-house type (`app.db.vector_type`) that only declares DDL, with
  writes done through explicit `CAST(... AS vector)` SQL, so no dependency
  decision is forced yet. 10D.3 must revisit this when it needs vector
  operators.

**Consequences**
- Positive: referential integrity, per-model coexistence, safe in-place
  replacement, an auditable allowlist, a ledger that does not distort the
  existing AI cost reporting, and a testable pure core.
- Negative: more tables (four); a hard dependency on the allowlist step before
  any document can be embedded; a fixed vector width that makes a later width
  change a re-embedding project; and a one-time documentation cost updating
  PLAN.md 4.9 / row 13.
- Risks accepted: stale-reclaimed jobs can briefly overlap (made harmless by the
  guarded upsert); per-batch commits mean a half-embedded extraction exists
  between attempts (retrieval must therefore treat only completed jobs, or
  per-chunk presence, as authoritative — decided in 10D.3).
- Unchanged: the `vector` extension is shared and never created, altered, or
  dropped by Nexus migrations beyond the existing `IF NOT EXISTS` in 0001.
