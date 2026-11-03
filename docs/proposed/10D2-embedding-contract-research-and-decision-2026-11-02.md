# Milestone 10D.2 — Embedding provider research and proposed contract (2026-11-02)

Status: **research and recommendation for owner approval. Nothing here is
accepted.** ADR-021 stays provisional. No provider was called, no SDK was
installed, no code, configuration, migration or dimension was changed, and
embeddings stay disabled. This document authorizes nothing.

Research date: **2026-11-02**. Method and limits: only public official
documentation pages were read (no sign-in, no account, no API call, generic
queries only, nothing from this repository sent anywhere). Each page was
retrieved through a fetch tool that returns an AI-generated extract of the page,
not the raw page, so every figure below is **"as extracted on 2026-11-02" and
must be re-verified against the live page at implementation time.** Where the
extract said "not stated" this document records a gap; it does not fill gaps
from memory or third-party material. "Page date" is the date the page itself
shows (or its metadata), where available.

Evidence labels: **[doc]** stated by the cited official page; **[local]** read
from this repository; **[inference]** reasoning, not a documented fact;
**[gap]** not found in the official sources read.

## 1. Executive recommendation and decisions requested

**Recommended:** OpenAI `text-embedding-3-large` at **1024 dimensions**
(request parameter `dimensions`), cosine similarity.

**Fallback:** Voyage AI `voyage-4` at its **native 1024** (parameter
`output_dimension`), with `input_type` document/query.

**Main reasons for the recommendation**

1. Strongest documented data-handling position of the three: API data is not
   used for training by default; abuse-monitoring logs are kept up to 30 days;
   the embeddings endpoint is zero-data-retention *eligible* (by OpenAI
   approval); in-region processing exists for the US, EU and UAE [doc]. The
   fallback and the third candidate document training-on-inputs unless the
   customer opts out (§2.3).
2. Dimension reduction is **provider-supported** (`dimensions`), 1024 is used
   in OpenAI's own examples, and vectors are documented as length-1
   normalized with cosine recommended [doc]. No manual slicing is needed.
3. Published price is clear: $0.13 per 1M input tokens, 50% less via the
   Batch API [doc] (§3.3).
4. Smallest operational footprint: `httpx` is already a dependency [local], so
   an adapter needs no new package (an SDK would be a separate approval).

**On 1024 vs another width.** 1024 is recommended **because** it is a
documented supported width for the recommended model and for the fallback,
gives a 4 KB-per-vector footprint, and leaves headroom under typical pgvector
index width limits (to be checked against the installed pgvector version —
[gap], not verified here). It is **not** recommended merely to keep the
provisional value. Quality at 1024 versus 1536 or 3072 for credit documents is
**not evaluated** (no evaluation is authorized); if retrieval quality is a
priority the owner may prefer to authorize a small public-document evaluation
before freezing the width.

**Decisions requested**

1. Approve, amend or reject: provider/model `openai` / `text-embedding-3-large`,
   dimension 1024, cosine, per §3.
2. Decide what **public-document approval** authorizes (§4.1): sending an
   approved document's text to this named vendor under its then-current terms,
   or only after a per-vendor attestation.
3. Confirm the fallback (Voyage `voyage-4`) and, if it is ever used, the
   training opt-out requirement (§2.3).
4. Whether to authorize an optional small quality evaluation (separately).

## 2. Compact sourced comparison (at most three candidates)

No embedding vendor is named in this repository [local]: ADR-021 says only that
"both leading candidate vendors" support 1024, and `.env.example` lists
`OPENAI_API_KEY`/`AZURE_OPENAI_*` for the LLM provider, not for embeddings.
Candidates were therefore chosen as three established providers with current
text-embedding models. No quality claim is made.

### 2.1 Models and technical facts

