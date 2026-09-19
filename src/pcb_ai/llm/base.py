"""Model-agnostic LLM provider abstraction (Phase 21).

`BaseLLMProvider` is the contract the reasoning agent (Phase 8/10) programs
against. Concrete adapters (OpenAI-compatible endpoints such as the
self-hosted vLLM/LiteLLM Nemotron gateway used here, and -- if credentials
are ever supplied -- native Anthropic/Gemini SDKs) live alongside it.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMMessage:
    role: str  # system | user | assistant | tool
    content: Optional[str] = None
    tool_call_id: Optional[str] = None  # set when role == "tool"
    tool_calls: list[ToolCall] = field(default_factory=list)  # set when role == "assistant" and it called tools


@dataclass
class LLMResponse:
    content: Optional[str]
    tool_calls: list[ToolCall] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    model: Optional[str] = None
    raw: Optional[dict] = None

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


class LLMProviderError(Exception):
    """Raised for provider-level failures (timeout, auth, malformed response)."""


class BaseLLMProvider(ABC):
    """Contract for all LLM backends used by the reasoning agent."""

    @abstractmethod
    def complete(
        self,
        messages: list[LLMMessage],
        *,
        tools: Optional[list[dict]] = None,
        json_mode: bool = False,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None,
    ) -> LLMResponse:
        """Run one chat-completion turn. `tools` uses the OpenAI function
        tool-calling schema: [{"type":"function","function":{"name":...,
        "description":...,"parameters": <json schema>}}]."""
        raise NotImplementedError

    @property
    @abstractmethod
    def model_name(self) -> str:
        raise NotImplementedError
