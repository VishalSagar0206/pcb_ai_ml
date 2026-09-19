"""Factory for constructing the configured LLM provider (Phase 21/28)."""
from __future__ import annotations

from typing import Optional

from pcb_ai.config import Settings, get_settings
from pcb_ai.llm.base import BaseLLMProvider
from pcb_ai.llm.mock import MockLLMProvider
from pcb_ai.llm.openai_compatible import OpenAICompatibleProvider

# Google publishes an official OpenAI-wire-format-compatible endpoint for
# Gemini (https://ai.google.dev/gemini-api/docs/openai) -- same request/
# response shape our OpenAICompatibleProvider already speaks to the
# configured Nemotron gateway, so Gemini needs no new provider class, just
# a different base_url/model/api_key. This lets a friend/teammate test the
# whole project with only a free Gemini API key (https://aistudio.google.com/
# apikey), without touching your CAF_MODEL_* Nemotron configuration --
# CAF_MODEL_PROVIDER=gemini is purely additive/alternative, selected via
# .env, never the implicit default. Uses the dedicated GEMINI_* settings
# fields (not CAF_MODEL_BASE_URL/CAF_MODEL_API_KEY) specifically so both
# configs can coexist in the same .env without one clobbering the other.
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
# "flash-lite" tier deliberately chosen over the newer/flagship "flash"
# models: live testing during this feature's development showed
# gemini-3.6-flash's free tier caps at just 20 requests/day per project
# (a single Board Explorer sample board alone can make 4-9 diagnosis
# calls), which isn't enough for anyone to meaningfully try the app.
# gemini-2.5-flash-lite has a substantially more generous free-tier daily
# quota and produced valid, evidence-grounded diagnoses in testing. Google
# renames/retires model ids periodically -- if this default ever 404s or
# hits a similarly tight quota, check
# https://ai.google.dev/gemini-api/docs/models and
# https://ai.google.dev/gemini-api/docs/rate-limits, and set GEMINI_MODEL
# explicitly to override.
GEMINI_DEFAULT_MODEL = "gemini-2.5-flash-lite"


def get_llm_provider(settings: Optional[Settings] = None, model: Optional[str] = None) -> BaseLLMProvider:
    settings = settings or get_settings()
    provider_kind = (settings.caf_model_provider or "").lower()

    if provider_kind in ("mock", "offline", "none"):
        return MockLLMProvider()

    if provider_kind == "gemini":
        if not settings.gemini_api_key:
            raise ValueError(
                "GEMINI_API_KEY is not configured. Get a free key from "
                "https://aistudio.google.com/apikey and set it in .env, or "
                "set CAF_MODEL_PROVIDER=mock for offline development."
            )
        return OpenAICompatibleProvider(
            settings=settings,
            model=model or settings.gemini_model or GEMINI_DEFAULT_MODEL,
            base_url=settings.gemini_base_url or GEMINI_BASE_URL,
            api_key=settings.gemini_api_key,
        )

    # vllm / openai / litellm / azure-openai-compatible all speak the same
    # OpenAI chat-completions wire format.
    if not settings.caf_model_base_url:
        raise ValueError(
            "CAF_MODEL_BASE_URL is not configured. Set it in .env, or set "
            "CAF_MODEL_PROVIDER=mock for offline development."
        )
    return OpenAICompatibleProvider(settings=settings, model=model)
