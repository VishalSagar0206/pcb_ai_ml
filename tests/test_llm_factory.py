"""Unit tests for the LLM provider factory (Phase 21/28), including the
Gemini convenience defaults added so a teammate can test the whole project
with just a free Gemini API key without touching the Nemotron config. No
network calls -- these only assert what gets constructed/raised, not real
completions."""
from __future__ import annotations

import pytest

from pcb_ai.config import Settings
from pcb_ai.llm.factory import GEMINI_BASE_URL, GEMINI_DEFAULT_MODEL, get_llm_provider
from pcb_ai.llm.mock import MockLLMProvider
from pcb_ai.llm.openai_compatible import OpenAICompatibleProvider


def test_mock_provider_kind_returns_mock_provider():
    settings = Settings(caf_model_provider="mock")
    provider = get_llm_provider(settings)
    assert isinstance(provider, MockLLMProvider)


def test_default_provider_requires_base_url():
    settings = Settings(caf_model_provider="vllm", caf_model_base_url="")
    with pytest.raises(ValueError, match="CAF_MODEL_BASE_URL"):
        get_llm_provider(settings)


def test_default_provider_uses_configured_base_url_and_model():
    settings = Settings(
        caf_model_provider="vllm",
        caf_model_base_url="https://example-gateway.internal/v1",
        caf_model_api_key="key123",
        caf_model_analysis="nemotron3-super-120b",
    )
    provider = get_llm_provider(settings)
    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.model_name == "nemotron3-super-120b"


def test_gemini_provider_requires_api_key():
    settings = Settings(caf_model_provider="gemini", gemini_api_key="")
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        get_llm_provider(settings)


def test_gemini_provider_defaults_base_url_and_model_when_unset():
    # A friend's minimal .env addition: just the provider switch + their key.
    # gemini_model/gemini_base_url explicitly forced empty here so this test
    # is deterministic regardless of ambient OS environment variables (this
    # dev machine happens to have an unrelated GEMINI_MODEL env var set,
    # which pydantic-settings would otherwise pick up ahead of our default).
    settings = Settings(caf_model_provider="gemini", gemini_api_key="fake-gemini-key", gemini_model="", gemini_base_url="")
    provider = get_llm_provider(settings)

    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.model_name == GEMINI_DEFAULT_MODEL
    assert str(provider._client.base_url) == GEMINI_BASE_URL


def test_gemini_provider_respects_explicit_model_and_base_url_overrides():
    settings = Settings(
        caf_model_provider="gemini",
        gemini_api_key="fake-gemini-key",
        gemini_model="gemini-2.5-flash",
        gemini_base_url="https://my-custom-gemini-proxy.example/v1beta/openai/",
    )
    provider = get_llm_provider(settings)

    assert provider.model_name == "gemini-2.5-flash"
    assert str(provider._client.base_url) == "https://my-custom-gemini-proxy.example/v1beta/openai/"


def test_gemini_provider_coexists_with_untouched_nemotron_config():
    """The core requirement: adding GEMINI_* config to an .env that already
    has a real CAF_MODEL_BASE_URL/CAF_MODEL_API_KEY for Nemotron must not
    make Gemini accidentally use the Nemotron gateway (or vice versa)."""
    settings = Settings(
        caf_model_provider="gemini",  # switched to Gemini...
        caf_model_base_url="https://vmaimltrg1.example.internal/v1",  # ...but Nemotron config still present
        caf_model_api_key="nemotron-key-untouched",
        caf_model_analysis="nemotron3-super-120b",
        gemini_api_key="fake-gemini-key",
        gemini_model="",  # forced empty -- see note in the test above about ambient env vars
        gemini_base_url="",
    )
    provider = get_llm_provider(settings)

    assert str(provider._client.base_url) == GEMINI_BASE_URL
    assert provider.model_name == GEMINI_DEFAULT_MODEL
    # Switching CAF_MODEL_PROVIDER back to "vllm" with the same settings
    # object must still resolve to the untouched Nemotron config.
    settings.caf_model_provider = "vllm"
    nemotron_provider = get_llm_provider(settings)
    assert str(nemotron_provider._client.base_url) == "https://vmaimltrg1.example.internal/v1/"
    assert nemotron_provider.model_name == "nemotron3-super-120b"
