"""Shared pytest fixtures."""
from __future__ import annotations

from pathlib import Path

import pytest

from pcb_ai.context.graph import PCBGraph
from pcb_ai.drc.runner import load_fixture_drc_report
from pcb_ai.parser.kicad_pcb_parser import parse_kicad_pcb_file

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_BOARD = FIXTURES_DIR / "sample_board.kicad_pcb"
SAMPLE_DRC_REPORT = FIXTURES_DIR / "sample_drc_report.json"


@pytest.fixture()
def sample_pcb():
    return parse_kicad_pcb_file(SAMPLE_BOARD)


@pytest.fixture()
def sample_graph(sample_pcb):
    return PCBGraph(sample_pcb)


@pytest.fixture()
def sample_drc_result(sample_pcb):
    return load_fixture_drc_report(SAMPLE_DRC_REPORT, sample_pcb)
