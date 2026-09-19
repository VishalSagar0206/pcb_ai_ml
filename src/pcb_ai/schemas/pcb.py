"""Canonical, versioned structured representation of a KiCad PCB design.

This module defines the schema described in Phase 1 of the PCB DRC
Intelligence architecture: a hierarchical, information-dense JSON
representation of a KiCad board that preserves component/net relationships
so downstream stages (DRC context retrieval, RAG, LLM reasoning) can work
with structured facts instead of raw KiCad file text.

The schema is intentionally permissive (most fields optional) because not
every KiCad board populates every field, and the parser must never fail
just because an optional attribute is missing.
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

PCB_SCHEMA_VERSION = "1.0"


class Point(BaseModel):
    x: float
    y: float


class BoardInfo(BaseModel):
    board_id: str
    title: Optional[str] = None
    revision: Optional[str] = None
    layers: list[str] = Field(default_factory=list)
    thickness_mm: Optional[float] = None
    width_mm: Optional[float] = None
    height_mm: Optional[float] = None
    origin: Optional[Point] = None


class LayerInfo(BaseModel):
    id: int
    name: str
    type: str  # e.g. "signal", "power", "user", "mixed"


class Pad(BaseModel):
    component_reference: str
    pad_number: str
    pad_type: Optional[str] = None  # thru_hole, smd, connect, np_thru_hole
    shape: Optional[str] = None  # circle, rect, oval, roundrect, custom
    position: Optional[Point] = None
    size: Optional[dict[str, float]] = None  # {"x":..,"y":..}
    drill_mm: Optional[float] = None
    layers: list[str] = Field(default_factory=list)
    net_id: Optional[int] = None
    net_name: Optional[str] = None
    uuid: Optional[str] = None  # KiCad object uuid, used to resolve DRC item references

    @property
    def pad_id(self) -> str:
        return f"{self.component_reference}:{self.pad_number}"


class ComponentProperty(BaseModel):
    key: str
    value: str


class Component(BaseModel):
    reference: str
    value: Optional[str] = None
    footprint: Optional[str] = None
    library_id: Optional[str] = None
    position: Optional[Point] = None
    rotation_deg: Optional[float] = None
    side: Optional[str] = None  # top / bottom
    properties: list[ComponentProperty] = Field(default_factory=list)
    pads: list[str] = Field(default_factory=list)  # pad_ids belonging to this component
    uuid: Optional[str] = None  # KiCad footprint uuid, used to resolve DRC item references


class Footprint(BaseModel):
    reference: str
    value: Optional[str] = None
    library_link: Optional[str] = None
    pads: list[str] = Field(default_factory=list)
    has_courtyard: bool = False
    graphics_count: int = 0
    fab_layer_present: bool = False


class Net(BaseModel):
    net_id: int
    net_name: str
    connected_pads: list[str] = Field(default_factory=list)
    connected_components: list[str] = Field(default_factory=list)


class Track(BaseModel):
    track_id: str
    layer: str
    start: Point
    end: Point
    width_mm: float
    net_id: Optional[int] = None
    net_name: Optional[str] = None


class Via(BaseModel):
    via_id: str
    position: Point
    diameter_mm: float
    drill_mm: float
    layers: list[str] = Field(default_factory=list)
    net_id: Optional[int] = None
    net_name: Optional[str] = None


class Zone(BaseModel):
    zone_id: str
    layer: str
    net_id: Optional[int] = None
    net_name: Optional[str] = None
    clearance_mm: Optional[float] = None
    polygon: list[Point] = Field(default_factory=list)


class DesignRule(BaseModel):
    rule_name: str
    rule_type: str  # clearance, track_width, via, hole, courtyard, diff_pair, ...
    value: Optional[float] = None
    unit: Optional[str] = None
    raw: dict[str, Any] = Field(default_factory=dict)


class PCBDesign(BaseModel):
    """Top-level canonical PCB representation. Always schema-versioned."""

    schema_version: str = PCB_SCHEMA_VERSION
    board: BoardInfo
    layers: list[LayerInfo] = Field(default_factory=list)
    components: list[Component] = Field(default_factory=list)
    footprints: list[Footprint] = Field(default_factory=list)
    pads: list[Pad] = Field(default_factory=list)
    nets: list[Net] = Field(default_factory=list)
    tracks: list[Track] = Field(default_factory=list)
    vias: list[Via] = Field(default_factory=list)
    zones: list[Zone] = Field(default_factory=list)
    rules: list[DesignRule] = Field(default_factory=list)

    source_file: Optional[str] = None

    def get_component(self, reference: str) -> Optional[Component]:
        return next((c for c in self.components if c.reference == reference), None)

    def get_pad(self, reference: str, pad_number: str) -> Optional[Pad]:
        return next(
            (p for p in self.pads if p.component_reference == reference and p.pad_number == pad_number),
            None,
        )

    def get_net_by_name(self, net_name: str) -> Optional[Net]:
        return next((n for n in self.nets if n.net_name == net_name), None)

    def get_net_by_id(self, net_id: int) -> Optional[Net]:
        return next((n for n in self.nets if n.net_id == net_id), None)