| | OpenAI `text-embedding-3-large` | Voyage AI `voyage-4` (family: `voyage-4-large`, `voyage-4`, `voyage-4-lite`) | Cohere `embed-v4.0` / `embed-v5.0-pro`, `-fast` |
|---|---|---|---|
| Availability / alias | Listed as the default snapshot; no dated snapshots or aliases listed; deprecation status not stated [doc][gap] | Listed as current; older `voyage-3*` still accessible; alias stability and deprecation commitments not stated [doc][gap] | Listed as "Latest Model"; deprecation policy not stated [doc][gap] |
| Native dimension | 3072 [doc] | 1024 default [doc] | v4: 1536 default; v5: 2048 default [doc] |
| Configurable widths | `dimensions` parameter; models "trained to support shortening"; 256 and 1024 appear in examples; **full allowed list not stated** [doc][gap] | `output_dimension` ∈ 256, 512, 1024 (default), 2048 [doc] | v4: 256, 512, 1024, 1536; v5: 256, 512, 768, 1024, 1536, 2048; parameter `output_dimension` for v4 and newer [doc] |
| 1024 supported | Yes via `dimensions` [doc: example]; list unverified | Yes (native default) [doc] | Yes via `output_dimension` [doc] |
| Reduction provider-supported | Yes [doc]; whether the returned shortened vector is re-normalized is not stated on the page [gap] | n/a at 1024 (native) | Yes (selectable widths) [doc] |
| Normalization / metric | "normalized to length 1"; "We recommend cosine similarity" [doc] | not stated [gap] | cosine, dot, Euclidean supported; no recommendation [doc][gap] |
| Document vs query modes | None documented; same call for both [doc] | `input_type` = `document` / `query` (prepends a retrieval prompt); with/without compatible [doc] | `input_type` required: `search_document` / `search_query` (+ others) [doc]; Pro and Fast share an embedding space [doc] |
| Max input | 8192 (table "Max input"; unit implied tokens) [doc] | 32,000 tokens context [doc] | 128k tokens (v5/v4) [doc] |
| Per-request limits | max inputs and total tokens per request: not stated [gap] | max 1,000 texts; total tokens per request 120K (`voyage-4-large`), 320K (`voyage-4`), 1M (`-lite`) [doc] | max 96 texts per call [doc] |
| Over-length behavior | not stated [gap] | `truncation` default **True** (silently cuts); `False` raises an error [doc] | `truncate` default `END` (silently cuts); `NONE` errors [doc] |
| Usage reporting | response usage field not verified in the pages read [gap] | not verified [gap] | `meta.billed_units.input_tokens` [doc] |
| Rate limits | By tier; e.g. Build tier 5,000 RPM / 1,000,000 TPM for this model [doc] | Tier 1: 8M TPM / 2000 RPM for `voyage-4`; higher at $100 / $1000 billed usage [doc] | not stated on pages read [gap] |

### 2.2 Pricing (USD, standard synchronous unless noted)

| Candidate | Standard per 1M input tokens | Batch | Conditions |
|---|---|---|---|
| OpenAI `text-embedding-3-large` | **$0.13** [doc] (`-3-small` $0.02, `ada-002` $0.10) | **50% cost discount** vs synchronous; `/v1/embeddings` supported; 24h window; ≤50,000 embedding inputs per batch [doc] | Prices "per 1M tokens"; no page date; batch queue token limits are per-account [doc] |
| Voyage `voyage-4` | **$0.06** [doc] (`voyage-4-large` $0.12, `-lite` $0.02) | **33% off**, 12-hour window; free credits do not apply to batch [doc] | First 200M tokens free on the voyage-4 series (account-level) [doc]; pricing page metadata 2026-09-29 |
| Cohere `embed-v4.0` / v5 | **not published as a per-token price on the pricing page read** [gap] | not stated [gap] | Dedicated "Model Vault" instances for Embed 5: $2,000–$3,250 per instance-month (not comparable to per-token); trial keys free but not for production [doc] |

### 2.3 Data handling (all account-specific unless stated)

| | OpenAI | Voyage AI | Cohere |
|---|---|---|---|
| Training on API inputs | Not by default; only if the customer opts in [doc] | Implied **on unless the org opts out**; opt-out gives "zero-day retention"; reversible only via legal@ contact [doc, FAQ updated 2026-10-30] | **May be used unless the customer opts out** (dashboard); default not stated [doc, page dated 2025-12-05] |
| Retention | Abuse-monitoring logs up to 30 days; embeddings endpoint stores no application state [doc] | Retention period for non-opted-out data not stated [gap] | Logged prompts deleted after 30 days, with exceptions [doc]; whether this covers the Embed endpoint is not stated [gap] |
| Zero retention | Embeddings endpoint ZDR-eligible; requires OpenAI approval and extra requirements [doc] | Via training opt-out only; other options not stated [gap] | Enterprise customers only, with extra commitments [doc] |
| Regional processing | Per-project data residency via sales; in-region processing for US, EU (EEA+CH), UAE; other regions storage-only; non-US needs approvals [doc] | Not stated [gap] | Not stated; private/partner deployments keep data in the customer's environment [doc] |
| Not accessed | Contract/DPA, security pages | Terms of Service (dashboard, needs login), privacy policy, DPA, security pages (not linked) | Privacy policy, trust center details |

