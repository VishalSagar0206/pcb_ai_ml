"""Interactive tool-calling query agent (Phase 10 / Phase 15 `/pcb/query`).

Unlike `ViolationDiagnosisAgent` (which assembles evidence deterministically
up front for reliability), this agent lets the LLM decide which tools to
call to answer a free-form engineering question -- e.g. "Why is U3 pad 4
failing DRC?" -- exactly matching the Phase 10 example flow.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from pcb_ai.agent.tools import AgentToolbox
from pcb_ai.llm.base import BaseLLMProvider, LLMMessage, LLMProviderError

_SYSTEM_PROMPT = """\
You are an engineering assistant answering questions about a specific PCB \
design and its deterministic DRC violations. You do not have direct access \
to the PCB or DRC database -- you must call the provided tools to retrieve \
any fact you need. Do not guess component values, net names, coordinates, \
or DRC results; always look them up with a tool call first.

Rules:
  - If you don't already know the specific violation_id being asked about,
call `list_violations` FIRST to find it -- do not guess an id or call
`get_violation`/`get_drc_evidence` with a made-up id.
  - Call tools as many times as needed to gather sufficient evidence.
  - Never state a specification, measurement, or DRC result you did not \
retrieve via a tool call in this conversation.
  - If, after using the available tools, you still lack enough evidence to \
answer confidently, say so explicitly instead of guessing.
  - Once you have enough evidence, answer in plain, concise engineering \
language (not JSON) and mention which objects/evidence your answer relies on.
"""


@dataclass
class QueryAnswer:
    answer: str
    tool_calls: list[str] = field(default_factory=list)
    iterations: int = 0
    exhausted: bool = False


class InteractiveQueryAgent:
    def __init__(self, llm_provider: BaseLLMProvider, toolbox: AgentToolbox, max_iterations: int = 10):
        self.llm_provider = llm_provider
        self.toolbox = toolbox
        self.max_iterations = max_iterations

    def answer(self, question: str) -> QueryAnswer:
        messages = [
            LLMMessage(role="system", content=_SYSTEM_PROMPT),
            LLMMessage(role="user", content=question),
        ]

        for iteration in range(1, self.max_iterations + 1):
            try:
                response = self.llm_provider.complete(messages, tools=self.toolbox.schemas)
            except LLMProviderError as exc:
                return QueryAnswer(answer=f"insufficient_evidence: LLM provider error: {exc}", iterations=iteration)

            if response.has_tool_calls:
                messages.append(
                    LLMMessage(role="assistant", content=response.content, tool_calls=response.tool_calls)
                )
                for tc in response.tool_calls:
                    result = self.toolbox.call(tc.name, tc.arguments)
                    messages.append(
                        LLMMessage(role="tool", tool_call_id=tc.id, content=json.dumps(result, default=str))
                    )
                continue

            return QueryAnswer(
                answer=response.content or "insufficient_evidence: empty response",
                tool_calls=list(self.toolbox.calls_made),
                iterations=iteration,
            )

        return QueryAnswer(
            answer="insufficient_evidence: tool-call budget exhausted before reaching a final answer.",
            tool_calls=list(self.toolbox.calls_made),
            iterations=self.max_iterations,
            exhausted=True,
        )
