"""Anthropic implementation of `LLMProvider` (PLAN.md section 10, ADR-017).

The only implemented provider this milestone. `call_tools`/`create_embeddings`
are not used by anything in Milestone 6.5 and raise clearly rather than
silently doing nothing.
"""

from __future__ import annotations

import anthropic

from app.ai.providers.base import CompletionRequest, CompletionResponse

# Live-caught real gap (Milestone 7, see BUILD_LOG.md): every HTTP-based
# provider client in this codebase (SEC/OpenFIGI/FRED/CourtListener) sets an
# explicit, bounded `timeout_seconds` via `ThrottledHttpClient`. The
# Anthropic SDK client had none, defaulting to its own library default
# (several minutes) — a real overnight docket sync stalled with no error and
# no progress for 25+ minutes on what looked like a hung AI-review call, with
# nothing in this codebase bounding it. 60s matches the timeout this
# milestone already set for CourtListener, and is generous for a single
# completion call that Milestone 6.5's live testing consistently finished in
# a few seconds.
_REQUEST_TIMEOUT_SECONDS = 60.0


class AnthropicProvider:
    def __init__(self, *, api_key: str, model: str) -> None:
        self._client = anthropic.Anthropic(api_key=api_key, timeout=_REQUEST_TIMEOUT_SECONDS)
        self._model = model

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        # `temperature` is deliberately not forwarded: confirmed live against
        # the configured model that it rejects the parameter outright
        # ("`temperature` is deprecated for this model", HTTP 400) rather
        # than silently ignoring it. `CompletionRequest.temperature` stays in
        # the domain type for providers that do accept it.
        response = self._client.messages.create(
            model=self._model,
            max_tokens=request.max_tokens,
            system=request.system_prompt,
            messages=[{"role": "user", "content": request.user_prompt}],
        )
        text = "".join(
            block.text for block in response.content if isinstance(block, anthropic.types.TextBlock)
        )
        return CompletionResponse(text=text, model=response.model, stop_reason=response.stop_reason)

    def call_tools(self, request: object) -> object:
        raise NotImplementedError("reserved for Milestone 13")

    def create_embeddings(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError("reserved for Milestone 13")
