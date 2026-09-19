"""Minimal PCB context bundle handed to the LLM per-violation (Phase 4),
and the observability trace schema (Phase 23).

The context bundle is deliberately narrow: only the components/pads/nets/
tracks/vias/zones/rules relevant to a *specific* violation are included, so
the LLM never receives the full board JSON.
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from pcb_ai.schemas.pcb import Component, DesignRule, Net, Pad, Track, Via, Zone

CONTEXT_SCHEMA_VERSION = "1.0"


class ViolationContext(BaseModel):
    """The minimal PCB context required to understand one DRC violation."""

    schema_version: str = CONTEXT_SCHEMA_VERSION
    violation_id: str
    components: list[Component] = Field(default_factory=list)
    pads: list[Pad] = Field(default_factory=list)
    nets: list[Net] = Field(default_factory=list)
    tracks: list[Track] = Field(default_factory=list)
    vias: list[Via] = Field(default_factory=list)
    zones: list[Zone] = Field(default_factory=list)
    rules: list[DesignRule] = Field(default_factory=list)
    nearby_object_ids: list[str] = Field(default_factory=list)

    def object_count(self) -> int:
        return (
            len(self.components)
            + len(self.pads)
            + len(self.nets)
            + len(self.tracks)
            + len(self.vias)
            + len(self.zones)
            + len(self.rules)
        )


class AnalysisTrace(BaseModel):
    """Observability trace for a single violation analysis (Phase 23)."""

    schema_version: str = CONTEXT_SCHEMA_VERSION
    analysis_id: str
    violation_id: str
    tools_called: list[str] = Field(default_factory=list)
    retrieved_pcb_objects: list[str] = Field(default_factory=list)
    retrieved_documents: list[str] = Field(default_factory=list)
    llm_model: Optional[str] = None
    prompt_version: Optional[str] = None
    response_schema_version: Optional[str] = None
    latency_ms: Optional[float] = None
    token_usage: dict[str, int] = Field(default_factory=dict)
    stages_completed: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)
