"""Versioned prompts for the violation-diagnosis reasoning agent (Phase 24).

Prompts are stored as data here (not inline in the agent logic) so new
versions can be added without touching pipeline code, and evaluation runs
can pin/report the exact `prompt_version` used (Phase 23 observability).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptVersion:
    version: str
    system_prompt: str
    user_template: str


_VIOLATION_ANALYSIS_V1_SYSTEM = """\
You are an engineering reasoning assistant embedded in a deterministic PCB \
design-rule-check (DRC) intelligence pipeline.

You are NOT a DRC engine. A deterministic KiCad DRC engine has already \
detected the violation described below; that detection is ground truth and \
must never be second-guessed, restated as uncertain, or recomputed by you.

Your job is strictly interpretation and diagnosis:
  - explain what the violation means in plain engineering terms
  - identify the most likely root cause
  - describe the engineering impact
  - recommend remediation
  - cite the evidence you were given for every non-trivial claim

Hard rules:
  1. Reason ONLY from the evidence supplied in the user message (DRC \
evidence, PCB context, engineering knowledge). Never invent component \
specifications, PCB dimensions, electrical limits, standards, or datasheet \
values that are not present in the supplied evidence.
  2. If the supplied evidence is insufficient to support a confident \
diagnosis, set "insufficient_evidence": true and say so plainly in \
"uncertainty" rather than fabricating a plausible-sounding answer.
  3. Every distinct claim in "evidence" must reference one of: the DRC \
evidence, a specific PCB object from the PCB context, or a specific \
knowledge/datasheet chunk you were given (using its chunk_id or document \
name). Do not cite sources that were not provided to you.
  4. You may propose your own severity assessment in \
"llm_assessed_severity", but you must NOT overwrite or omit the \
deterministic severity provided to you -- both must appear in the output.
  5. Output ONLY a single JSON object matching the schema described in the \
user message. No prose before or after the JSON.
"""

_VIOLATION_ANALYSIS_V1_USER_TEMPLATE = """\
------------------------------------------------------------
DRC EVIDENCE (deterministic ground truth -- do not dispute)
------------------------------------------------------------
{drc_evidence_json}

------------------------------------------------------------
PCB CONTEXT (retrieved deterministically; minimal relevant subset of the design)
------------------------------------------------------------
{pcb_context_json}

------------------------------------------------------------
ENGINEERING KNOWLEDGE (retrieved passages; empty if none found)
------------------------------------------------------------
{engineering_knowledge_json}

------------------------------------------------------------
REQUIRED OUTPUT SCHEMA
------------------------------------------------------------
Return exactly one JSON object with this shape (types illustrative):

{{
  "violation_id": "{violation_id}",
  "classification": {{"type": "...", "severity": "critical|high|medium|low|info", "confidence": 0.0}},
  "summary": "...",
  "affected_objects": [{{"type": "...", "reference": "...", "pad": "...", "net": "..."}}],
  "driving_rule": {{"rule_name": "...", "required_value": "...", "actual_value": "...", "unit": "..."}},
  "root_cause": {{"explanation": "...", "confidence": 0.0}},
  "engineering_impact": {{"description": "...", "potential_effects": ["..."]}},
  "recommended_fix": {{"description": "...", "actions": ["..."]}},
  "evidence": [{{"source_type": "drc|pcb|datasheet|engineering_document", "source_id": "...", "location": "...", "claim": "..."}}],
  "uncertainty": ["..."],
  "requires_human_review": true,
  "llm_assessed_severity": "critical|high|medium|low|info",
  "insufficient_evidence": false
}}

The deterministic severity for this violation is: "{deterministic_severity}". \
Include it verbatim if asked to restate it; your own judgement goes only in \
"llm_assessed_severity".
"""

VIOLATION_ANALYSIS_V1 = PromptVersion(
    version="violation_analysis_v1",
    system_prompt=_VIOLATION_ANALYSIS_V1_SYSTEM,
    user_template=_VIOLATION_ANALYSIS_V1_USER_TEMPLATE,
)

PROMPT_VERSIONS: dict[str, PromptVersion] = {
    VIOLATION_ANALYSIS_V1.version: VIOLATION_ANALYSIS_V1,
}


def get_prompt_version(version: str) -> PromptVersion:
    try:
        return PROMPT_VERSIONS[version]
    except KeyError as exc:
        raise ValueError(f"Unknown prompt version: {version}") from exc
