"""Violation-driven PCB context retrieval (Phase 4).

Given a normalized `DRCViolation`, deterministically retrieve the minimal
PCB context needed to understand it: the directly referenced components/
pads/nets, their connected objects (tracks/vias/zones), nearby geometry
around the violation location, and applicable design rules.

This module never sends the *entire* PCB JSON to the LLM -- it is the
software, not the model, that locates relevant objects (per Phase 4).
"""
from __future__ import annotations

from typing import Optional

from pcb_ai.config import Settings, get_settings
from pcb_ai.context.graph import PCBGraph
from pcb_ai.schemas.context import ViolationContext
from pcb_ai.schemas.drc import DRCViolation
from pcb_ai.schemas.pcb import Component, DesignRule, Net, Pad, Track, Via, Zone

_DEFAULT_NEARBY_RADIUS_MM = 3.0

# Maps our violation taxonomy to the DesignRule.rule_type strings the
# parser emits, so "get_applicable_rules" returns rules actually relevant
# to this violation type rather than the entire rule set.
_TAXONOMY_TO_RULE_TYPE: dict[str, list[str]] = {
    "clearance": ["clearance"],
    "copper_to_edge": ["clearance"],
    "zone_clearance": ["clearance"],
    "track_width": ["clearance"],
    "min_track_width": ["clearance"],
}


class PCBContextRetriever:
    def __init__(self, graph: PCBGraph, settings: Optional[Settings] = None):
        self.graph = graph
        self.settings = settings or get_settings()

    def retrieve(self, violation: DRCViolation, nearby_radius_mm: float = _DEFAULT_NEARBY_RADIUS_MM) -> ViolationContext:
        components: dict[str, Component] = {}
        pads: dict[str, Pad] = {}
        nets: dict[str, Net] = {}
        tracks: dict[str, Track] = {}
        vias: dict[str, Via] = {}
        zones: dict[str, Zone] = {}
        nearby_ids: list[str] = []

        def add_component(reference: Optional[str]) -> None:
            if not reference:
                return
            comp = self.graph.get_component(reference)
            if comp:
                components[comp.reference] = comp

        def add_pad(reference: Optional[str], pad_number: Optional[str]) -> None:
            if not reference or not pad_number:
                return
            pad = self.graph.get_pad(reference, pad_number)
            if pad:
                pads[pad.pad_id] = pad
                add_component(reference)

        def add_net(net_name: Optional[str], expand: bool = True) -> None:
            if not net_name:
                return
            net = self.graph.get_net(net_name)
            if not net:
                return
            nets[net.net_name] = net
            if not expand:
                return
            for pad_id in net.connected_pads:
                pad = self.graph.get_pad_by_id(pad_id)
                if pad:
                    pads[pad.pad_id] = pad
            for ref in net.connected_components:
                add_component(ref)
            for t in self.graph.get_tracks_for_net(net_name):
                tracks[t.track_id] = t
            for v in self.graph.get_vias_for_net(net_name):
                vias[v.via_id] = v
            for z in self.graph.get_zones_for_net(net_name):
                zones[z.zone_id] = z

        # 1. Directly referenced objects from the violation's items.
        for item in violation.items:
            if item.type == "component":
                add_component(item.reference)
            elif item.type == "pad":
                add_pad(item.reference, item.pad)
            if item.net:
                add_net(item.net)

        # Re-resolve track/via/zone items directly from raw ids preserved on the violation.
        for raw_item in violation.raw.get("items", []) if isinstance(violation.raw, dict) else []:
            uuid = raw_item.get("uuid")
            if not uuid:
                continue
            if track := self.graph.get_track(uuid):
                tracks[uuid] = track
            elif via := self.graph.get_via(uuid):
                vias[uuid] = via
            elif zone := self.graph.get_zone(uuid):
                zones[uuid] = zone

        # 2. Nearby geometry around the violation location.
        if violation.location and violation.location.x is not None and violation.location.y is not None:
            for obj in self.graph.get_nearby_objects(violation.location.x, violation.location.y, nearby_radius_mm):
                nearby_ids.append(obj.id)
                if obj.kind == "pad":
                    pad = self.graph.get_pad_by_id(obj.id)
                    if pad:
                        pads[pad.pad_id] = pad
                        add_component(pad.component_reference)
                elif obj.kind == "track":
                    track = self.graph.get_track(obj.id)
                    if track:
                        tracks[track.track_id] = track
                elif obj.kind == "via":
                    via = self.graph.get_via(obj.id)
                    if via:
                        vias[via.via_id] = via

        # 3. Applicable design rules for this violation type.
        rule_types = _TAXONOMY_TO_RULE_TYPE.get(violation.rule_type.value, [])
        rules: list[DesignRule] = []
        for rt in rule_types:
            rules.extend(self.graph.get_applicable_rules(rt))
        if not rules:
            rules = self.graph.get_applicable_rules()

        context = ViolationContext(
            violation_id=violation.violation_id,
            components=list(components.values()),
            pads=list(pads.values()),
            nets=list(nets.values()),
            tracks=list(tracks.values()),
            vias=list(vias.values()),
            zones=list(zones.values()),
            rules=rules,
            nearby_object_ids=nearby_ids,
        )
        return self._enforce_context_limit(context)

    def _enforce_context_limit(self, context: ViolationContext) -> ViolationContext:
        max_objects = self.settings.max_pcb_context_objects
        if context.object_count() <= max_objects:
            return context
        # Trim least-critical categories first: nearby-only tracks/vias, then zones/rules.
        while context.object_count() > max_objects and context.zones:
            context.zones.pop()
        while context.object_count() > max_objects and context.tracks:
            context.tracks.pop()
        while context.object_count() > max_objects and context.vias:
            context.vias.pop()
        return context
