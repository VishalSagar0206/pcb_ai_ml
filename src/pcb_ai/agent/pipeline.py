"""Multi-stage violation diagnosis pipeline (Phase 8, 9, 11).

Stages 1-3 (deterministic DRC interpretation, PCB context resolution,
engineering knowledge retrieval) are performed entirely in Python -- no LLM
involvement -- per the architecture's core principle that the software,
not the model, locates relevant evidence. Only stages 4-6 (evidence
synthesis, root-cause reasoning, remediation generation) are delegated to
the LLM, constrained to the evidence explicitly assembled here. Stage 7
(evidence validation) is performed by `pcb_ai.validation` after this
pipeline returns; stage 8 is the final structured `ViolationDiagnosis`.
"""
from __future__ import annotations

import json
import re
import time
from typing import Optional

from pydantic import ValidationError

from pcb_ai.config import Settings, get_settings
from pcb_ai.context.graph import PCBGraph
from pcb_ai.context.retriever import PCBContextRetriever
from pcb_ai.llm.base import BaseLLMProvider, LLMMessage, LLMProviderError
from pcb_ai.prompts.violation_analysis import PromptVersion, get_prompt_version
from pcb_ai.rag.retriever import KnowledgeRetriever
from pcb_ai.schemas.context import AnalysisTrace, ViolationContext
from pcb_ai.schemas.diagnosis import (
    AffectedObject,
    Classification,
    EngineeringImpact,
    EvidenceItem,
    RecommendedFix,
    RootCause,
    ViolationDiagnosis,
)
from pcb_ai.schemas.drc import DRCViolation
from pcb_ai.severity.policy import compute_deterministic_severity
from pcb_ai.validation.evidence_validator import validate_diagnosis

