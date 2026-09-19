"""End-to-end pipeline test (Phase 25): sample board -> DRC -> diagnosis ->
report, using a deterministic mock LLM (no network calls)."""
from __future__ import annotations

import json
from pathlib import Path

from pcb_ai.agent.pipeline import ViolationDiagnosisAgent
from pcb_ai.context.graph import PCBGraph
from pcb_ai.drc.runner import load_fixture_drc_report
from pcb_ai.llm.base import LLMResponse
from pcb_ai.llm.mock import MockLLMProvider
from pcb_ai.parser.kicad_pcb_parser import parse_kicad_pcb_file
from pcb_ai.rag.retriever import KnowledgeRetriever
from pcb_ai.reporting.report_generator import generate_report

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_BOARD = FIXTURES_DIR / "sample_board.kicad_pcb"
SAMPLE_DRC_REPORT = FIXTURES_DIR / "sample_drc_report.json"


def _mock_response_fn(messages):
    # Extract the violation_id embedded in the user prompt so the mock can
    # produce a schema-valid, violation-specific response.
    user_content = next(m.content for m in messages if m.role == "user")
    violation_id = user_content.split('"violation_id": "', 1)[1].split('"', 1)[0]
    content = json.dumps(
        {
            "violation_id": violation_id,
            "classification": {"type": "clearance", "severity": "high", "confidence": 0.8},
            "summary": "Mock summary.",
            "affected_objects": [],
            "root_cause": {"explanation": "Mock root cause.", "confidence": 0.8},
            "engineering_impact": {"description": "Mock impact.", "potential_effects": []},
            "recommended_fix": {"description": "Mock fix.", "actions": []},
            "evidence": [{"source_type": "drc", "source_id": violation_id, "claim": "mock claim"}],
            "uncertainty": [],
            "requires_human_review": True,
        }
    )
    return LLMResponse(content=content, prompt_tokens=10, completion_tokens=10, total_tokens=20)


def test_full_pipeline_end_to_end():
    pcb = parse_kicad_pcb_file(SAMPLE_BOARD)
    graph = PCBGraph(pcb)
    drc_result = load_fixture_drc_report(SAMPLE_DRC_REPORT, pcb)
    assert len(drc_result.violations) > 0

    knowledge_retriever = KnowledgeRetriever()
    knowledge_retriever.index_directory(FIXTURES_DIR / "knowledge")
    knowledge_retriever.index_directory(FIXTURES_DIR / "datasheets")

    mock_llm = MockLLMProvider(response_fn=_mock_response_fn)
    agent = ViolationDiagnosisAgent(mock_llm, knowledge_retriever=knowledge_retriever)

    diagnoses = {}
    for violation in drc_result.violations:
        diagnosis, trace = agent.diagnose(violation, graph, analysis_id="e2e-test")
        diagnoses[violation.violation_id] = diagnosis
        assert trace.violation_id == violation.violation_id
        assert trace.stages_completed == [
            "drc_interpretation",
            "pcb_context_resolution",
            "engineering_knowledge_retrieval",
            "llm_reasoning",
            "evidence_validation",
            "structured_output",
        ]

    assert len(diagnoses) == len(drc_result.violations)

    report = generate_report(pcb, drc_result, diagnoses, analysis_id="e2e-test")
    assert "# PCB DRC INTELLIGENCE REPORT" in report
    for violation_id in diagnoses:
        assert violation_id in report
