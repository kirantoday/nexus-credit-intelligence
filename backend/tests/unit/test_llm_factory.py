"""Unit tests for `app/ai/factory.py` (PLAN.md 24.7).

No network — only tests configuration validation and error behavior.
"""

from __future__ import annotations

import pytest

from app.ai.factory import LLMConfigurationError, get_llm_provider
from app.ai.providers.anthropic_provider import AnthropicProvider
from app.config import Settings


def _settings(**overrides: object) -> Settings:
    return Settings(**overrides)  # type: ignore[arg-type]


def test_anthropic_provider_resolves_with_key_configured() -> None:
    settings = _settings(llm_provider="anthropic", anthropic_api_key="sk-test-key")

    provider = get_llm_provider(settings)

    assert isinstance(provider, AnthropicProvider)


def test_anthropic_provider_raises_clearly_without_key() -> None:
    settings = _settings(llm_provider="anthropic", anthropic_api_key=None)

    with pytest.raises(LLMConfigurationError, match="ANTHROPIC_API_KEY"):
        get_llm_provider(settings)


def test_openai_provider_raises_not_implemented_even_with_a_key_present() -> None:
    """A configured OPENAI_API_KEY must never make LLM_PROVIDER=openai work —
    only LLM_PROVIDER selects the implementation; presence of unrelated
    provider keys is irrelevant."""
    settings = _settings(llm_provider="openai", openai_api_key="sk-unused")

    with pytest.raises(LLMConfigurationError, match="not implemented"):
        get_llm_provider(settings)


def test_azure_openai_provider_raises_not_implemented() -> None:
    settings = _settings(llm_provider="azure_openai")

    with pytest.raises(LLMConfigurationError, match="not implemented"):
        get_llm_provider(settings)


def test_unknown_provider_raises_clearly() -> None:
    settings = _settings(llm_provider="some_future_vendor")

    with pytest.raises(LLMConfigurationError, match="unknown LLM_PROVIDER"):
        get_llm_provider(settings)


def test_missing_anthropic_key_never_silently_falls_back_to_another_provider() -> None:
    """A misconfigured selected provider must fail loudly, not silently
    resolve to whichever provider happens to have a key set."""
    settings = _settings(
        llm_provider="anthropic", anthropic_api_key=None, openai_api_key="sk-present"
    )

    with pytest.raises(LLMConfigurationError):
        get_llm_provider(settings)
