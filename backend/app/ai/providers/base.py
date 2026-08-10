"""`LLMProvider` Protocol (PLAN.md section 10) — no application code depends
on a vendor SDK directly.

**Deviation from PLAN.md section 10's original async sketch**: `complete()`
here is synchronous. Section 10 was written before any of this existed;
Milestone 6.5 (ADR-017) is the first real implementation, and this codebase's
entire stack is deliberately synchronous today (TD-004 — sync SQLAlchemy, the
overnight monitor is a plain synchronous script). Making this one method
async would force either an `asyncio.run()` per filing or converting the
whole monitor to async for no present benefit. Revisit together with TD-004
if/when a genuinely async-shaped consumer (e.g. Milestone 13's interactive
chat over FastAPI) makes it worthwhile.

`call_tools`/`create_embeddings` are reserved for Milestone 13 and are not
called by anything in this milestone.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class CompletionRequest:
    system_prompt: str
    user_prompt: str
    max_tokens: int = 1024
    temperature: float = 0.0


@dataclass(frozen=True, slots=True)
class CompletionResponse:
    text: str
    model: str
    stop_reason: str | None = None
    # `None` for a provider/response shape that doesn't report usage — a
    # caller must not treat that as zero tokens (see app.ai.pricing).
    input_tokens: int | None = None
    output_tokens: int | None = None


class LLMProvider(Protocol):
    def complete(self, request: CompletionRequest) -> CompletionResponse:
        """A single, non-streaming text completion."""
        ...

    def call_tools(self, request: object) -> object:
        """Reserved for Milestone 13's AI Research Assistant tool layer."""
        ...

    def create_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Reserved for Milestone 13's gated embeddings."""
        ...
