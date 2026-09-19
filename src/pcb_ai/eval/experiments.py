"""Experimental baselines / ablation conditions (Phase 18, 20).

Each condition varies only how much and what kind of evidence is assembled
before the single constrained LLM reasoning call (`synthesize_diagnosis`),
so differences in outcome can be attributed to the evidence-assembly
strategy rather than to prompt wording.

Implemented conditions:
  drc_only        -- Baseline A / Experiment 1: DRC message only.
  raw_kicad       -- Baseline B: DRC + raw .kicad_pcb file text excerpt.
  pcb_json        -- Baseline C / Experiment 2 & 7: DRC + deterministically
                      retrieved, minimal PCB context (this is what the main
                      pipeline uses by default).
  full_pcb_json   -- Experiment 6: DRC + the *entire* PCB JSON (no
                      filtering), for comparison against `pcb_json`'s
                      token/latency/accuracy profile.
  pcb_json_rag    -- Baseline D / Experiment 4: DRC + retrieved PCB context
                      + engineering-knowledge RAG.

Baseline E (DRC + PCB JSON + RAG + tool-based agent) is NOT implemented as
a single-shot condition here: it would require reconciling free tool use
with strict single-call JSON-schema output. The tool-calling agent
infrastructure itself exists (`pcb_ai.agent.query_agent`) and can be used
interactively; wiring it into this structured ablation harness is tracked
as future work (see EVALUATION.md) rather than faked here.
"""
from __future__ import annotations

import json
from typing import Optional

from pcb_ai.agent.pipeline import synthesize_diagnosis
from pcb_ai.config import Settings, get_settings
from pcb_ai.context.graph import PCBGraph
from pcb_ai.context.retriever import PCBContextRetriever
from pcb_ai.llm.base import BaseLLMProvider
from pcb_ai.prompts.violation_analysis import get_prompt_version
from pcb_ai.rag.retriever import KnowledgeRetriever
from pcb_ai.schemas.diagnosis import ViolationDiagnosis
from pcb_ai.schemas.drc import DRCViolation
from pcb_ai.schemas.pcb import PCBDesign
from pcb_ai.severity.policy import SEVERITY_POLICY_VERSION, compute_deterministic_severity
from pcb_ai.validation.evidence_validator import validate_diagnosis

EXPERIMENT_CONDITIONS: list[str] = ["drc_only", "raw_kicad", "pcb_json", "full_pcb_json", "pcb_json_rag"]

_RAW_KICAD_EXCERPT_CHARS = 6000
_MAX_KNOWLEDGE_CHUNKS_FOR_EVAL = 6


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


def _retrieve_knowledge_chunks(
    violation: DRCViolation,
    context_components: list[str],
    knowledge_retriever: Optional[KnowledgeRetriever],
    max_chunks: int,
) -> list[dict]:
    if knowledge_retriever is None:
        return []
    seen: set[str] = set()
    results = []
    for chunk in knowledge_retriever.search_by_violation_type(violation.rule_type.value, top_k=max_chunks):
        if chunk.chunk_id not in seen:
            seen.add(chunk.chunk_id)
            results.append(chunk)
    for ref in context_components:
        if len(results) >= max_chunks:
            break
        for chunk in knowledge_retriever.search_by_component(ref, top_k=3):
            if chunk.chunk_id not in seen:
                seen.add(chunk.chunk_id)
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


def run_condition(
    condition: str,
    violation: DRCViolation,
    pcb: PCBDesign,
    graph: PCBGraph,
    llm_provider: BaseLLMProvider,
    knowledge_retriever: Optional[KnowledgeRetriever] = None,
    settings: Optional[Settings] = None,
    raw_pcb_text: Optional[str] = None,
    prompt_version: str = "violation_analysis_v1",
) -> tuple[ViolationDiagnosis, dict]:
    """Run one ablation condition for one violation. Returns
    (diagnosis, metadata) where metadata includes token usage and an
    estimated evidence size (word count) for the "context size" metric
    (Phase 19: full PCB context tokens vs retrieved PCB context tokens)."""
    if condition not in EXPERIMENT_CONDITIONS:
        raise ValueError(f"Unknown experiment condition: {condition}. Known: {EXPERIMENT_CONDITIONS}")

    settings = settings or get_settings()
    prompt = get_prompt_version(prompt_version)
    drc_evidence = _drc_evidence_dict(violation)

    pcb_context_json = "{}"
    knowledge_json = "[]"
    chunks: list[dict] = []

    if condition == "drc_only":
        pass

    elif condition == "raw_kicad":
        excerpt = (raw_pcb_text or "")[:_RAW_KICAD_EXCERPT_CHARS]
        pcb_context_json = json.dumps({"raw_kicad_pcb_excerpt": excerpt})

    elif condition == "pcb_json":
        retriever = PCBContextRetriever(graph, settings)
        context = retriever.retrieve(violation)
        pcb_context_json = context.model_dump_json(exclude={"schema_version"})

    elif condition == "full_pcb_json":
        pcb_context_json = pcb.model_dump_json(exclude={"schema_version"})

    elif condition == "pcb_json_rag":
        retriever = PCBContextRetriever(graph, settings)
        context = retriever.retrieve(violation)
        pcb_context_json = context.model_dump_json(exclude={"schema_version"})
        chunks = _retrieve_knowledge_chunks(
            violation, [c.reference for c in context.components], knowledge_retriever, _MAX_KNOWLEDGE_CHUNKS_FOR_EVAL
        )
        knowledge_json = json.dumps(chunks)

    evidence_word_count = len(json.dumps(drc_evidence).split()) + len(pcb_context_json.split()) + len(knowledge_json.split())

    diagnosis, raw_content, token_usage = synthesize_diagnosis(
        llm_provider, prompt, violation, drc_evidence, pcb_context_json, knowledge_json
    )

    # Preserve deterministic vs. LLM-assessed severity (Phase 13), mirroring
    # the main pipeline, so severity_agreement is a meaningful metric here too.
    diagnosis.deterministic_severity = compute_deterministic_severity(violation)
    diagnosis.severity_policy_version = SEVERITY_POLICY_VERSION
    if diagnosis.llm_assessed_severity is None:
        diagnosis.llm_assessed_severity = diagnosis.classification.severity

    # Evidence validation (Phase 12) must run for every condition, not just
    # the main pipeline, or "evidence grounding" / "hallucination rate"
    # metrics would be meaningless (always false/zero).
    if not diagnosis.insufficient_evidence:
        known_chunk_ids = {c["chunk_id"] for c in chunks}
        validate_diagnosis(diagnosis, violation, graph, known_chunk_ids)

    metadata = {
        "condition": condition,
        "token_usage": token_usage,
        "evidence_word_count": evidence_word_count,
        "raw_content_length": len(raw_content),
    }
    return diagnosis, metadata
