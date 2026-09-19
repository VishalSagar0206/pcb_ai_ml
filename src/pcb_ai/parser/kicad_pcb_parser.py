"""Parser for KiCad `.kicad_pcb` files (S-expression format, KiCad 6/7/8/9)
into the canonical `PCBDesign` structured representation (Phase 1).

This is a best-effort structural parser: it extracts the object types
listed in the architecture spec (board, layers, components/footprints,
pads, nets, tracks, vias, zones, and whatever design-rule-like values are
present in the `setup` section). It intentionally does not implement a full
KiCad file-format writer or a complete DRC rule engine -- that
responsibility belongs to KiCad's own DRC (Phase 2).
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Optional, Union

import sexpdata

from pcb_ai.schemas.pcb import (
    BoardInfo,
    Component,
    ComponentProperty,
    DesignRule,
    Footprint,
    LayerInfo,
    Net,
    Pad,
    PCBDesign,
    Point,
    Track,
    Via,
    Zone,
)

SExpr = Union[list, sexpdata.Symbol, str, int, float]


class KiCadParseError(Exception):
    """Raised when a `.kicad_pcb` file cannot be parsed at all (e.g. not a
    valid S-expression, or missing the top-level `kicad_pcb` node)."""


def _sym_name(x: Any) -> Optional[str]:
    """Return the plain string name of a Symbol/str atom, else None."""
    if isinstance(x, sexpdata.Symbol):
        return x.value()
    if isinstance(x, str):
        return x
    return None


def _tag(expr: Any) -> Optional[str]:
    if isinstance(expr, list) and expr and isinstance(expr[0], sexpdata.Symbol):
        return expr[0].value()
    return None


def _children(expr: Any, tag: str) -> list[list]:
    """Direct child sub-expressions of `expr` whose head symbol == tag."""
    if not isinstance(expr, list):
        return []
    return [item for item in expr if isinstance(item, list) and _tag(item) == tag]


def _child(expr: Any, tag: str) -> Optional[list]:
    matches = _children(expr, tag)
    return matches[0] if matches else None


def _as_str(x: Any) -> Optional[str]:
    if x is None:
        return None
    if isinstance(x, sexpdata.Symbol):
        return x.value()
    if isinstance(x, str):
        return x
    return str(x)


def _as_float(x: Any) -> Optional[float]:
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, str):
        try:
            return float(x)
        except ValueError:
            return None
    return None


def _at(expr: Any) -> tuple[Optional[Point], Optional[float]]:
    """Parse an `(at x y [rot])` child, returning (position, rotation_deg)."""
    at_expr = _child(expr, "at")
    if not at_expr or len(at_expr) < 3:
        return None, None
    x = _as_float(at_expr[1])
    y = _as_float(at_expr[2])
    rot = _as_float(at_expr[3]) if len(at_expr) > 3 else None
    if x is None or y is None:
        return None, None
    return Point(x=x, y=y), rot


def _layer_strs(expr: Any) -> list[str]:
    layer_expr = _child(expr, "layer")
    layers_expr = _child(expr, "layers")
    result: list[str] = []
    if layer_expr:
        for item in layer_expr[1:]:
            s = _as_str(item)
            if s:
                result.append(s)
    if layers_expr:
        for item in layers_expr[1:]:
            s = _as_str(item)
            if s:
                result.append(s)
    return result


def _to_absolute(
    local: Optional[Point],
    footprint_position: Optional[Point],
    footprint_rotation: Optional[float],
) -> Optional[Point]:
    """Transform a footprint-local coordinate (e.g. a pad's `(at x y)`)
    into an absolute board coordinate by applying the footprint's rotation
    then translating by its board position."""
    if local is None:
        return None
    if footprint_position is None:
        return local
    angle_rad = math.radians(footprint_rotation or 0.0)
    cos_a, sin_a = math.cos(angle_rad), math.sin(angle_rad)
    rotated_x = local.x * cos_a - local.y * sin_a
    rotated_y = local.x * sin_a + local.y * cos_a
    return Point(x=footprint_position.x + rotated_x, y=footprint_position.y + rotated_y)


def _net_of(expr: Any) -> tuple[Optional[int], Optional[str]]:
    net_expr = _child(expr, "net")
    if not net_expr:
        return None, None
    net_id = None
    net_name = None
    if len(net_expr) > 1 and isinstance(net_expr[1], (int, float)):
        net_id = int(net_expr[1])
    if len(net_expr) > 2:
        net_name = _as_str(net_expr[2])
    return net_id, net_name


def parse_kicad_pcb_text(text: str, source_file: Optional[str] = None) -> PCBDesign:
    try:
        parsed = sexpdata.loads(text)
    except Exception as exc:  # pragma: no cover - defensive
        raise KiCadParseError(f"Failed to parse S-expression content: {exc}") from exc

    if _tag(parsed) != "kicad_pcb":
        raise KiCadParseError("File does not start with a top-level (kicad_pcb ...) node")

    root = parsed

    board = _parse_board(root, source_file)
    layers = _parse_layers(root)
    nets_by_id = _parse_top_level_nets(root)

    components: list[Component] = []
    footprints: list[Footprint] = []
    pads: list[Pad] = []

    for fp_expr in _children(root, "footprint"):
        component, footprint, fp_pads = _parse_footprint(fp_expr)
        components.append(component)
        footprints.append(footprint)
        pads.extend(fp_pads)

    tracks = _parse_tracks(root)
    vias = _parse_vias(root)
    zones = _parse_zones(root)
    rules = _parse_rules(root)

    nets = _build_nets(nets_by_id, pads, tracks, vias, zones)

    board.width_mm, board.height_mm = _board_dimensions(root)

    return PCBDesign(
        board=board,
        layers=layers,
        components=components,
        footprints=footprints,
        pads=pads,
        nets=nets,
        tracks=tracks,
        vias=vias,
        zones=zones,
        rules=rules,
        source_file=source_file,
    )


def parse_kicad_pcb_file(path: Union[str, Path]) -> PCBDesign:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"KiCad PCB file not found: {path}")
    text = path.read_text(encoding="utf-8", errors="replace")
    return parse_kicad_pcb_text(text, source_file=str(path))


def _parse_board(root: list, source_file: Optional[str]) -> BoardInfo:
    title_block = _child(root, "title_block")
    title = None
    revision = None
    if title_block:
        title_expr = _child(title_block, "title")
        rev_expr = _child(title_block, "rev")
        if title_expr and len(title_expr) > 1:
            title = _as_str(title_expr[1])
        if rev_expr and len(rev_expr) > 1:
            revision = _as_str(rev_expr[1])

    general = _child(root, "general")
    thickness = None
    if general:
        thickness_expr = _child(general, "thickness")
        if thickness_expr and len(thickness_expr) > 1:
            thickness = _as_float(thickness_expr[1])

    layer_names = [layer.name for layer in _parse_layers(root)]

    board_id = Path(source_file).stem if source_file else (title or "board")

    return BoardInfo(
        board_id=board_id,
        title=title,
        revision=revision,
        layers=layer_names,
        thickness_mm=thickness,
    )


def _parse_layers(root: list) -> list[LayerInfo]:
    layers_expr = _child(root, "layers")
    result: list[LayerInfo] = []
    if not layers_expr:
        return result
    for item in layers_expr[1:]:
        if not isinstance(item, list) or len(item) < 3:
            continue
        layer_id = item[0]
        name = _as_str(item[1])
        layer_type = _as_str(item[2])
        if not isinstance(layer_id, (int, float)) or name is None:
            continue
        result.append(LayerInfo(id=int(layer_id), name=name, type=layer_type or "unknown"))
    return result


def _parse_top_level_nets(root: list) -> dict[int, str]:
    result: dict[int, str] = {}
    for net_expr in _children(root, "net"):
        if len(net_expr) < 2:
            continue
        net_id = net_expr[1]
        net_name = _as_str(net_expr[2]) if len(net_expr) > 2 else ""
        if isinstance(net_id, (int, float)):
            result[int(net_id)] = net_name or ""
    return result


def _parse_footprint(fp_expr: list) -> tuple[Component, Footprint, list[Pad]]:
    library_id = _as_str(fp_expr[1]) if len(fp_expr) > 1 else None
    position, rotation = _at(fp_expr)

    fp_uuid_expr = _child(fp_expr, "uuid")
    fp_uuid = _as_str(fp_uuid_expr[1]) if fp_uuid_expr and len(fp_uuid_expr) > 1 else None

    layer_strs = _layer_strs(fp_expr)
    side = None
    if layer_strs:
        side = "bottom" if layer_strs[0].startswith("B.") else "top"

    reference = None
    value = None
    properties: list[ComponentProperty] = []
    for prop_expr in _children(fp_expr, "property"):
        if len(prop_expr) < 3:
            continue
        key = _as_str(prop_expr[1])
        val = _as_str(prop_expr[2])
        if key is None:
            continue
        properties.append(ComponentProperty(key=key, value=val or ""))
        if key == "Reference":
            reference = val
        elif key == "Value":
            value = val

    if reference is None or value is None:
        for text_expr in _children(fp_expr, "fp_text"):
            if len(text_expr) < 3:
                continue
            kind = _sym_name(text_expr[1])
            text_val = _as_str(text_expr[2])
            if kind == "reference" and reference is None:
                reference = text_val
            elif kind == "value" and value is None:
                value = text_val

    reference = reference or "UNKNOWN"

    pads: list[Pad] = []
    pad_ids: list[str] = []
    for pad_expr in _children(fp_expr, "pad"):
        pad = _parse_pad(pad_expr, reference, position, rotation)
        if pad is None:
            continue
        pads.append(pad)
        pad_ids.append(pad.pad_id)

    has_courtyard = any(
        any(str(layer).endswith("CrtYd") for layer in _layer_strs(sub))
        for tag in ("fp_line", "fp_rect", "fp_circle", "fp_arc", "fp_poly")
        for sub in _children(fp_expr, tag)
    )
    graphics_count = sum(
        len(_children(fp_expr, tag))
        for tag in ("fp_line", "fp_rect", "fp_circle", "fp_arc", "fp_poly", "fp_text")
    )
    fab_layer_present = any(
        any(str(layer).endswith("Fab") for layer in _layer_strs(sub))
        for tag in ("fp_line", "fp_rect", "fp_circle", "fp_arc", "fp_poly", "fp_text")
        for sub in _children(fp_expr, tag)
    )

    component = Component(
        reference=reference,
        value=value,
        footprint=library_id,
        library_id=library_id,
        position=position,
        rotation_deg=rotation,
        side=side,
        properties=properties,
        pads=pad_ids,
        uuid=fp_uuid,
    )
    footprint = Footprint(
        reference=reference,
        value=value,
        library_link=library_id,
        pads=pad_ids,
        has_courtyard=has_courtyard,
        graphics_count=graphics_count,
        fab_layer_present=fab_layer_present,
    )
    return component, footprint, pads


def _parse_pad(
    pad_expr: list,
    component_reference: str,
    footprint_position: Optional[Point],
    footprint_rotation: Optional[float],
) -> Optional[Pad]:
    if len(pad_expr) < 2:
        return None
    pad_number = _as_str(pad_expr[1])
    if pad_number is None:
        return None
    pad_type = _sym_name(pad_expr[2]) if len(pad_expr) > 2 else None
    shape = _sym_name(pad_expr[3]) if len(pad_expr) > 3 else None

    local_position, _rot = _at(pad_expr)
    # Pad `(at x y)` coordinates in KiCad are LOCAL to the footprint, not
    # absolute board coordinates -- they must be rotated by the footprint's
    # rotation and translated by the footprint's board position before use
    # in any spatial query (clearance/nearby-object lookups).
    position = _to_absolute(local_position, footprint_position, footprint_rotation)

    size_expr = _child(pad_expr, "size")
    size = None
    if size_expr and len(size_expr) >= 3:
        sx = _as_float(size_expr[1])
        sy = _as_float(size_expr[2])
        if sx is not None and sy is not None:
            size = {"x": sx, "y": sy}

    drill_expr = _child(pad_expr, "drill")
    drill_mm = None
    if drill_expr and len(drill_expr) > 1:
        drill_mm = _as_float(drill_expr[1])

    layers = _layer_strs(pad_expr)
    net_id, net_name = _net_of(pad_expr)
    uuid_expr = _child(pad_expr, "uuid")
    pad_uuid = _as_str(uuid_expr[1]) if uuid_expr and len(uuid_expr) > 1 else None

    return Pad(
        component_reference=component_reference,
        pad_number=pad_number,
        pad_type=pad_type,
        shape=shape,
        position=position,
        size=size,
        drill_mm=drill_mm,
        layers=layers,
        net_id=net_id,
        net_name=net_name,
        uuid=pad_uuid,
    )


def _parse_tracks(root: list) -> list[Track]:
    tracks: list[Track] = []
    for idx, seg_expr in enumerate(_children(root, "segment")):
        start_expr = _child(seg_expr, "start")
        end_expr = _child(seg_expr, "end")
        width_expr = _child(seg_expr, "width")
        if not start_expr or not end_expr or len(start_expr) < 3 or len(end_expr) < 3:
            continue
        start = Point(x=_as_float(start_expr[1]) or 0.0, y=_as_float(start_expr[2]) or 0.0)
        end = Point(x=_as_float(end_expr[1]) or 0.0, y=_as_float(end_expr[2]) or 0.0)
        width_mm = _as_float(width_expr[1]) if width_expr and len(width_expr) > 1 else 0.0
        layer_strs = _layer_strs(seg_expr)
        net_id, net_name = _net_of(seg_expr)
        uuid_expr = _child(seg_expr, "uuid")
        track_id = _as_str(uuid_expr[1]) if uuid_expr and len(uuid_expr) > 1 else f"track_{idx}"
        tracks.append(
            Track(
                track_id=track_id or f"track_{idx}",
                layer=layer_strs[0] if layer_strs else "unknown",
                start=start,
                end=end,
                width_mm=width_mm or 0.0,
                net_id=net_id,
                net_name=net_name,
            )
        )
    return tracks


def _parse_vias(root: list) -> list[Via]:
    vias: list[Via] = []
    for idx, via_expr in enumerate(_children(root, "via")):
        position, _rot = _at(via_expr)
        size_expr = _child(via_expr, "size")
        drill_expr = _child(via_expr, "drill")
        if position is None:
            continue
        diameter_mm = _as_float(size_expr[1]) if size_expr and len(size_expr) > 1 else 0.0
        drill_mm = _as_float(drill_expr[1]) if drill_expr and len(drill_expr) > 1 else 0.0
        layers = _layer_strs(via_expr)
        net_id, net_name = _net_of(via_expr)
        uuid_expr = _child(via_expr, "uuid")
        via_id = _as_str(uuid_expr[1]) if uuid_expr and len(uuid_expr) > 1 else f"via_{idx}"
        vias.append(
            Via(
                via_id=via_id or f"via_{idx}",
                position=position,
                diameter_mm=diameter_mm or 0.0,
                drill_mm=drill_mm or 0.0,
                layers=layers,
                net_id=net_id,
                net_name=net_name,
            )
        )
    return vias


def _parse_zones(root: list) -> list[Zone]:
    zones: list[Zone] = []
    for idx, zone_expr in enumerate(_children(root, "zone")):
        layer_strs = _layer_strs(zone_expr)
        net_id, net_name = _net_of(zone_expr)
        net_name_expr = _child(zone_expr, "net_name")
        if net_name is None and net_name_expr and len(net_name_expr) > 1:
            net_name = _as_str(net_name_expr[1])

        connect_pads_expr = _child(zone_expr, "connect_pads")
        clearance_mm = None
        if connect_pads_expr:
            clearance_expr = _child(connect_pads_expr, "clearance")
            if clearance_expr and len(clearance_expr) > 1:
                clearance_mm = _as_float(clearance_expr[1])

        polygon: list[Point] = []
        polygon_expr = _child(zone_expr, "polygon")
        if polygon_expr:
            pts_expr = _child(polygon_expr, "pts")
            if pts_expr:
                for xy_expr in _children(pts_expr, "xy"):
                    if len(xy_expr) >= 3:
                        px = _as_float(xy_expr[1])
                        py = _as_float(xy_expr[2])
                        if px is not None and py is not None:
                            polygon.append(Point(x=px, y=py))

        uuid_expr = _child(zone_expr, "uuid")
        zone_id = _as_str(uuid_expr[1]) if uuid_expr and len(uuid_expr) > 1 else f"zone_{idx}"

        zones.append(
            Zone(
                zone_id=zone_id or f"zone_{idx}",
                layer=layer_strs[0] if layer_strs else "unknown",
                net_id=net_id,
                net_name=net_name,
                clearance_mm=clearance_mm,
                polygon=polygon,
            )
        )
    return zones


# Setup keys we surface as best-effort DesignRule entries. Not exhaustive --
# full design-rule semantics live in KiCad's own DRC engine (Phase 2).
_SETUP_RULE_KEYS: dict[str, str] = {
    "pad_to_mask_clearance": "clearance",
    "solder_mask_min_width": "clearance",
    "pad_to_paste_clearance": "clearance",
    "grid_origin": "origin",
    "aux_axis_origin": "origin",
}


def _parse_rules(root: list) -> list[DesignRule]:
    setup_expr = _child(root, "setup")
    rules: list[DesignRule] = []
    if not setup_expr:
        return rules
    for key, rule_type in _SETUP_RULE_KEYS.items():
        entry = _child(setup_expr, key)
        if not entry or len(entry) < 2:
            continue
        value = _as_float(entry[1])
        rules.append(
            DesignRule(
                rule_name=key,
                rule_type=rule_type,
                value=value,
                unit="mm",
                raw={"setup_key": key, "raw_values": [str(v) for v in entry[1:]]},
            )
        )
    return rules


def _board_dimensions(root: list) -> tuple[Optional[float], Optional[float]]:
    """Best-effort board width/height from Edge.Cuts graphics bounding box."""
    xs: list[float] = []
    ys: list[float] = []

    def collect_points(expr: list) -> None:
        for tag in ("start", "end", "center"):
            sub = _child(expr, tag)
            if sub and len(sub) >= 3:
                x, y = _as_float(sub[1]), _as_float(sub[2])
                if x is not None and y is not None:
                    xs.append(x)
                    ys.append(y)
        pts = _child(expr, "pts")
        if pts:
            for xy_expr in _children(pts, "xy"):
                if len(xy_expr) >= 3:
                    x, y = _as_float(xy_expr[1]), _as_float(xy_expr[2])
                    if x is not None and y is not None:
                        xs.append(x)
                        ys.append(y)

    for tag in ("gr_line", "gr_rect", "gr_poly", "gr_arc", "gr_circle"):
        for expr in _children(root, tag):
            layer_strs = _layer_strs(expr)
            if any(layer == "Edge.Cuts" for layer in layer_strs):
                collect_points(expr)

    if not xs or not ys:
        return None, None
    return (max(xs) - min(xs)), (max(ys) - min(ys))


def _build_nets(
    nets_by_id: dict[int, str],
    pads: list[Pad],
    tracks: list[Track],
    vias: list[Via],
    zones: list[Zone],
) -> list[Net]:
    nets: dict[int, Net] = {
        net_id: Net(net_id=net_id, net_name=name) for net_id, name in nets_by_id.items()
    }

    def ensure_net(net_id: Optional[int], net_name: Optional[str]) -> Optional[Net]:
        if net_id is None:
            return None
        if net_id not in nets:
            nets[net_id] = Net(net_id=net_id, net_name=net_name or "")
        return nets[net_id]

    for pad in pads:
        net = ensure_net(pad.net_id, pad.net_name)
        if net is not None:
            net.connected_pads.append(pad.pad_id)
            if pad.component_reference not in net.connected_components:
                net.connected_components.append(pad.component_reference)

    for track in tracks:
        ensure_net(track.net_id, track.net_name)
    for via in vias:
        ensure_net(via.net_id, via.net_name)
    for zone in zones:
        ensure_net(zone.net_id, zone.net_name)

    return sorted(nets.values(), key=lambda n: n.net_id)
