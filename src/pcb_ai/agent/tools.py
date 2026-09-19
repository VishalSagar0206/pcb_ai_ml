"""Tool-based reasoning interfaces (Phase 10).

`AgentToolbox` exposes deterministic PCB/DRC/knowledge lookups as
OpenAI-style function tools so an LLM agent can retrieve *only* the
evidence it needs instead of receiving the entire board. All tool
implementations are deterministic Python -- the LLM never guesses which
object a reference/uuid maps to.
"""
from __future__ import annotations

from typing import Any, Callable, Optional

from pcb_ai.context.graph import PCBGraph
from pcb_ai.context.retriever import PCBContextRetriever
from pcb_ai.rag.retriever import KnowledgeRetriever
from pcb_ai.schemas.drc import DRCViolation


class AgentToolbox:
    def __init__(
        self,
        graph: PCBGraph,
        context_retriever: PCBContextRetriever,
        knowledge_retriever: Optional[KnowledgeRetriever],
        violations_by_id: dict[str, DRCViolation],
    ):
        self.graph = graph
        self.context_retriever = context_retriever
        self.knowledge_retriever = knowledge_retriever
        self.violations_by_id = violations_by_id
        self.calls_made: list[str] = []

        self._dispatch: dict[str, Callable[..., dict]] = {
            "list_violations": self._list_violations,
            "get_violation": self._get_violation,
            "get_component": self._get_component,
            "get_pad": self._get_pad,
            "get_net": self._get_net,
            "get_connected_objects": self._get_connected_objects,
            "get_nearby_objects": self._get_nearby_objects,
            "get_applicable_rules": self._get_applicable_rules,
            "search_datasheet": self._search_datasheet,
            "search_engineering_knowledge": self._search_engineering_knowledge,
            "get_drc_evidence": self._get_drc_evidence,
        }

    # --- OpenAI tool schemas -------------------------------------------------
    @property
    def schemas(self) -> list[dict]:
        return [
            _tool_schema(
                "list_violations",
                "List all DRC violations for this board with a short summary each "
                "(violation_id, rule_type, severity, message, affected references). "
                "Use this first when you don't already know which violation_id is relevant.",
                {},
                [],
            ),
            _tool_schema(
                "get_violation",
                "Get the normalized DRC violation record by its violation_id.",
                {"violation_id": {"type": "string"}},
                ["violation_id"],
            ),
            _tool_schema(
                "get_component",
                "Get a PCB component (reference designator, value, footprint, position) by its reference, e.g. 'U3'.",
                {"reference": {"type": "string"}},
                ["reference"],
            ),
            _tool_schema(
                "get_pad",
                "Get a specific pad of a component by reference and pad number.",
                {"reference": {"type": "string"}, "pad_number": {"type": "string"}},
                ["reference", "pad_number"],
            ),
            _tool_schema(
                "get_net",
                "Get a net by name, including its connected pads and components.",
                {"net_name": {"type": "string"}},
                ["net_name"],
            ),
            _tool_schema(
                "get_connected_objects",
                "Get all components, tracks, vias, and zones connected to a given net.",
                {"net_name": {"type": "string"}},
                ["net_name"],
            ),
            _tool_schema(
                "get_nearby_objects",
                "Find pads/tracks/vias within radius_mm of a board coordinate (x, y in mm).",
                {
                    "x": {"type": "number"},
                    "y": {"type": "number"},
                    "radius_mm": {"type": "number", "description": "search radius in millimeters"},
                },
                ["x", "y", "radius_mm"],
            ),
            _tool_schema(
                "get_applicable_rules",
                "Get design rules applicable to a rule_type (e.g. 'clearance'); omit rule_type for all known rules.",
                {"rule_type": {"type": "string"}},
                [],
            ),
            _tool_schema(
                "search_datasheet",
                "Search ingested component datasheets for text relevant to a component reference and query.",
                {"component_reference": {"type": "string"}, "query": {"type": "string"}},
                ["component_reference", "query"],
            ),
            _tool_schema(
                "search_engineering_knowledge",
                "Search ingested engineering knowledge (design guidelines, app notes) for text relevant to a query and/or violation type.",
                {"query": {"type": "string"}, "violation_type": {"type": "string"}},
                ["query"],
            ),
            _tool_schema(
                "get_drc_evidence",
                "Get the raw, unmodified DRC evidence (message, severity, items) for a violation_id.",
                {"violation_id": {"type": "string"}},
                ["violation_id"],
            ),
        ]

    def call(self, name: str, arguments: dict[str, Any]) -> dict:
        handler = self._dispatch.get(name)
        if handler is None:
            return {"error": f"Unknown tool: {name}"}
        self.calls_made.append(name)
        try:
            return handler(**arguments)
        except TypeError as exc:
            return {"error": f"Invalid arguments for {name}: {exc}"}

    # --- tool implementations -------------------------------------------------
    def _list_violations(self) -> dict:
        return {
            "violations": [
                {
                    "violation_id": v.violation_id,
                    "rule_type": v.rule_type.value,
                    "severity": v.severity.value,
                    "message": v.message,
                    "affected_objects": [
                        {"type": item.type, "reference": item.reference, "pad": item.pad, "net": item.net}
                        for item in v.items
                    ],
                }
                for v in self.violations_by_id.values()
            ]
        }

    def _get_violation(self, violation_id: str) -> dict:
        violation = self.violations_by_id.get(violation_id)
        if not violation:
            return {"error": f"No such violation_id: {violation_id}"}
        return violation.model_dump(mode="json")

    def _get_component(self, reference: str) -> dict:
        component = self.graph.get_component(reference)
        if not component:
            return {"error": f"No such component: {reference}"}
        return component.model_dump(mode="json")

    def _get_pad(self, reference: str, pad_number: str) -> dict:
        pad = self.graph.get_pad(reference, pad_number)
        if not pad:
            return {"error": f"No such pad: {reference}:{pad_number}"}
        return pad.model_dump(mode="json")

    def _get_net(self, net_name: str) -> dict:
        net = self.graph.get_net(net_name)
        if not net:
            return {"error": f"No such net: {net_name}"}
        return net.model_dump(mode="json")

    def _get_connected_objects(self, net_name: str) -> dict:
        return {
            "components": [c.model_dump(mode="json") for c in self.graph.get_connected_components(net_name)],
            "tracks": [t.model_dump(mode="json") for t in self.graph.get_tracks_for_net(net_name)],
            "vias": [v.model_dump(mode="json") for v in self.graph.get_vias_for_net(net_name)],
            "zones": [z.model_dump(mode="json") for z in self.graph.get_zones_for_net(net_name)],
        }

    def _get_nearby_objects(self, x: float, y: float, radius_mm: float) -> dict:
        objects = self.graph.get_nearby_objects(x, y, radius_mm)
        return {"objects": [obj.__dict__ for obj in objects]}

    def _get_applicable_rules(self, rule_type: Optional[str] = None) -> dict:
        rules = self.graph.get_applicable_rules(rule_type)
        return {"rules": [r.model_dump(mode="json") for r in rules]}

    def _search_datasheet(self, component_reference: str, query: str) -> dict:
        if self.knowledge_retriever is None:
            return {"chunks": [], "note": "No knowledge retriever configured."}
        chunks = self.knowledge_retriever.search(
            query, component_references=[component_reference]
        )
        chunks = [c for c in chunks if c.source == "datasheet"] or chunks
        return {"chunks": [c.model_dump(mode="json") for c in chunks]}

    def _search_engineering_knowledge(self, query: str, violation_type: Optional[str] = None) -> dict:
        if self.knowledge_retriever is None:
            return {"chunks": [], "note": "No knowledge retriever configured."}
        chunks = self.knowledge_retriever.search(query, violation_type=violation_type)
        return {"chunks": [c.model_dump(mode="json") for c in chunks]}

    def _get_drc_evidence(self, violation_id: str) -> dict:
        violation = self.violations_by_id.get(violation_id)
        if not violation:
            return {"error": f"No such violation_id: {violation_id}"}
        return {
            "raw_drc_message": violation.raw_drc_message,
            "severity": violation.severity.value,
            "rule_type": violation.rule_type.value,
            "items": [item.model_dump(mode="json") for item in violation.items],
        }


def _tool_schema(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }
