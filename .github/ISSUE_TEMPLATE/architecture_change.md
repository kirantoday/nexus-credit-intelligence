---
name: Architecture change proposal
about: Propose a change to the frozen Version 1.0 architecture
title: "[Architecture Change] "
labels: architecture
---

> The Version 1.0 architecture (`PLAN.md` §1–23) is frozen. Per `CLAUDE.md` §
> Architecture Change Policy, no material architecture change happens silently —
> it stops, gets proposed here, and waits for approval before implementation.

## Context

What's currently true (the relevant part of `PLAN.md`), and what's forcing this
change — a real constraint discovered during implementation, not a preference.

## Proposed change

The specific change: new/modified table, new provider contract, new infrastructure
dependency, changed data flow, etc.

## Alternatives considered

What else could solve this, and why they were rejected.

## Tradeoffs

What this change costs (complexity, migration effort, new dependency, scope) versus
what it buys.

## Impact on PLAN.md

Which sections need updating if this is approved (data model, module list, build
order, environment variables, etc.).

## ADR requirement

- [ ] This change requires a new entry in `ARCHITECTURE_DECISIONS.md`.
- [ ] Draft ADR content is included below, or in a linked PR.

## Migration implications

Does this require an Alembic migration, a data backfill, a breaking API change, or
coordination with anything already deployed?

## Approval status

- [ ] Proposed
- [ ] Reviewed
- [ ] Approved — implementation may proceed
- [ ] Rejected — reason recorded below

**Approved by / date:**
