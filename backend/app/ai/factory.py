"""Resolves `LLM_PROVIDER` to a concrete `LLMProvider` implementation (PLAN.md 24.7).

Validates only the selected provider's own required configuration — an
unconfigured `OPENAI_API_KEY` never blocks booting with `LLM_PROVIDER=anthropic`.
Never falls back to a different provider; never logs a key.
"""

from __future__ import annotations

from app.ai.model_router import AiCallBudget, ModelRouter, default_routing_config
from app.ai.providers.anthropic_provider import AnthropicProvider
from app.ai.providers.base import LLMProvider
from app.config import Settings


class LLMConfigurationError(Exception):
    """The configured `LLM_PROVIDER` is missing required credentials, or
    names a provider that isn't implemented yet."""


def get_llm_provider(settings: Settings, *, model: str | None = None) -> LLMProvider:
    """Returns a single-model provider bound to `model` (default:
    `settings.anthropic_model`, i.e. Sonnet) — used directly by callers
    that don't go through `build_model_router` (the one-off reclassify
    script, and `app.ai.model_router.ModelRouter`'s own construction of
    its Haiku/Sonnet providers below)."""
    provider_name = settings.llm_provider

    if provider_name == "anthropic":
        if not settings.anthropic_api_key:
            raise LLMConfigurationError(
                "LLM_PROVIDER=anthropic requires ANTHROPIC_API_KEY to be set"
            )
        return AnthropicProvider(
            api_key=settings.anthropic_api_key, model=model or settings.anthropic_model
        )

    if provider_name == "openai":
        raise LLMConfigurationError(
            "LLM_PROVIDER=openai is selected but not implemented yet (PLAN.md section 10)"
        )

    if provider_name == "azure_openai":
        raise LLMConfigurationError(
            "LLM_PROVIDER=azure_openai is selected but not implemented yet (PLAN.md section 10)"
        )

    if provider_name == "ollama":
        raise LLMConfigurationError(
            "LLM_PROVIDER=ollama is selected but not implemented yet (PLAN.md section 10)"
        )

    raise LLMConfigurationError(f"unknown LLM_PROVIDER: {provider_name!r}")


def build_model_router(settings: Settings, *, budget: AiCallBudget | None = None) -> ModelRouter:
    """The one sanctioned way to obtain a routed Haiku/Sonnet AI reviewer
    (PLAN.md Milestone 7.5.3) — every real caller (discovery/backfill CLI,
    the nightly monitor, CourtListener docket sync, the reclassify script)
    goes through this, never `get_llm_provider` directly, so a model id or
    a budget can never silently diverge between callers.

    `settings.ai_routing_enabled=False` collapses to Sonnet-only, no Haiku
    attempt ever made — an explicit opt-out, not a silent one, still fully
    budget-enforced and logged.
    """
    sonnet = get_llm_provider(settings, model=settings.ai_sonnet_model_id)
    haiku = (
        get_llm_provider(settings, model=settings.ai_haiku_model_id)
        if settings.ai_routing_enabled
        else None
    )
    return ModelRouter(
        haiku=haiku,
        sonnet=sonnet,
        config=default_routing_config(settings),
        budget=budget if budget is not None else AiCallBudget(),
    )
