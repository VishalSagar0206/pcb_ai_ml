"""Unit/integration tests for the diagnosis pipeline using a deterministic
mock LLM provider (Phase 8/9/11/26) -- no network calls."""
from __future__ import annotations

import json

from pcb_ai.agent.pipeline import ViolationDiagnosisAgent
from pcb_ai.llm.mock import MockLLMProvider


def _valid_diagnosis_json(violation_id: str) -> str:
    return json.dumps(
        {
            "violation_id": violation_id,
            "classification": {"type": "clearance", "severity": "high", "confidence": 0.9},
            "summary": "Pads are too close together.",
            "affected_objects": [{"type": "pad", "reference": "U3", "pad": "4", "net": "SPI_CLK"}],
            "driving_rule": {"rule_name": "clearance", "required_value": 0.2, "actual_value": 0.09, "unit": "mm"},
            "root_cause": {"explanation": "Placement too tight.", "confidence": 0.9},
            "engineering_impact": {"description": "Solder bridge risk.", "potential_effects": ["short risk"]},
            "recommended_fix": {"description": "Move parts apart.", "actions": ["reposition R8"]},
            "evidence": [{"source_type": "drc", "source_id": violation_id, "claim": "clearance violation"}],
            "uncertainty": [],
            "requires_human_review": True,
        }
    )


def test_pipeline_produces_valid_diagnosis_with_mock_llm(sample_graph, sample_drc_result):
    violation = next(v for v in sample_drc_result.violations if v.rule_type.value == "clearance")
    mock = MockLLMProvider(fixed_content=_valid_diagnosis_json(violation.violation_id))
    agent = ViolationDiagnosisAgent(mock, knowledge_retriever=None)

    diagnosis, trace = agent.diagnose(violation, sample_graph, analysis_id="test")

    assert diagnosis.violation_id == violation.violation_id
    assert diagnosis.insufficient_evidence is False
    assert diagnosis.deterministic_severity is not None
    assert diagnosis.validation_passed is True
    assert "drc_interpretation" in trace.stages_completed
    assert "pcb_context_resolution" in trace.stages_completed
    assert "llm_reasoning" in trace.stages_completed
    assert "evidence_validation" in trace.stages_completed


def test_pipeline_unwraps_markdown_json_fence(sample_graph, sample_drc_result):
    """Some OpenAI-compatible providers (observed with Gemini's
    compatibility layer) occasionally wrap JSON-mode output in a markdown
    code fence. The pipeline should still parse it successfully rather than
    falling back to insufficient_evidence on otherwise-valid content."""
    violation = next(v for v in sample_drc_result.violations if v.rule_type.value == "clearance")
    fenced_content = f"```json\n{_valid_diagnosis_json(violation.violation_id)}\n```"
    mock = MockLLMProvider(fixed_content=fenced_content)
    agent = ViolationDiagnosisAgent(mock, knowledge_retriever=None)

    diagnosis, _trace = agent.diagnose(violation, sample_graph, analysis_id="test")

    assert diagnosis.violation_id == violation.violation_id
    assert diagnosis.insufficient_evidence is False
    assert diagnosis.validation_passed is True


def test_pipeline_handles_invalid_json_gracefully(sample_graph, sample_drc_result):
    violation = sample_drc_result.violations[0]
    mock = MockLLMProvider(fixed_content="{not valid json")
    agent = ViolationDiagnosisAgent(mock, knowledge_retriever=None)

    diagnosis, _trace = agent.diagnose(violation, sample_graph, analysis_id="test")

    assert diagnosis.insufficient_evidence is True
    assert diagnosis.requires_human_review is True
    assert any("invalid JSON" in u for u in diagnosis.uncertainty)


def test_pipeline_handles_schema_violation_gracefully(sample_graph, sample_drc_result):
    violation = sample_drc_result.violations[0]
    # Missing required fields (e.g. "root_cause") should fail pydantic validation.
    mock = MockLLMProvider(fixed_content=json.dumps({"violation_id": violation.violation_id, "summary": "x"}))
    agent = ViolationDiagnosisAgent(mock, knowledge_retriever=None)

    diagnosis, _trace = agent.diagnose(violation, sample_graph, analysis_id="test")

    assert diagnosis.insufficient_evidence is True
    assert any("schema validation" in u for u in diagnosis.uncertainty)


def test_pipeline_handles_llm_provider_error(sample_graph, sample_drc_result):
    from pcb_ai.llm.base import LLMProviderError

    def _raise(_messages):
        raise LLMProviderError("simulated timeout")

    violation = sample_drc_result.violations[0]
    mock = MockLLMProvider(response_fn=_raise)
    agent = ViolationDiagnosisAgent(mock, knowledge_retriever=None)

    diagnosis, _trace = agent.diagnose(violation, sample_graph, analysis_id="test")
    assert diagnosis.insufficient_evidence is True
    assert any("LLM provider error" in u for u in diagnosis.uncertainty)


def test_never_fabricates_content_on_failure(sample_graph, sample_drc_result):
    """Failure-path diagnoses must say insufficient_evidence, not invent
    plausible-sounding engineering content (Phase 26)."""
    violation = sample_drc_result.violations[0]
    mock = MockLLMProvider(fixed_content="not json at all")
    agent = ViolationDiagnosisAgent(mock, knowledge_retriever=None)

    diagnosis, _trace = agent.diagnose(violation, sample_graph, analysis_id="test")
    assert diagnosis.root_cause.explanation == "insufficient_evidence"
    assert diagnosis.engineering_impact.description == "insufficient_evidence"
    assert diagnosis.recommended_fix.description == "insufficient_evidence"