# Some OpenAI-compatible providers (observed with Gemini's compatibility
# layer, not just Nemotron) occasionally wrap otherwise-valid JSON in a
# markdown code fence even when JSON mode is requested. This is a
# defensive, no-op-if-absent unwrap -- it never invents or alters content,
# it only strips a leading/trailing ``` or ```json fence so `json.loads`
# doesn't spuriously fail and fall back to `insufficient_evidence` on
# output that was otherwise perfectly valid.
_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*\n?(.*?)\n?```\s*$", re.DOTALL)


def _strip_json_fence(content: str) -> str:
    stripped = content.strip()
    match = _JSON_FENCE_RE.match(stripped)
    return match.group(1).strip() if match else stripped


class ViolationDiagnosisAgent:
    def __init__(
        self,
        llm_provider: BaseLLMProvider,
        knowledge_retriever: Optional[KnowledgeRetriever] = None,
        settings: Optional[Settings] = None,
        prompt_version: str = "violation_analysis_v1",
    ):
        self.llm_provider = llm_provider
        self.knowledge_retriever = knowledge_retriever
        self.settings = settings or get_settings()
        self.prompt: PromptVersion = get_prompt_version(prompt_version)

    def diagnose(
        self,
        violation: DRCViolation,
        graph: PCBGraph,
        analysis_id: str,
    ) -> tuple[ViolationDiagnosis, AnalysisTrace]:
        start = time.perf_counter()
        trace = AnalysisTrace(
            analysis_id=analysis_id,
            violation_id=violation.violation_id,
            llm_model=self.llm_provider.model_name,
            prompt_version=self.prompt.version,
            response_schema_version=ViolationDiagnosis.model_fields["schema_version"].default,
        )

        # STAGE 1: deterministic DRC interpretation.
        drc_evidence = _drc_evidence_dict(violation)
        trace.stages_completed.append("drc_interpretation")

        # STAGE 2: PCB context resolution (deterministic retrieval).
        retriever = PCBContextRetriever(graph, self.settings)
        context = retriever.retrieve(violation)
        trace.retrieved_pcb_objects = _context_object_ids(context)
        trace.stages_completed.append("pcb_context_resolution")

        # STAGE 3: engineering knowledge retrieval (deterministic retrieval).
        knowledge_chunks = self._retrieve_knowledge(violation, context)
        trace.retrieved_documents = [c["chunk_id"] for c in knowledge_chunks]
        trace.stages_completed.append("engineering_knowledge_retrieval")

        # STAGE 4-6: evidence synthesis + root-cause + remediation via one
        # constrained, JSON-mode LLM call.
        diagnosis, raw_content, token_usage = self._reason(violation, drc_evidence, context, knowledge_chunks)
        trace.stages_completed.append("llm_reasoning")
        trace.token_usage = token_usage

        # Preserve deterministic vs. LLM-assessed severity separately (Phase 13).
        diagnosis.deterministic_severity = compute_deterministic_severity(violation)
        diagnosis.severity_policy_version = self.settings.severity_policy_version
        if diagnosis.llm_assessed_severity is None:
            diagnosis.llm_assessed_severity = diagnosis.classification.severity

        # STAGE 7: evidence validation -- never accept the LLM's output at face value.
        if not diagnosis.insufficient_evidence:
            known_chunk_ids = {c["chunk_id"] for c in knowledge_chunks}
            validate_diagnosis(diagnosis, violation, graph, known_chunk_ids)
        trace.stages_completed.append("evidence_validation")

        trace.latency_ms = (time.perf_counter() - start) * 1000
        trace.stages_completed.append("structured_output")
        return diagnosis, trace

    def _retrieve_knowledge(self, violation: DRCViolation, context: ViolationContext) -> list[dict]:
        if self.knowledge_retriever is None:
            return []
        max_chunks = self.settings.max_knowledge_chunks
        seen_ids: set[str] = set()
        results = []

        for chunk in self.knowledge_retriever.search_by_violation_type(violation.rule_type.value, top_k=max_chunks):
            if chunk.chunk_id not in seen_ids:
                seen_ids.add(chunk.chunk_id)
                results.append(chunk)

        for component in context.components:
            if len(results) >= max_chunks:
                break
            for chunk in self.knowledge_retriever.search_by_component(component.reference, top_k=3):
                if chunk.chunk_id not in seen_ids:
                    seen_ids.add(chunk.chunk_id)
                    results.append(chunk)

        results = results[:max_chunks]
        return [
            {
                "chunk_id": c.chunk_id,
                "document_name": c.document_name,
                "source": c.source,
                "page": c.page,
                "section": c.section,
                "text": c.text,
                "similarity": c.similarity,
            }
            for c in results
        ]

    def _reason(
        self,
        violation: DRCViolation,
        drc_evidence: dict,
        context: ViolationContext,
        knowledge_chunks: list[dict],
    ) -> tuple[ViolationDiagnosis, str, dict]:
        pcb_context_json = context.model_dump_json(indent=2, exclude={"schema_version"})
        knowledge_json = json.dumps(knowledge_chunks, indent=2)
        return synthesize_diagnosis(
            self.llm_provider, self.prompt, violation, drc_evidence, pcb_context_json, knowledge_json
        )


def synthesize_diagnosis(
    llm_provider,
    prompt: PromptVersion,
    violation: DRCViolation,
    drc_evidence: dict,
    pcb_context_json: str,
    engineering_knowledge_json: str,
) -> tuple[ViolationDiagnosis, str, dict]:
    """Stage 4-6 in isolation: render the prompt with arbitrary evidence
    strings and get back a validated `ViolationDiagnosis`. Exposed as a
    module-level function (rather than only a method) so the evaluation
    harness (Phase 17-20) can run the same reasoning step with different
    evidence-assembly strategies (baselines A-E) without duplicating the
    JSON-parsing/fallback logic.
    """
    user_content = prompt.user_template.format(
        drc_evidence_json=json.dumps(drc_evidence, indent=2),
        pcb_context_json=pcb_context_json,
        engineering_knowledge_json=engineering_knowledge_json,
        violation_id=violation.violation_id,
        deterministic_severity=violation.severity.value,
    )
    messages = [
        LLMMessage(role="system", content=prompt.system_prompt),
        LLMMessage(role="user", content=user_content),
    ]
    try:
        response = llm_provider.complete(messages, json_mode=True)
    except LLMProviderError as exc:
        return _fallback_diagnosis(violation, [f"LLM provider error: {exc}"]), "", {}

    content = response.content or ""
    token_usage = {
        "prompt_tokens": response.prompt_tokens,
        "completion_tokens": response.completion_tokens,
        "total_tokens": response.total_tokens,
    }

    try:
        parsed = json.loads(_strip_json_fence(content))
    except json.JSONDecodeError as exc:
        return (
            _fallback_diagnosis(violation, [f"LLM returned invalid JSON: {exc}"]),
            content,
            token_usage,
        )

    parsed.setdefault("violation_id", violation.violation_id)
    try:
        diagnosis = ViolationDiagnosis.model_validate(parsed)
    except ValidationError as exc:
        return (
            _fallback_diagnosis(violation, [f"LLM output failed schema validation: {exc}"]),
            content,
            token_usage,
        )

    return diagnosis, content, token_usage



def _drc_evidence_dict(violation: DRCViolation) -> dict:
    return {
        "violation_id": violation.violation_id,
        "rule_type": violation.rule_type.value,
        "raw_rule_id": violation.raw_rule_id,
        "severity": violation.severity.value,
        "message": violation.message,
        "layer": violation.layer,
        "location": violation.location.model_dump() if violation.location else None,
        "items": [item.model_dump() for item in violation.items],
        "actual_value": violation.actual_value,
        "required_value": violation.required_value,
        "unit": violation.unit,
        "raw_drc_message": violation.raw_drc_message,
    }


def _context_object_ids(context: ViolationContext) -> list[str]:
    ids: list[str] = [c.reference for c in context.components]
    ids += [p.pad_id for p in context.pads]
    ids += [n.net_name for n in context.nets]
    ids += [t.track_id for t in context.tracks]
    ids += [v.via_id for v in context.vias]
    ids += [z.zone_id for z in context.zones]
    return ids


def _fallback_diagnosis(violation: DRCViolation, uncertainty: list[str]) -> ViolationDiagnosis:
    """Never fabricate a diagnosis when the LLM call/parse fails; return an
    explicit insufficient-evidence result instead (Phase 26 failure handling)."""
    return ViolationDiagnosis(
        violation_id=violation.violation_id,
        classification=Classification(type=violation.rule_type.value, severity=violation.severity, confidence=0.0),
        summary="Diagnosis unavailable: LLM reasoning stage failed or returned an invalid response.",
        affected_objects=[
            AffectedObject(type=item.type, reference=item.reference, pad=item.pad, net=item.net)
            for item in violation.items
        ],
        root_cause=RootCause(explanation="insufficient_evidence", confidence=0.0),
        engineering_impact=EngineeringImpact(description="insufficient_evidence", potential_effects=[]),
        recommended_fix=RecommendedFix(description="insufficient_evidence", actions=[]),
        evidence=[
            EvidenceItem(source_type="drc", source_id=violation.violation_id, claim=violation.raw_drc_message)
        ],
        uncertainty=uncertainty,
        requires_human_review=True,
        insufficient_evidence=True,
        deterministic_severity=compute_deterministic_severity(violation),
    )
