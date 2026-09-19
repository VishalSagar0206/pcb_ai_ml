"""Dev-only generator for the "medium" and "large" bundled sample boards
used to visually stress-test the frontend (Board Explorer canvas at
different scales/component counts, violation-list scrolling, and the full
severity/taxonomy badge range) beyond the original tiny 4-component demo
board.

Not part of the `pcb_ai` package -- run manually with:

    python scripts/generate_sample_boards.py

Regenerates:
    data/samples/medium_board.kicad_pcb + medium_drc_report.json
    data/samples/large_board.kicad_pcb  + large_drc_report.json
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "samples"


@dataclass
class PadSpec:
    number: str
    dx: float
    dy: float
    net_id: int
    net_name: str
    size: tuple[float, float] = (0.9, 0.95)
    shape: str = "roundrect"


@dataclass
class ComponentSpec:
    reference: str
    value: str
    footprint: str
    x: float
    y: float
    side: str = "top"
    pads: list[PadSpec] = field(default_factory=list)

    @property
    def uuid_prefix(self) -> str:
        return self.reference.lower()


def pad_uuid(comp: ComponentSpec, pad: PadSpec) -> str:
    return f"{comp.uuid_prefix}-p{pad.number}"


def render_footprint(comp: ComponentSpec) -> str:
    layer = "F.Cu" if comp.side == "top" else "B.Cu"
    silk = "F.SilkS" if comp.side == "top" else "B.SilkS"
    fab = "F.Fab" if comp.side == "top" else "B.Fab"
    lines = [
        f'  (footprint "{comp.footprint}" (layer "{layer}")',
        f'    (uuid "{comp.uuid_prefix}-uuid")',
        f"    (at {comp.x} {comp.y} 0)",
        f'    (property "Reference" "{comp.reference}" (at 0 -2 0) (layer "{silk}"))',
        f'    (property "Value" "{comp.value}" (at 0 2 0) (layer "{fab}"))',
        f'    (fp_text reference "{comp.reference}" (at 0 -2 0) (layer "{silk}"))',
        f'    (fp_text value "{comp.value}" (at 0 2 0) (layer "{fab}"))',
    ]
    for pad in comp.pads:
        lines.append(
            f'    (pad "{pad.number}" smd {pad.shape} (at {pad.dx} {pad.dy} 0) '
            f"(size {pad.size[0]} {pad.size[1]}) "
            f'(layers "{layer}" "{"F.Paste" if comp.side == "top" else "B.Paste"}" '
            f'"{"F.Mask" if comp.side == "top" else "B.Mask"}") '
            f'(net {pad.net_id} "{pad.net_name}") (uuid "{pad_uuid(comp, pad)}"))'
        )
    lines.append("  )")
    return "\n".join(lines)


def build_board(
    title: str,
    width: float,
    height: float,
    components: list[ComponentSpec],
    nets: dict[int, str],
    tracks: list[tuple[str, float, float, float, float, float, int]],
    vias: list[tuple[str, float, float, float, float, int]],
    zones: list[tuple[str, str, int, list[tuple[float, float]]]] | None = None,
) -> str:
    net_lines = "\n".join(f'  (net {nid} "{name}")' for nid, name in sorted(nets.items()))
    fp_lines = "\n".join(render_footprint(c) for c in components)
    track_lines = "\n".join(
        f'  (segment (start {x1} {y1}) (end {x2} {y2}) (width {w}) (layer "F.Cu") (net {net_id}) (uuid "{tid}"))'
        for tid, x1, y1, x2, y2, w, net_id in tracks
    )
    via_lines = "\n".join(
        f'  (via (at {x} {y}) (size {size}) (drill {drill}) (layers "F.Cu" "B.Cu") (net {net_id}) (uuid "{vid}"))'
        for vid, x, y, size, drill, net_id in vias
    )
    zone_lines = ""
    if zones:
        zone_blocks = []
        for zid, net_name, net_id, points in zones:
            pts = " ".join(f"(xy {x} {y})" for x, y in points)
            zone_blocks.append(
                f'  (zone (net {net_id}) (net_name "{net_name}") (layer "B.Cu") (uuid "{zid}")\n'
                f"    (connect_pads (clearance 0.2))\n"
                f"    (min_thickness 0.2)\n"
                f"    (polygon (pts {pts}))\n"
                f"  )"
            )
        zone_lines = "\n".join(zone_blocks)
    return f"""(kicad_pcb (version 20221018) (generator pcbnew)

  (general
    (thickness 1.6)
  )

  (paper "A4")
  (title_block
    (title "{title}")
    (rev "B1")
  )

  (layers
    (0 "F.Cu" signal)
    (31 "B.Cu" signal)
    (36 "B.SilkS" user "B.Silkscreen")
    (37 "F.SilkS" user "F.Silkscreen")
    (38 "B.Mask" user)
    (39 "F.Mask" user)
    (44 "Edge.Cuts" user)
  )

  (setup
    (pad_to_mask_clearance 0.05)
    (solder_mask_min_width 0.1)
  )

{net_lines}

  (gr_line (start 0 0) (end {width} 0) (layer "Edge.Cuts") (width 0.1) (uuid "edge-1"))
  (gr_line (start {width} 0) (end {width} {height}) (layer "Edge.Cuts") (width 0.1) (uuid "edge-2"))
  (gr_line (start {width} {height}) (end 0 {height}) (layer "Edge.Cuts") (width 0.1) (uuid "edge-3"))
  (gr_line (start 0 {height}) (end 0 0) (layer "Edge.Cuts") (width 0.1) (uuid "edge-4"))

{fp_lines}

{track_lines}

{zone_lines}

{via_lines}
)
"""


def medium_board() -> tuple[str, dict]:
    nets = {
        0: "",
        1: "GND",
        2: "VCC",
        3: "SPI_CLK",
        4: "SPI_MOSI",
        5: "SPI_MISO",
        6: "DATA1",
        7: "DATA2",
        8: "XTAL1",
        9: "XTAL2",
        10: "RESET",
        11: "VIN",
        12: "VOUT",
        13: "3V3",
    }

    components = [
        ComponentSpec("U1", "MCU_ARM32", "Package_QFN:QFN-32_5x5mm_P0.5mm", 20, 15, pads=[
            PadSpec("1", -1, -1, 2, "VCC"),
            PadSpec("2", 1, -1, 1, "GND"),
            PadSpec("3", -1, 1, 3, "SPI_CLK"),
            PadSpec("4", 1, 1, 4, "SPI_MOSI"),
        ]),
        ComponentSpec("U2", "AP2112K-3.3", "Package_TO_SOT_SMD:SOT-23-5", 55, 15, pads=[
            PadSpec("1", -1, 0, 11, "VIN"),
            PadSpec("2", 0, 0, 1, "GND"),
            PadSpec("3", 1, 0, 12, "VOUT"),
        ]),
        ComponentSpec("J1", "Header_4Pin", "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm", 88, 15, pads=[
            PadSpec("1", -3, 0, 2, "VCC", size=(1.2, 1.2)),
            PadSpec("2", -1, 0, 1, "GND", size=(1.2, 1.2)),
            PadSpec("3", 1, 0, 6, "DATA1", size=(1.2, 1.2)),
            PadSpec("4", 3, 0, 7, "DATA2", size=(1.2, 1.2)),
        ]),
        # R1/R2 deliberately placed almost touching -> clearance violation
        ComponentSpec("R1", "10k", "Resistor_SMD:R_0603_1608Metric", 25, 30, pads=[
            PadSpec("1", -0.75, 0, 3, "SPI_CLK"),
            PadSpec("2", 0.75, 0, 2, "VCC"),
        ]),
        ComponentSpec("R2", "10k", "Resistor_SMD:R_0603_1608Metric", 25.28, 30, pads=[
            PadSpec("1", -0.75, 0, 4, "SPI_MOSI"),
            PadSpec("2", 0.75, 0, 2, "VCC"),
        ]),
        ComponentSpec("R3", "4k7", "Resistor_SMD:R_0603_1608Metric", 40, 40, pads=[
            PadSpec("1", -0.75, 0, 5, "SPI_MISO"), PadSpec("2", 0.75, 0, 2, "VCC"),
        ]),
        ComponentSpec("R4", "4k7", "Resistor_SMD:R_0603_1608Metric", 50, 40, pads=[
            PadSpec("1", -0.75, 0, 10, "RESET"), PadSpec("2", 0.75, 0, 2, "VCC"),
        ]),
        ComponentSpec("C1", "100nF", "Capacitor_SMD:C_0402_1005Metric", 15, 20, pads=[
            PadSpec("1", -0.5, 0, 2, "VCC", size=(0.6, 0.6)), PadSpec("2", 0.5, 0, 1, "GND", size=(0.6, 0.6)),
        ]),
        ComponentSpec("C2", "1uF", "Capacitor_SMD:C_0603_1608Metric", 60, 25, pads=[
            PadSpec("1", -0.75, 0, 12, "VOUT"), PadSpec("2", 0.75, 0, 1, "GND"),
        ]),
        # C3 deliberately overlapping D1 courtyard
        ComponentSpec("C3", "10uF", "Capacitor_SMD:C_0805_2012Metric", 70, 40, pads=[
            PadSpec("1", -0.9, 0, 13, "3V3"), PadSpec("2", 0.9, 0, 1, "GND"),
        ]),
        ComponentSpec("D1", "SS14", "Diode_SMD:D_SOD-123", 70.6, 40, pads=[
            PadSpec("1", -0.9, 0, 11, "VIN"), PadSpec("2", 0.9, 0, 13, "3V3"),
        ]),
        ComponentSpec("Y1", "16MHz", "Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm", 20, 45, pads=[
            PadSpec("1", -1.4, 0, 8, "XTAL1"), PadSpec("2", 1.4, 0, 9, "XTAL2"),
        ]),
        ComponentSpec("SW1", "SW_RESET", "Button_Switch_SMD:SW_SPST_TL3342", 85, 45, pads=[
            PadSpec("1", -1.5, 0, 10, "RESET", size=(1.0, 1.0)), PadSpec("2", 1.5, 0, 1, "GND", size=(1.0, 1.0)),
        ]),
    ]

    tracks = [
        ("trk-1", 20, 16, 25, 29, 0.15, 3),
        ("trk-2", 55, 15, 60, 25, 0.15, 12),
        ("trk-3", 21, 14, 15, 20, 0.15, 2),
    ]
    vias = [("via-1", 55, 15, 0.5, 0.15, 12)]  # deliberately small drill -> min_drill violation
    # Two zones on B.Cu placed to overlap slightly -> zones_intersect violation.
    zones = [
        ("zone-gnd", "GND", 1, [(60, 30), (85, 30), (85, 50), (60, 50)]),
        ("zone-3v3", "3V3", 13, [(64, 32), (89, 32), (89, 52), (64, 52)]),
    ]

    board_text = build_board(
        "Medium Complexity Sample Board", 100, 60, components, nets, tracks, vias, zones
    )

    drc_report = {
        "$schema": "https://schemas.kicad.org/drc.v1.json",
        "coordinate_units": "mm",
        "kicad_version": "8.0.5 (fixture, not live)",
        "source": "medium_board.kicad_pcb",
        "violations": [
            {
                "type": "clearance",
                "severity": "error",
                "description": "Clearance violation (netclass 'Default' clearance 0.2000mm; actual 0.0800mm) between R1 pad 1 and R2 pad 1",
                "excluded": False,
                "items": [
                    {"description": "Pad 1 of R1", "pos": {"x": 24.25, "y": 30.0}, "uuid": "r1-p1"},
                    {"description": "Pad 1 of R2", "pos": {"x": 24.53, "y": 30.0}, "uuid": "r2-p1"},
                ],
            },
            {
                "type": "edge_clearance",
                "severity": "error",
                "description": "Copper-to-edge clearance violation (required 0.3000mm; actual 0.1200mm) on J1 pad 4",
                "excluded": False,
                "items": [{"description": "Pad 4 of J1 on F.Cu", "pos": {"x": 91.0, "y": 15.0}, "uuid": "j1-p4"}],
            },
            {
                "type": "annular_width",
                "severity": "warning",
                "description": "Annular ring width violation (netclass 'Default' min annular width 0.1500mm; actual 0.0900mm)",
                "excluded": False,
                "items": [{"description": "Via on net VOUT", "pos": {"x": 55.0, "y": 15.0}, "uuid": "via-1"}],
            },
            {
                "type": "courtyards_overlap",
                "severity": "warning",
                "description": "Courtyard overlap between footprints C3 and D1",
                "excluded": False,
                "items": [
                    {"description": "Courtyard of C3", "pos": {"x": 70.0, "y": 40.0}, "uuid": "c3-uuid"},
                    {"description": "Courtyard of D1", "pos": {"x": 70.6, "y": 40.0}, "uuid": "d1-uuid"},
                ],
            },
            {
                "type": "diff_pair_gap_out_of_range",
                "severity": "warning",
                "description": "Differential pair gap out of range (required 0.1000-0.2000mm; actual 0.3500mm) on SPI_MOSI/SPI_MISO",
                "excluded": False,
                "items": [
                    {"description": "Track on net SPI_MOSI", "pos": {"x": 25.28, "y": 32.0}, "uuid": "r2-p1"},
                    {"description": "Track on net SPI_MISO", "pos": {"x": 40.0, "y": 40.0}, "uuid": "r3-p1"},
                ],
            },
            {
                "type": "zones_intersect",
                "severity": "error",
                "description": "Zone clearance violation: GND pour and 3V3 pour overlap without sufficient clearance",
                "excluded": False,
                "items": [
                    {"description": "Zone (GND) on B.Cu", "pos": {"x": 65.0, "y": 35.0}, "uuid": "zone-gnd"},
                    {"description": "Zone (3V3) on B.Cu", "pos": {"x": 66.0, "y": 36.0}, "uuid": "zone-3v3"},
                ],
            },
            {
                "type": "shorting_items",
                "severity": "error",
                "description": "Short circuit: net VCC and net GND are electrically connected via an unintended copper path near C1",
                "excluded": False,
                "items": [
                    {"description": "Pad 1 of C1 (net VCC)", "pos": {"x": 14.5, "y": 20.0}, "uuid": "c1-p1"},
                    {"description": "Pad 2 of C1 (net GND)", "pos": {"x": 15.5, "y": 20.0}, "uuid": "c1-p2"},
                ],
            },
            {
                "type": "drill_out_of_range",
                "severity": "error",
                "description": "Drill size out of range (min 0.2000mm; actual 0.1500mm) on via at (55.0, 15.0)",
                "excluded": False,
                "items": [{"description": "Via on net VOUT", "pos": {"x": 55.0, "y": 15.0}, "uuid": "via-1"}],
            },
        ],
        "unconnected_items": [
            {
                "description": "Unconnected items: net DATA2 pad has no completed route",
                "items": [{"description": "Pad 4 of J1", "pos": {"x": 91.0, "y": 15.0}, "uuid": "j1-p4"}],
            }
        ],
    }

    return board_text, drc_report


def large_board() -> tuple[str, dict]:
    nets: dict[int, str] = {0: "", 1: "GND", 2: "VCC"}
    components: list[ComponentSpec] = []
    tracks: list[tuple[str, float, float, float, float, float, int]] = []

    # Generate a grid of ~24 mixed components across a bigger board purely
    # to stress-test canvas rendering/zoom/pan and violation-list scrolling
    # at scale -- most are non-violating; a handful are deliberately placed
    # close together for a modest, realistic violation count.
    grid_refs = [
        ("U1", "MCU_ARM32", "Package_QFN:QFN-32_5x5mm_P0.5mm"),
        ("U2", "FLASH_W25Q", "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm"),
        ("U3", "GYRO_MPU6050", "Package_LGA:LGA-16_3x3mm_P0.5mm"),
        ("U4", "USB_HUB", "Package_SO:TSSOP-24_4.4x7.8mm_P0.65mm"),
    ]
    net_id = 3
    x0, y0 = 15, 15
    col_w, row_h = 22, 18

    idx = 0
    for name, val, fp in grid_refs:
        col, row = idx % 6, idx // 6
        x, y = x0 + col * col_w, y0 + row * row_h
        n1, n2 = net_id, net_id + 1
        nets[n1] = f"NET_{name}_A"
        nets[n2] = f"NET_{name}_B"
        components.append(
            ComponentSpec(name, val, fp, x, y, pads=[
                PadSpec("1", -1.2, -1.2, n1, nets[n1]),
                PadSpec("2", 1.2, -1.2, 2, "VCC"),
                PadSpec("3", -1.2, 1.2, 1, "GND"),
                PadSpec("4", 1.2, 1.2, n2, nets[n2]),
            ])
        )
        net_id += 2
        idx += 1

    passive_kinds = [
        ("R", "10k", "Resistor_SMD:R_0603_1608Metric"),
        ("C", "100nF", "Capacitor_SMD:C_0402_1005Metric"),
        ("L", "10uH", "Inductor_SMD:L_0805_2012Metric"),
        ("D", "SS14", "Diode_SMD:D_SOD-123"),
    ]
    for i in range(20):
        kind, val, fp = passive_kinds[i % len(passive_kinds)]
        ref = f"{kind}{i // len(passive_kinds) + 1}"
        col, row = idx % 6, idx // 6
        x, y = x0 + col * col_w, y0 + row * row_h
        n1 = net_id
        nets[n1] = f"NET_{ref}"
        components.append(
            ComponentSpec(ref, val, fp, x, y, pads=[
                PadSpec("1", -0.75, 0, n1, nets[n1], size=(0.6, 0.6)),
                PadSpec("2", 0.75, 0, 2, "VCC", size=(0.6, 0.6)),
            ])
        )
        net_id += 1
        idx += 1

    # Deliberate close pair for one clearance violation.
    components.append(ComponentSpec("R21", "1k", "Resistor_SMD:R_0603_1608Metric", 150, 20, pads=[
        PadSpec("1", -0.75, 0, net_id, "NET_R21", size=(0.6, 0.6)), PadSpec("2", 0.75, 0, 2, "VCC", size=(0.6, 0.6)),
    ]))
    nets[net_id] = "NET_R21"
    net_id += 1
    components.append(ComponentSpec("R22", "1k", "Resistor_SMD:R_0603_1608Metric", 150.25, 20, pads=[
        PadSpec("1", -0.75, 0, net_id, "NET_R22", size=(0.6, 0.6)), PadSpec("2", 0.75, 0, 2, "VCC", size=(0.6, 0.6)),
    ]))
    nets[net_id] = "NET_R22"
    net_id += 1

    board_text = build_board(
        "Large Stress-Test Sample Board", 170, 110, components, nets, tracks, []
    )

    drc_report = {
        "$schema": "https://schemas.kicad.org/drc.v1.json",
        "coordinate_units": "mm",
        "kicad_version": "8.0.5 (fixture, not live)",
        "source": "large_board.kicad_pcb",
        "violations": [
            {
                "type": "clearance",
                "severity": "error",
                "description": "Clearance violation (netclass 'Default' clearance 0.2000mm; actual 0.0700mm) between R21 pad 1 and R22 pad 1",
                "excluded": False,
                "items": [
                    {"description": "Pad 1 of R21", "pos": {"x": 149.25, "y": 20.0}, "uuid": "r21-p1"},
                    {"description": "Pad 1 of R22", "pos": {"x": 149.5, "y": 20.0}, "uuid": "r22-p1"},
                ],
            },
            {
                "type": "silk_overlap",
                "severity": "warning",
                "description": "Silkscreen overlap between reference text of U2 and U3",
                "excluded": False,
                "items": [
                    {"description": "Reference of U2", "pos": {"x": 37.0, "y": 13.0}, "uuid": "u2-uuid"},
                    {"description": "Reference of U3", "pos": {"x": 59.0, "y": 13.0}, "uuid": "u3-uuid"},
                ],
            },
            {
                "type": "hole_clearance",
                "severity": "warning",
                "description": "Hole-to-hole clearance violation (min 0.5000mm; actual 0.3200mm) near U4",
                "excluded": False,
                "items": [{"description": "Pad 1 of U4", "pos": {"x": 103.0, "y": 13.8}, "uuid": "u4-p1"}],
            },
            {
                "type": "lib_footprint_mismatch",
                "severity": "warning",
                "description": "Footprint library mismatch: L3 footprint differs from library definition",
                "excluded": False,
                "items": [{"description": "Footprint of L3", "pos": {"x": 59.0, "y": 51.0}, "uuid": "l3-uuid"}],
            },
        ],
        "unconnected_items": [
            {
                "description": "Unconnected items: net NET_D4 has an unrouted pad",
                "items": [{"description": "Pad 1 of D4", "pos": {"x": 125.0, "y": 51.0}, "uuid": "d4-p1"}],
            }
        ],
    }

    return board_text, drc_report


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    medium_text, medium_drc = medium_board()
    (OUT_DIR / "medium_board.kicad_pcb").write_text(medium_text, encoding="utf-8")
    (OUT_DIR / "medium_drc_report.json").write_text(json.dumps(medium_drc, indent=2), encoding="utf-8")

    large_text, large_drc = large_board()
    (OUT_DIR / "large_board.kicad_pcb").write_text(large_text, encoding="utf-8")
    (OUT_DIR / "large_drc_report.json").write_text(json.dumps(large_drc, indent=2), encoding="utf-8")

    print(f"Wrote medium_board.kicad_pcb + medium_drc_report.json ({len(medium_drc['violations'])} violations)")
    print(f"Wrote large_board.kicad_pcb + large_drc_report.json ({len(large_drc['violations'])} violations)")


if __name__ == "__main__":
    main()