### 2.4 Sources (official; fetched 2026-11-02)

- OpenAI embeddings guide — https://developers.openai.com/api/docs/guides/embeddings (no page date)
- OpenAI pricing — https://developers.openai.com/api/docs/pricing (no page date)
- OpenAI model page — https://developers.openai.com/api/docs/models/text-embedding-3-large (no page date)
- OpenAI Batch API — https://developers.openai.com/api/docs/guides/batch (no page date)
- OpenAI data controls — https://developers.openai.com/api/docs/guides/your-data (no page date)
- Voyage embeddings — https://docs.voyageai.com/docs/embeddings (metadata 2026-08-10)
- Voyage pricing — https://docs.voyageai.com/docs/pricing (metadata 2026-09-29)
- Voyage rate limits — https://docs.voyageai.com/docs/rate-limits (metadata 2026-08-26)
- Voyage FAQ — https://docs.voyageai.com/docs/faq (updated 2026-10-30)
- Cohere Embed models — https://docs.cohere.com/docs/cohere-embed (no page date)
- Cohere Embed API reference — https://docs.cohere.com/reference/embed (extract covered the first ~100k of ~143k characters; the rest was not read)
- Cohere pricing — https://cohere.com/pricing (no page date)
- Cohere enterprise data commitments — https://cohere.com/enterprise-data-commitments (page dated 2025-12-05)

Published benchmark results were not collected; no quality ranking is claimed.

## 3. Proposed contract (NOT accepted)

### 3.1 Recommended: OpenAI `text-embedding-3-large` @ 1024

| Field | Proposed value |
|---|---|
| `provider_name` | `openai` |
| `model_id` | `text-embedding-3-large` |
| `model_version` | A Nexus-owned label (e.g. `alias-2026-11`) because the vendor lists no dated snapshot [doc][gap]. Record the model string the API returns, if it returns one (unverified). |
| Pinning policy | The alias cannot be pinned to a dated snapshot per the pages read [gap]. Mitigation: store a small fixed canary text's vector at approval time; a scheduled or on-demand comparison flags silent model change, which then requires a new `model_version` label and re-embedding. |
| Dimension / request parameter | 1024 / `dimensions=1024`. Verify at implementation that 1024 is accepted; the returned length must equal 1024 or the batch is rejected (already enforced by `validate_result` [local]). |
| Input modes | `embed_documents` and `embed_query` use the same request (no documented asymmetry). Fingerprints still separate `document` and `query` input types [local]. |
| Metric / normalization | Cosine (`vector_cosine_ops`, `<=>` in 10D.3). **To verify:** returned vectors have L2 norm ≈ 1 at 1024 after `dimensions` reduction. Never slice a vector manually. If the vendor does not return unit-length vectors at 1024, normalization becomes a documented, owner-approved transformation, not an assumption. |
| Input limits | Provider max 8192 tokens [doc]. Nexus chunks are ≤ 4,000 characters (about ≤ 1,000 estimated tokens) plus a short title/section header [local]. Pre-check length with the existing estimator; treat vendor rejection as terminal. **No reliance on silent truncation.** |
| Batching | Per-request input count/total tokens not stated [gap]. Keep the existing conservative batch of 64 [local] until verified at implementation; the processor already uses `min(config, provider.max_batch_size)`. |
| Pricing basis | USD per 1,000,000 input tokens: **$0.13** standard; **$0.065** via Batch API (not used by the current synchronous worker). Effective research date 2026-11-02, source above. Enter in `pricing.py` only on approval. Budget accounting uses vendor-reported input tokens; if the response does not report usage, tokens and cost stay **unknown, never zero** (existing behavior [local]). |
| Retryable errors | Network failure, timeout, 5xx, and 429 rate-limit (`EmbeddingTransientError`/`EmbeddingRateLimitError`). |
| Terminal errors | Input too long / malformed (`EmbeddingInputError`); authentication or insufficient quota (`EmbeddingAuthError`, stops the run); dimension, count or identity mismatch (`EmbeddingDimensionMismatchError`). The vendor's exact HTTP status and error-code names were **not** read (error docs not fetched) and must be verified when the adapter is built. |
| Usage reconciliation | Compare per-batch reported tokens to the estimator; large divergence is logged, never silently trusted. Vendor invoices remain the source of truth for spend. |
| Data-handling constraints | Public-approved documents only (existing gate). ZDR and data residency are **optional, account-specific, approval-gated** and not assumed. |
| Future secret variable names (names only) | `EMBEDDING_API_KEY` (new, a dedicated key separate from the LLM `OPENAI_API_KEY`); existing `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL_ID`, `EMBEDDING_MODEL_VERSION`, `EMBEDDING_DIMENSION`; optional `EMBEDDING_REQUEST_TIMEOUT_SECONDS`. No values anywhere. |

