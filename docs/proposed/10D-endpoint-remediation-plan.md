# Milestone 10D — Existing content-endpoint remediation and compatibility plan

Status: **proposal**. Nothing here changes an existing endpoint. No existing
public endpoint is modified by 10D.2.

Decision recorded for this plan: favor **allowlist-only** access for
unauthenticated public retrieval (the earlier "R2"). The "standard document"
rule (R1) is not a substitute for authorization, and no authenticated internal
role is invented where authentication does not exist. Unsafe chunk and download
exposure is a **release blocker for publicly enabling any 10D retrieval** — not
for merging 10D.2, which adds no route.

## 1. Route-by-route

| Route | What it returns | Current checks | Exposure | Planned handling |
|---|---|---|---|---|
| `GET /api/document-extractions/{id}/chunks` (`api/routes/document_extraction.py:99`) | Full chunk text for any extraction id | Existence only | Archived, superseded, restricted and non-approved documents | **10D.3, required.** See section 2. |
| `GET /api/document-extractions/{id}/chunks/search` (`:109`) | Matching chunks' text | Existence only | Same | **10D.3, required.** Same predicate as the list route. |
| `GET /api/research-documents/{id}/download` | Short-lived signed URL to the entire PDF | Existence only | Any document, including restricted and archived | **Decision needed before public retrieval** (section 3). Not changed by 10D.3 unless approved. |
| `GET /api/research-documents/{id}`, `GET /api/research-documents` | Title, description, metadata | None | Metadata of every document | Out of 10D scope; recorded under TD-027. |
| `POST /api/research-documents/{id}/process` | Enqueues an extraction | Existence, not archived | Anyone can queue work | Out of 10D scope; noted for the auth milestone. |
| New 10D retrieval/passage routes | Passages with citations | Allowlist eligibility, four enforcement points | None by design | 10D.3+, disabled-by-default feature flag. |

Callers (verified): the only consumer of the two chunk routes is
`web/src/pages/ChunkInspectorPage.tsx`, reached from
`web/src/components/DocumentIntelligencePanel.tsx:160`, which links only to the
document's **current** extraction. Existing route tests
(`backend/tests/test_document_extraction_routes.py`) cover only 404/422, so no
leak is currently covered by a regression test.

## 2. Chunk routes: recommended mechanism

Authorization cannot depend on who is asking (no identity exists), so the
mechanism must depend on **where the server runs and what the document is**:

- *Approved public documents* (allowlist, current completed extraction, not
  archived): readable via the chunk routes in every environment.
- *All other documents*: the chunk routes return **404** (not 403, to avoid
  revealing existence) unless the server is explicitly running in an
  inspection-permitted environment — a server-side setting
  (`ENVIRONMENT in {local, test}` or an explicit, default-off
  `CHUNK_INSPECTION_ENABLED` that must be set in the server's own environment).
  A client cannot send a parameter, header, or ID that enables it.
- Even where inspection is permitted: archived documents and non-current
  extractions are excluded unless a separate explicit flag is set, so stale
  content is never an accident.

This preserves the 10C workflow for developers and local use, and deliberately
removes chunk text of non-approved documents from the deployed API until real
authentication exists. It is a **breaking change for deployed analysts** who
use the Chunk Inspector on internal documents; the alternative that avoids the
break (R1: expose any non-archived `standard` document) was rejected because
`standard` is client-supplied.

### `ChunkInspectorPage` handling

- Keep the page and route. Replace the generic "Could not load chunks" with an
  explicit "Not available for this document" state on a 404 from these routes,
  so a deliberate refusal is not mistaken for an outage.
- `DocumentIntelligencePanel`: show the "View chunks" link only when the
  document is approved for public retrieval or the deployment permits
  inspection (a new boolean on the extraction/document response, derived
  server-side).
- No frontend code changes in 10D.2.

### Regression tests required (written in 10D.3 against the live-join predicate)

For both chunk routes and every new retrieval route, each of these must return
nothing / 404 even though chunks and embeddings exist:

1. archived document;
2. superseded (non-current) extraction;
3. restricted document;
4. document reclassified `standard` -> `restricted` **after** approval and after
   chunks were created (proves the chunk's stale copy is not trusted);
5. document never approved (`standard` only);
6. approval revoked;
7. stored file replaced so its checksum no longer matches the approval;
8. extraction belonging to a different document than requested;
9. non-completed extraction (`pending`, `processing`, `failed`, `needs_ocr`);
10. positive control: an approved, current, completed document is returned.

Plus a parity test asserting the SQL predicate and
`app.retrieval.eligibility.evaluate_eligibility` agree on all of the above.

## 3. Signed download URLs

The download route is the same exposure class as the chunk routes (full text of
any document), and it backs the existing Research Documents view/download UI
for **every** internal document. Restricting it to the allowlist would break
that UI entirely in deployed environments. This is a product decision, not an
engineering default, so it is **not** made here. Options for engineering:

- A. Leave as-is and record explicitly that public retrieval does not widen
  exposure (the PDF is already retrievable), accepting the pre-existing gap until
  authentication (TD-002/TD-027).
- B. Allowlist-only in production, local/test unrestricted (same mechanism as
  section 2) — breaks deployed document viewing until authentication exists.
- C. Defer retrieval exposure until authentication exists.

Recommended: A for the 10D pilot with the gap documented, because the
retrieval pilot is limited to documents already approved as public; B or C
before any non-public document is ever made retrievable.

## 4. Phase split

| Work | Phase |
|---|---|
| Eligibility decision function, allowlist table design, no route changes | **10D.2 (done locally)** |
| Live-join SQL predicate + parity test; chunk-route enforcement; the regression suite above; Chunk Inspector 404 state | **10D.3 (separate approval)** |
| Download-route decision | **Before enabling public retrieval** |
| Authentication / per-user authorization | Out of 10D (TD-002/TD-025/TD-027) |

If the chunk-route enforcement cannot be made safe for the existing workflow,
the new retrieval capability stays disabled and the blocker is reported.
