"""Resolves `LLM_PROVIDER` to a concrete `LLMProvider` implementation (PLAN.md 24.7).

Validates only the selected provider's own required configuration — an
unconfigured `OPENAI_API_KEY` never blocks booting with `LLM_PROVIDER=anthropic`.
Never falls back to a different provider; never logs a key.
"""

from __future__ import annotations

from app.ai.providers.anthropic_provider import AnthropicProvider
from app.ai.providers.base import LLMProvider
from app.config import Settings


class LLMConfigurationError(Exception):
    """The configured `LLM_PROVIDER` is missing required credentials, or
    names a provider that isn't implemented yet."""


def get_llm_provider(settings: Settings) -> LLMProvider:
    provider_name = settings.llm_provider

    if provider_name == "anthropic":
        if not settings.anthropic_api_key:
            raise LLMConfigurationError(
                "LLM_PROVIDER=anthropic requires ANTHROPIC_API_KEY to be set"
            )
        return AnthropicProvider(api_key=settings.anthropic_api_key, model=settings.anthropic_model)

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
