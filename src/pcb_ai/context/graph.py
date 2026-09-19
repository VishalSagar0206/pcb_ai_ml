"""PCB context graph (Phase 5): deterministic traversal of the
Component -> Footprint -> Pad -> Net -> Track -> Via -> Zone -> Layer
relationship graph, plus KiCad-uuid resolution used to map DRC violation
items back to concrete design objects without ever asking the LLM to guess.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal, Optional, Union

from pcb_ai.schemas.pcb import Component, DesignRule, Net, Pad, PCBDesign, Track, Via, Zone

ResolvedKind = Literal["component", "pad", "track", "via", "zone", "unknown"]


@dataclass
class ResolvedObject:
    kind: ResolvedKind
    id: str
    reference: Optional[str] = None
    pad: Optional[str] = None
    net: Optional[str] = None


class PCBGraph:
    """Deterministic index/query layer over a parsed `PCBDesign`.

    All lookups here are O(1)/O(n) deterministic operations -- no LLM
    involvement -- per the Phase 4/5 requirement that the software (not the
    model) locates relevant PCB objects.
    """

    def __init__(self, pcb: PCBDesign):
        self.pcb = pcb
        self._components_by_ref: dict[str, Component] = {c.reference: c for c in pcb.components}
        self._pads_by_id: dict[str, Pad] = {p.pad_id: p for p in pcb.pads}
        self._nets_by_name: dict[str, Net] = {n.net_name: n for n in pcb.nets if n.net_name}
        self._nets_by_id: dict[int, Net] = {n.net_id: n for n in pcb.nets}
        self._tracks_by_id: dict[str, Track] = {t.track_id: t for t in pcb.tracks}
        self._vias_by_id: dict[str, Via] = {v.via_id: v for v in pcb.vias}
        self._zones_by_id: dict[str, Zone] = {z.zone_id: z for z in pcb.zones}

        self._uuid_index: dict[str, ResolvedObject] = {}
        for c in pcb.components:
            if c.uuid:
                self._uuid_index[c.uuid] = ResolvedObject(kind="component", id=c.reference, reference=c.reference)
        for p in pcb.pads:
            if p.uuid:
                self._uuid_index[p.uuid] = ResolvedObject(
                    kind="pad", id=p.pad_id, reference=p.component_reference, pad=p.pad_number, net=p.net_name
                )
        for t in pcb.tracks:
            self._uuid_index[t.track_id] = ResolvedObject(kind="track", id=t.track_id, net=t.net_name)
        for v in pcb.vias:
            self._uuid_index[v.via_id] = ResolvedObject(kind="via", id=v.via_id, net=v.net_name)
        for z in pcb.zones:
            self._uuid_index[z.zone_id] = ResolvedObject(kind="zone", id=z.zone_id, net=z.net_name)

    # --- direct lookups -------------------------------------------------
    def get_component(self, reference: str) -> Optional[Component]:
        return self._components_by_ref.get(reference)

    def get_pad(self, reference: str, pad_number: str) -> Optional[Pad]:
        return self._pads_by_id.get(f"{reference}:{pad_number}")

    def get_pad_by_id(self, pad_id: str) -> Optional[Pad]:
        return self._pads_by_id.get(pad_id)

    def get_track(self, track_id: str) -> Optional[Track]:
        return self._tracks_by_id.get(track_id)

    def get_via(self, via_id: str) -> Optional[Via]:
        return self._vias_by_id.get(via_id)

    def get_zone(self, zone_id: str) -> Optional[Zone]:
        return self._zones_by_id.get(zone_id)

    def get_net(self, net_name: str) -> Optional[Net]:
        return self._nets_by_name.get(net_name)

    def get_net_by_id(self, net_id: int) -> Optional[Net]:
        return self._nets_by_id.get(net_id)

    def resolve_uuid(self, uuid: str) -> Optional[ResolvedObject]:
        return self._uuid_index.get(uuid)

    # --- relationship traversal ------------------------------------------
    def get_connected_components(self, net_name: str) -> list[Component]:
        net = self.get_net(net_name)
        if not net:
            return []
        return [c for ref in net.connected_components if (c := self.get_component(ref))]

    def get_tracks_for_net(self, net_name: str) -> list[Track]:
        return [t for t in self.pcb.tracks if t.net_name == net_name]

    def get_vias_for_net(self, net_name: str) -> list[Via]:
        return [v for v in self.pcb.vias if v.net_name == net_name]

    def get_zones_for_net(self, net_name: str) -> list[Zone]:
        return [z for z in self.pcb.zones if z.net_name == net_name]

    def get_pads_for_component(self, reference: str) -> list[Pad]:
        component = self.get_component(reference)
        if not component:
            return []
        return [p for pad_id in component.pads if (p := self.get_pad_by_id(pad_id))]

    # --- spatial queries --------------------------------------------------
    def get_nearby_objects(self, x: float, y: float, radius_mm: float) -> list[ResolvedObject]:
        """Deterministic radius search across pads, tracks, and vias."""
        found: list[ResolvedObject] = []

        for p in self.pcb.pads:
            if p.position and _dist(p.position.x, p.position.y, x, y) <= radius_mm:
                found.append(
                    ResolvedObject(kind="pad", id=p.pad_id, reference=p.component_reference, pad=p.pad_number, net=p.net_name)
                )
        for t in self.pcb.tracks:
            if _segment_within(t.start.x, t.start.y, t.end.x, t.end.y, x, y, radius_mm):
                found.append(ResolvedObject(kind="track", id=t.track_id, net=t.net_name))
        for v in self.pcb.vias:
            if _dist(v.position.x, v.position.y, x, y) <= radius_mm:
                found.append(ResolvedObject(kind="via", id=v.via_id, net=v.net_name))
        return found

    # --- rule lookup -------------------------------------------------------
    def get_applicable_rules(self, rule_type: Optional[str] = None) -> list[DesignRule]:
        if rule_type is None:
            return list(self.pcb.rules)
        return [r for r in self.pcb.rules if r.rule_type == rule_type]


def _dist(x1: float, y1: float, x2: float, y2: float) -> float:
    return math.hypot(x1 - x2, y1 - y2)


def _segment_within(x1: float, y1: float, x2: float, y2: float, px: float, py: float, radius: float) -> bool:
    """Point-to-segment distance <= radius (used for track proximity)."""
    dx, dy = x2 - x1, y2 - y1
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return _dist(x1, y1, px, py) <= radius
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / length_sq))
    proj_x, proj_y = x1 + t * dx, y1 + t * dy
    return _dist(proj_x, proj_y, px, py) <= radius
