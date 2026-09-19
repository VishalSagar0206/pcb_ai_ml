"""Unit tests for the agent tool registry (Phase 10)."""
from __future__ import annotations

from pcb_ai.agent.tools import AgentToolbox
from pcb_ai.context.retriever import PCBContextRetriever


def test_toolbox_get_component(sample_graph, sample_drc_result):
    toolbox = AgentToolbox(
        sample_graph,
        PCBContextRetriever(sample_graph),
        None,
        {v.violation_id: v for v in sample_drc_result.violations},
    )
    result = toolbox.call("get_component", {"reference": "U3"})
    assert result["reference"] == "U3"
    assert "error" not in result


def test_toolbox_list_violations(sample_graph, sample_drc_result):
    violations_by_id = {v.violation_id: v for v in sample_drc_result.violations}
    toolbox = AgentToolbox(sample_graph, PCBContextRetriever(sample_graph), None, violations_by_id)
    result = toolbox.call("list_violations", {})
    assert len(result["violations"]) == len(violations_by_id)
    ids = {v["violation_id"] for v in result["violations"]}
    assert ids == set(violations_by_id.keys())


def test_toolbox_unknown_component_returns_error(sample_graph, sample_drc_result):
    toolbox = AgentToolbox(
        sample_graph,
        PCBContextRetriever(sample_graph),
        None,
        {v.violation_id: v for v in sample_drc_result.violations},
    )
    result = toolbox.call("get_component", {"reference": "NOPE"})
    assert "error" in result


def test_toolbox_get_drc_evidence(sample_graph, sample_drc_result):
    violations_by_id = {v.violation_id: v for v in sample_drc_result.violations}
    toolbox = AgentToolbox(sample_graph, PCBContextRetriever(sample_graph), None, violations_by_id)
    violation_id = sample_drc_result.violations[0].violation_id
    result = toolbox.call("get_drc_evidence", {"violation_id": violation_id})
    assert result["raw_drc_message"] == sample_drc_result.violations[0].raw_drc_message


def test_toolbox_tracks_calls_made(sample_graph, sample_drc_result):
    toolbox = AgentToolbox(
        sample_graph,
        PCBContextRetriever(sample_graph),
        None,
        {v.violation_id: v for v in sample_drc_result.violations},
    )
    toolbox.call("get_component", {"reference": "U3"})
    toolbox.call("get_net", {"net_name": "SPI_CLK"})
    assert toolbox.calls_made == ["get_component", "get_net"]


def test_toolbox_unknown_tool_name(sample_graph, sample_drc_result):
    toolbox = AgentToolbox(
        sample_graph,
        PCBContextRetriever(sample_graph),
        None,
        {v.violation_id: v for v in sample_drc_result.violations},
    )
    result = toolbox.call("not_a_real_tool", {})
    assert "error" in result


def test_toolbox_schemas_are_valid_openai_tool_format(sample_graph, sample_drc_result):
    toolbox = AgentToolbox(
        sample_graph,
        PCBContextRetriever(sample_graph),
        None,
        {v.violation_id: v for v in sample_drc_result.violations},
    )
    for schema in toolbox.schemas:
        assert schema["type"] == "function"
        assert "name" in schema["function"]
        assert "parameters" in schema["function"]
