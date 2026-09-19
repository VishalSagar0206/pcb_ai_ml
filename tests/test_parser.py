"""Unit tests for the KiCad .kicad_pcb parser (Phase 1)."""
from __future__ import annotations

import pytest

from pcb_ai.parser.kicad_pcb_parser import KiCadParseError, parse_kicad_pcb_text


def test_parses_board_metadata(sample_pcb):
    assert sample_pcb.board.title == "PCB DRC Intelligence Sample Board"
    assert sample_pcb.board.revision == "A1"
    assert sample_pcb.board.thickness_mm == pytest.approx(1.6)
    assert sample_pcb.board.width_mm == pytest.approx(60.0)
    assert sample_pcb.board.height_mm == pytest.approx(40.0)
    assert "F.Cu" in sample_pcb.board.layers
    assert "Edge.Cuts" in sample_pcb.board.layers


def test_parses_components_and_pads(sample_pcb):
    refs = {c.reference for c in sample_pcb.components}
    assert refs == {"U3", "R8", "C1", "R9"}

    u3 = sample_pcb.get_component("U3")
    assert u3.value == "MCU_XYZ"
    assert u3.position.x == pytest.approx(30.0)
    assert set(u3.pads) == {"U3:1", "U3:2", "U3:4"}

    pad = sample_pcb.get_pad("U3", "4")
    assert pad is not None
    assert pad.net_name == "SPI_CLK"
    assert pad.uuid == "u3-p4"


def test_parses_nets_with_connectivity(sample_pcb):
    net = sample_pcb.get_net_by_name("SPI_CLK")
    assert net is not None
    assert set(net.connected_pads) == {"U3:4", "R8:1"}
    assert set(net.connected_components) == {"U3", "R8"}


def test_parses_tracks_vias_zones(sample_pcb):
    assert len(sample_pcb.tracks) == 3
    assert len(sample_pcb.vias) == 1
    assert len(sample_pcb.zones) == 1
    zone = sample_pcb.zones[0]
    assert zone.net_name == "GND"
    assert len(zone.polygon) == 4


def test_parses_setup_rules(sample_pcb):
    rule_names = {r.rule_name for r in sample_pcb.rules}
    assert "pad_to_mask_clearance" in rule_names


def test_component_uuid_captured(sample_pcb):
    u3 = sample_pcb.get_component("U3")
    assert u3.uuid == "u3-uuid"


def test_rejects_non_kicad_pcb_content():
    with pytest.raises(KiCadParseError):
        parse_kicad_pcb_text("(not_a_pcb (foo bar))")


def test_handles_missing_optional_fields_gracefully():
    minimal = """
    (kicad_pcb (version 1) (generator test)
      (layers (0 "F.Cu" signal))
    )
    """
    pcb = parse_kicad_pcb_text(minimal, source_file="minimal.kicad_pcb")
    assert pcb.board.board_id == "minimal"
    assert pcb.components == []
    assert pcb.tracks == []
