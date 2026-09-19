"""Unit tests for the PCB context graph (Phase 5) and retriever (Phase 4)."""
from __future__ import annotations

from pcb_ai.context.retriever import PCBContextRetriever


def test_graph_direct_lookups(sample_graph):
    assert sample_graph.get_component("U3") is not None
    assert sample_graph.get_component("NONEXISTENT") is None
    assert sample_graph.get_pad("U3", "4") is not None
    assert sample_graph.get_net("SPI_CLK") is not None


def test_graph_resolves_uuid_to_object(sample_graph):
    resolved = sample_graph.resolve_uuid("u3-p4")
    assert resolved is not None
    assert resolved.kind == "pad"
    assert resolved.reference == "U3"
    assert resolved.pad == "4"


def test_graph_connected_components_for_net(sample_graph):
    components = sample_graph.get_connected_components("SPI_CLK")
    refs = {c.reference for c in components}
    assert refs == {"U3", "R8"}


def test_graph_nearby_objects_deterministic(sample_graph):
    nearby = sample_graph.get_nearby_objects(31.05, 21.0, radius_mm=1.0)
    kinds = {(obj.kind, obj.id) for obj in nearby}
    assert ("pad", "U3:4") in kinds
    assert ("pad", "R8:1") in kinds


def test_retriever_returns_minimal_context_not_full_board(sample_pcb, sample_graph, sample_drc_result):
    retriever = PCBContextRetriever(sample_graph)
    clearance_violation = next(v for v in sample_drc_result.violations if v.rule_type.value == "clearance")
    context = retriever.retrieve(clearance_violation)

    refs = {c.reference for c in context.components}
    assert "U3" in refs
    assert "R8" in refs
    # Unrelated components should not be pulled in for this violation.
    assert "C1" not in refs
    # The retrieved context must be a strict subset of the full board.
    assert len(context.components) < len(sample_pcb.components)
