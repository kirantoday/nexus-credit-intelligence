"""AI layer (PLAN.md section 24.7, ADR-017).

Pulled forward from Milestone 13, scoped narrowly to backend-only evidence
classification for the Overnight Distress Filing Monitor — no chat, no RAG,
no user-facing assistant, no embeddings. `providers/` holds the `LLMProvider`
Protocol (PLAN.md section 10) and its Anthropic implementation; `factory.py`
resolves `LLM_PROVIDER` to a concrete provider; `llm_gate.py` wraps the
existing `policy_check` choke point; `evidence_review.py` is this milestone's
actual capability.
"""

from __future__ import annotations