### 3.2 Fallback: Voyage `voyage-4` @ native 1024

`provider_name=voyage`, `model_id=voyage-4`, `output_dimension` left at the native
1024 (set explicitly), `input_type` = `document` for stored chunks and `query`
for queries, **`truncation=false`** so over-length input fails instead of being
cut. Max 1,000 texts per request (cap Nexus batches lower). Price $0.06 per 1M
(batch 33% off; free credits do not apply to batch). Tradeoffs: lower price and
no dimension reduction needed, but the documented default is data use for
training unless the organization opts out, normalization and alias stability are
[gap], and the privacy/DPA documents were not available to read. Using it would
require the opt-out (or a contract) **before** any text is sent.

### 3.3 Cost illustrations (hypothetical volumes; not corpus size or spend)

Volumes: 1,000,000 and 10,000,000 document tokens; and a separate query example
of 1,000 queries × 100 tokens = 100,000 query tokens. Formula: tokens ÷
1,000,000 × price per 1M.

| Scenario | OpenAI 3-large std ($0.13) | OpenAI 3-large batch ($0.065) | Voyage voyage-4 std ($0.06) | Voyage voyage-4 batch ($0.0402) |
|---|---|---|---|---|
| 1M document tokens | $0.13 | $0.065 | $0.06 | $0.0402 |
| 10M document tokens | $1.30 | $0.65 | $0.60 | $0.402 |
| 100k query tokens (synchronous only) | $0.013 | n/a (batch is async) | $0.006 | n/a |

Notes: Voyage standard calls may fall within the 200M-token free allowance
(account-specific, not applied to batch). Cohere cannot be priced because no
per-token price was found [gap]. Nexus's own token estimate is `len ÷ 4`; real
billed tokens depend on the vendor's tokenizer and on the "Document/Section"
header added to each chunk, so costs and limits must be re-verified at
implementation time. Re-embedding after a model or dimension change repeats the
document cost.

### 3.4 What changes if the model or dimension later changes

- **Fingerprint / cache isolation:** model id, model version and dimension are
  hashed into every fingerprint [local], so a change never reuses stale
  vectors; all affected chunks are re-embedded (and re-paid).
- **Schema:** the embedding column is `vector(N)` with
  `CHECK (vector_dims(embedding) = dimension)` and a unique key on
  (chunk, model, version) [local]. A new model at the **same** width can
  coexist under a new version label. A **different** width needs a schema
  change (new column or table, or an alteration whose feasibility depends on the
  data present and on the live server — not asserted here either way).
- **Document/query compatibility:** query vectors must come from the same model
  and width as the stored document vectors. Voyage documents that vectors made
  with and without `input_type` are compatible, and Cohere documents that
  Embed 5 Pro and Fast share a space [doc]; OpenAI documents no cross-model
  compatibility, so none is assumed.

## 4. Data-handling uncertainties and blockers

