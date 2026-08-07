# Nexus Credit Intelligence — Vision

This is the permanent, authoritative source for why Nexus exists, who it is
for, and the product philosophy that governs every future feature decision.
`PLAN.md` is the execution roadmap — architecture, data model, milestone
status; it points here rather than duplicating this content. `CLAUDE.md`
enforces the engineering discipline that makes this vision achievable
(provenance discipline, real providers, milestone-by-milestone stop-and-wait
review). This document does not change engineering discipline — if
anything, it raises the bar, since Nexus is now being built as the
foundation of a commercial institutional research platform, not a
demonstration.

Established 2026-08-06, after Milestone 6.5, on explicit direction: *"This
project has now evolved beyond an interview demonstration... think and
build as though Nexus Credit Intelligence is becoming a commercial
institutional research platform used by distressed-credit hedge funds."*

---

## Why Nexus exists

Distressed-credit and leveraged-finance investment professionals spend a
disproportionate share of their time on manual research mechanics — pulling
filings, cross-referencing court dockets, reconciling capital structures
across sources, re-deriving a status they could have gotten from a single
trustworthy screen. None of that manual work makes an investment decision
better; it only delays reaching one. Nexus exists to collapse that manual
work into a single, trustworthy surface, so an analyst's time goes into
judgment, not retrieval.

The test for every feature, always: **does this reduce manual work for an
investment professional while increasing confidence in the underlying
research?** Technology is never added because it is interesting — only
because it improves an analyst's actual daily workflow. When a milestone's
design is ambiguous, resolve the ambiguity toward how a distressed-credit
team actually works, not toward what is technically convenient.

## Target users

Investment professionals covering distressed and leveraged credit: analysts
and portfolio managers at hedge funds, credit funds, and similar
institutions, who need to move from "something changed" to "here is the
evidence, here is where it sits in the capital structure, here is what I
need to decide" as fast as the underlying facts allow — without ever having
to wonder whether a number on the screen is real, sourced, calculated, or
guessed.

## Product philosophy

Every fact Nexus displays carries provenance: which provider produced it,
the source record, when it was reported, when it was retrieved, whether
it's live/cached/stale, whether it's a reported fact or a calculated one,
and its classification (public/licensed/synthetic/AI-extracted). A value
that can't carry that lineage does not get displayed. This isn't a
technical nicety — it is the entire basis on which an analyst can trust a
number enough to act on it, and it is non-negotiable as Nexus grows.

**Prefer honesty over completeness.** An empty state that says "no filings
on file for this issuer yet" is correct and useful. A fabricated filing is
not, no matter how plausible it looks. This governs everything from a
single missing field (leave it null, never guess) to an entire feature
(don't build a capability the underlying data can't honestly support).

## Research Operating System vision

Nexus is not a set of independent pages. It is one continuous workflow an
analyst moves through every day:

```
Morning Research Brief → Research Universe → Issuer → Capital Structure
   → Evidence → Supporting Documents → Research Notes → Investment Decision
```

The analyst logs in each morning and immediately sees what happened
overnight — new filings, court developments, macro changes, potential
distress events, prioritized by what actually matters to their coverage —
without having to go find it themselves. From there, every drill-down stays
inside the same chain: a Research Universe groups the issuers a
distressed-credit team actually tracks together; an issuer's detail page is
the analyst's own questions ("what debt exists, where does it sit, what
changed recently, what happened in court, where did this come from") rather
than a database schema; capital structure, evidence, and documents are all
one click from wherever the analyst currently is, not a separate
destination they have to navigate to and back from.

Every future feature should be framed against where it sits in this chain,
not designed as an isolated page. A new provider, a new page, or a new AI
capability that doesn't map onto a step in this chain is a signal to
reconsider its scope before building it.

## AI philosophy

Facts are created only by verified providers — SEC, CourtListener, OpenFIGI,
FRED, TRACE, ratings, Bloomberg, and future licensed providers. **AI never
invents a fact.** Canonical facts produce Research Evidence; Research
Evidence produces Alerts. AI's role is downstream of that chain: it
explains, summarizes, classifies, compares, prioritizes, and connects
already-verified facts. It never asserts a conclusion beyond what the
underlying evidence actually supports, and it fails closed — a malformed or
ungrounded AI response falls back to deterministic, evidence-only wording
rather than silently becoming an alert. This discipline, proven in
Milestone 6.5's evidence-review layer and Milestone 7's docket evidence
pipeline, governs every future AI-touching feature: Universal Search
ranking, the AI Research Assistant, investment memo generation, and
whatever comes after those.

## Provider philosophy

Every provider must answer a specific business question an analyst actually
asks:

| Provider | Question it answers |
|---|---|
| SEC | What did the company disclose? |
| CourtListener | What happened in court? |
| OpenFIGI | What security is this? |
| TRACE | How is the market trading this instrument? |
| FRED | What macro environment surrounds this issuer? |
| Bloomberg | What is today's market data? |

A provider is never integrated simply because an API exists. Each new
provider extends the same evidence-first pipeline (`ProviderName` →
Provider DTO → Normalizer → Canonical Domain Object → Repository →
`research_evidence`/Alerts) already proven twice — once for SEC filings
(Milestone 6.5), once for CourtListener dockets (Milestone 7) — rather than
inventing its own parallel path.

## Long-term workflow

The full research workflow Nexus is building toward:

- **Research Universes** — curated, organization-wide coverage groups
- **Credit Universe** — the screenable table of every bond and loan tracked
- **Issuer Workspace** — the analyst's per-issuer research surface
- **Capital Structure** — where an instrument sits, what's senior to what
- **Morning Research Brief** — what changed overnight, prioritized
- **Research Evidence** — the provenanced signals underneath every alert
- **Provider-integrated alerts** — SEC filings and court dockets today,
  ratings/macro/TRACE next
- **Court intelligence** — CourtListener docket monitoring (Milestone 7)
- **Market intelligence** — TRACE, benchmark rates, spreads
- **Document intelligence** — research notes, uploaded documents, extraction
- **RAG** — grounded retrieval over an issuer's full evidentiary record
- **Governed AI assistants** — the AI Research Assistant, scoped by the same
  entitlement/provenance rules as every other surface
- **Investment memo generation** — the workflow's eventual endpoint: from
  evidence to a defensible written thesis

## Future product direction

Document Intelligence, RAG, Embeddings, and Agentic Research (the AI
Research Assistant, PLAN.md's final Version 1 milestone) are **mandatory
scope**, not an optional stretch goal, even though they are scheduled last.
Every milestone between now and then should be built so that this final
milestone has real, provenanced, well-structured evidence to work with —
not a redesign it has to wait for.

Beyond Version 1: broader automatic provider coverage where a real
constraint currently requires curated linking (e.g. CourtListener docket
discovery, ADR-019), additional licensed data providers activated behind
the existing entitlement engine rather than a new one, and continued
expansion of the same evidence → alert → brief chain to whatever new
signal source an analyst's actual workflow next requires.
