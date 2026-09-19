"""Deterministic offline provider for tests and CI when no LLM credentials
are configured. Never makes network calls."""
from __future__ import annotations

from typing import Callable, Optional

from pcb_ai.llm.base import BaseLLMProvider, LLMMessage, LLMResponse


class MockLLMProvider(BaseLLMProvider):
    """Returns a pre-scripted or callback-generated response. Useful for
    unit-testing the agent/validation pipeline without a live LLM."""

    def __init__(
        self,
        response_fn: Optional[Callable[[list[LLMMessage]], LLMResponse]] = None,
        fixed_content: Optional[str] = None,
        model: str = "mock-offline-provider",
    ):
        self._response_fn = response_fn
        self._fixed_content = fixed_content
        self._model = model
        self.call_log: list[list[LLMMessage]] = []

    @property
    def model_name(self) -> str:
        return self._model

    def complete(
        self,
        messages: list[LLMMessage],
        *,
        tools=None,
        json_mode: bool = False,
        temperature=None,
        max_tokens=None,
        model=None,
    ) -> LLMResponse:
        self.call_log.append(messages)
        if self._response_fn:
            return self._response_fn(messages)
        return LLMResponse(
            content=self._fixed_content or "{}",
            model=self._model,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
        )
