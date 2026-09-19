"""OpenAI-compatible LLM provider adapter.

Works with any OpenAI-compatible chat-completions endpoint: OpenAI itself,
and self-hosted gateways such as vLLM or LiteLLM proxies (e.g. the
CAF_MODEL_BASE_URL / CAF_MODEL_API_KEY / CAF_MODEL_ANALYSIS Nemotron
deployment configured for this project).
"""
from __future__ import annotations

import json as json_lib
from typing import Any, Optional

from openai import APIError, APITimeoutError, OpenAI

from pcb_ai.config import Settings, get_settings
from pcb_ai.llm.base import BaseLLMProvider, LLMMessage, LLMProviderError, LLMResponse, ToolCall


class OpenAICompatibleProvider(BaseLLMProvider):
    def __init__(
        self,
        settings: Optional[Settings] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.settings = settings or get_settings()
        self._model = model or self.settings.caf_model_analysis
        self._client = OpenAI(
            base_url=base_url or self.settings.caf_model_base_url,
            api_key=api_key or self.settings.caf_model_api_key or "unused",
            timeout=self.settings.llm_request_timeout_s,
            # The openai SDK's own default (2) wasn't always enough to ride
            # out transient 503 "model currently experiencing high demand"
            # responses observed live against Gemini's compatibility
            # endpoint during testing -- bumped for both providers since
            # any OpenAI-compatible gateway can return transient 429/5xx.
            max_retries=5,
        )

    @property
    def model_name(self) -> str:
        return self._model

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
        payload_messages = [_to_openai_message(m) for m in messages]
        kwargs: dict[str, Any] = {
            "model": model or self._model,
            "messages": payload_messages,
            "temperature": temperature if temperature is not None else self.settings.llm_temperature,
            "max_tokens": max_tokens or self.settings.llm_max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            completion = self._client.chat.completions.create(**kwargs)
        except APITimeoutError as exc:
            raise LLMProviderError(f"LLM request timed out: {exc}") from exc
        except APIError as exc:
            raise LLMProviderError(f"LLM provider error: {exc}") from exc

        choice = completion.choices[0]
        message = choice.message

        tool_calls: list[ToolCall] = []
        for tc in message.tool_calls or []:
            try:
                arguments = json_lib.loads(tc.function.arguments) if tc.function.arguments else {}
            except json_lib.JSONDecodeError:
                arguments = {"_raw_arguments": tc.function.arguments}
            tool_calls.append(ToolCall(id=tc.id, name=tc.function.name, arguments=arguments))

        usage = completion.usage
        return LLMResponse(
            content=message.content,
            tool_calls=tool_calls,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            total_tokens=usage.total_tokens if usage else 0,
            model=completion.model,
            raw=completion.model_dump(),
        )


def _to_openai_message(message: LLMMessage) -> dict[str, Any]:
    result: dict[str, Any] = {"role": message.role}
    if message.content is not None:
        result["content"] = message.content
    if message.role == "tool" and message.tool_call_id:
        result["tool_call_id"] = message.tool_call_id
    if message.role == "assistant" and message.tool_calls:
        result["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.name, "arguments": json_lib.dumps(tc.arguments)},
            }
            for tc in message.tool_calls
        ]
    return result