1. **What does a public-document approval authorize?** [local] ADR-021 says the
   allowlist limits embedding to documents that "may be sent to an external
   embedding vendor"; the operator script records a free-text `approval_basis`
   and `approved_by`, the checksum and lineage, but **not which vendor or terms**
   the approval covers. A document being public does not by itself settle
   copyright, site terms-of-use (for example documents obtained under a
   service's access conditions), or a vendor's retention and training terms.
   **Owner decision:** (a) approval means "this document may be sent to any
   vendor the owner has separately approved", or (b) each approval must name the
   vendor/contract scope (this would be a later, separately approved schema or
   process change).
2. Training-on-inputs defaults differ by vendor (§2.3); the fallback requires
   an opt-out before use.
3. OpenAI ZDR, data residency and rate-limit tier are **account-specific**; they
   need the account owner to confirm in the vendor console or contract. Not
   accessed here.
4. Evidence gaps: OpenAI — allowed `dimensions` values, per-request limits,
   over-length behavior, usage field name, alias stability/deprecation,
   whether a shortened vector is re-normalized; Voyage — normalization, alias
   stability, region, privacy/DPA; Cohere — per-token price, training default
   for Embed, region.
5. Blockers to any real call: owner approval of the contract; an account and
   key (owner-provisioned, never committed); separately authorized paid usage
   with a budget cap.

## 5. Later implementation scope (NOT approved; embeddings stay disabled)

| Component | Proposed work |
|---|---|
| `backend/app/embeddings/openai_provider.py` (new) | `EmbeddingProvider` over `httpx` (no new dependency; an SDK would be a separate dependency approval); `dimensions=1024`; timeouts; error mapping; usage extraction; transport injectable so tests use a mock. |
| `backend/app/embeddings/factory.py` | Register `openai`; require key, model id, dimension equal to `EMBEDDING_COLUMN_DIMENSION`; keep refusing unknown providers and keep fake local/test only. |
| `backend/app/config.py`, `.env.example` | `embedding_api_key` (secret, optional, never logged), request timeout; embeddings remain off by default. |
| `backend/app/embeddings/pricing.py` | Add the `openai` / `text-embedding-3-large` entry with citation and date; tests that unknown stays `None`. |
| `backend/app/embeddings/dimensions.py`, draft `0022` | Unchanged if 1024 is approved (remove "DRAFT pilot" wording only on acceptance); if another width is approved change both and the existing parity test together. |
| `fingerprint.py`, `processor.py`, `budget.py` | No change expected; confirm batch sizing and the unknown-usage path with the new adapter. |
| pgvector resolution | Verify the extension's schema and the migration and application roles' `search_path`; decide on schema-qualifying `vector`/`vector_dims` in the column type, the CHECK, and the repository `CAST(:embedding AS vector)` (see the addendum §2.7). |
| Tests | Mocked adapter tests: success, wrong width, wrong count, 429, 5xx, 400 too long, auth/quota, missing usage, no network without injection; factory and pricing tests; extend negative eligibility tests (archived, superseded, restricted, reclassified, revoked, checksum mismatch, incomplete extraction, mismatched extraction) so no ineligible text ever reaches the provider; a test that the adapter is never built when embeddings are disabled. |
| Docs | Accept ADR-021 only after owner approval; `PLAN.md`/`BUILD_LOG.md` only at milestone completion. |

**Unknowns that need a named-environment read-only preflight** (not done; no
database contact): installed pgvector version and the extension's schema; index
dimension limits for the planned retrieval index; migration and application
role `search_path`; currently applied revision; backup/PITR confirmation.

**Required validation before live use:** the unit and mock tests above; a
full implementation review (a WIP checkpoint and a pattern scan are **not** a
comprehensive code review); one separately authorized, budget-capped live
smoke call to confirm width, norm, usage and error behavior; an optional
public-document quality evaluation.

## 6. Download-policy clarification

A dated clarification was added to the final addendum (§1.8 acceptance tests)
replacing the earlier statement that extraction states deny signed download:
chunk list/search need the current completed extraction and live eligibility;
signed download uses the approved source-PDF policy and is not denied by
extraction state alone; archive, classification, revocation and checksum rules
still apply; the chunk inspection flag never grants download access. These
rules are **planned, not implemented**.

## 7. Next actions and remaining gates (ordered; each separate, none granted)

Security and exposure (separately scoped authorization, **prioritized before
any public use**): the anonymous process route (unbounded enqueue, forged
`requested_by`), restricted-document metadata exposure, and the adjacent
anonymous mutation routes (upload, metadata patch, archive). Download
restrictions and the local-inspection safeguards are planned, not implemented.
Implementation review remains required before live use.

1. Owner decision on this contract and on the approval-meaning question (§4.1).
2. Approval of a concrete implementation scope (§5) — code changes.
3. Vendor account, key and data-terms confirmation by the owner (ZDR,
   residency, any opt-out) — no keys in the repository.
4. Security authorization and implementation (separate scope).
5. Policy exception and provisioning for an isolated integration environment
   (conflicts with CLAUDE.md and ADR-013 until excepted), or the shared-schema
   alternative.
6. Named-environment read-only preflight.
7. Migration 0021, then 0022 (only after the dimension is final), each its own
   approval.
8. Integration test execution and cleanup scope.
9. First live embedding call (paid, budget-capped).
10. 10D.3 retrieval work.

10D.2 stays open; migration 0022 stays blocked until step 1 is resolved; no
migration is authorized.
