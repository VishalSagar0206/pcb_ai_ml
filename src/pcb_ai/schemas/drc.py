"""Normalized DRC violation schema and violation taxonomy (Phase 2 & 3).

Raw KiCad DRC output (JSON from `kicad-cli pcb drc --format json`, or legacy
text/XML reports) is parsed and normalized into the schema below. The raw
DRC message is always preserved verbatim as evidence; normalization never
discards or rewrites the original text.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

DRC_SCHEMA_VERSION = "1.0"


class ViolationTaxonomy(str, Enum):
    """Normalized violation types (Phase 3). Unknown types map to OTHER and
    must retain their raw KiCad rule identifier in `raw_rule_id`."""

    CLEARANCE = "clearance"
    TRACK_WIDTH = "track_width"
    MIN_TRACK_WIDTH = "min_track_width"
    MIN_VIA_DIAMETER = "min_via_diameter"
    MIN_DRILL = "min_drill"
    COPPER_TO_EDGE = "copper_to_edge"
    HOLE_TO_HOLE = "hole_to_hole"
    COURTYARD = "courtyard_overlap"
    SILKSCREEN_OVERLAP = "silkscreen_overlap"
    UNCONNECTED = "unconnected_items"
    SHORT_CIRCUIT = "short_circuit"
    MISSING_CONNECTION = "missing_connection"
    DIFF_PAIR = "differential_pair_violation"
    LENGTH_MISMATCH = "length_mismatch"
    IMPEDANCE = "impedance_violation"
    ZONE_CLEARANCE = "zone_clearance"
    ANNULAR_RING = "annular_ring_violation"
    BOARD_EDGE = "board_edge_violation"
    FOOTPRINT_LIBRARY = "footprint_library_violation"
    OTHER = "other"
    UNKNOWN = "unknown"


# Maps KiCad's internal DRC rule identifiers (as emitted by kicad-cli / pcbnew)
# to our normalized taxonomy. Not exhaustive; unmapped ids fall back to OTHER.
KICAD_RULE_ID_TAXONOMY_MAP: dict[str, ViolationTaxonomy] = {
    "clearance": ViolationTaxonomy.CLEARANCE,
    "edge_clearance": ViolationTaxonomy.COPPER_TO_EDGE,
    "copper_edge_clearance": ViolationTaxonomy.COPPER_TO_EDGE,
    "track_width": ViolationTaxonomy.TRACK_WIDTH,
    "track_dangling": ViolationTaxonomy.UNCONNECTED,
    "via_dangling": ViolationTaxonomy.UNCONNECTED,
    "drill_out_of_range": ViolationTaxonomy.MIN_DRILL,
    "annular_width": ViolationTaxonomy.ANNULAR_RING,
    "hole_clearance": ViolationTaxonomy.HOLE_TO_HOLE,
    "hole_near_hole": ViolationTaxonomy.HOLE_TO_HOLE,
    "courtyards_overlap": ViolationTaxonomy.COURTYARD,
    "silk_over_copper": ViolationTaxonomy.SILKSCREEN_OVERLAP,
    "silk_overlap": ViolationTaxonomy.SILKSCREEN_OVERLAP,
    "unconnected_items": ViolationTaxonomy.UNCONNECTED,
    "shorting_items": ViolationTaxonomy.SHORT_CIRCUIT,
    "net_conflict": ViolationTaxonomy.SHORT_CIRCUIT,
    "diff_pair_gap_out_of_range": ViolationTaxonomy.DIFF_PAIR,
    "diff_pair_uncoupled_length_too_long": ViolationTaxonomy.DIFF_PAIR,
    "length_out_of_range": ViolationTaxonomy.LENGTH_MISMATCH,
    "zones_intersect": ViolationTaxonomy.ZONE_CLEARANCE,
    "zone_has_empty_net": ViolationTaxonomy.ZONE_CLEARANCE,
    "edge_clearance_zone": ViolationTaxonomy.ZONE_CLEARANCE,
    "malformed_courtyard": ViolationTaxonomy.COURTYARD,
    "lib_footprint_mismatch": ViolationTaxonomy.FOOTPRINT_LIBRARY,
    "lib_footprint_issues": ViolationTaxonomy.FOOTPRINT_LIBRARY,
    "footprint_type_mismatch": ViolationTaxonomy.FOOTPRINT_LIBRARY,
}


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ViolationLocation(BaseModel):
    x: Optional[float] = None
    y: Optional[float] = None


class ViolationItem(BaseModel):
    """A single design object referenced by a DRC violation."""

    type: str  # component | pad | net | track | via | zone | text | unknown
    reference: Optional[str] = None
    pad: Optional[str] = None
    net: Optional[str] = None
    description: Optional[str] = None


class DRCViolation(BaseModel):
    """Normalized DRC violation (Phase 2). `raw_drc_message` and `raw` must
    never be mutated -- they are the deterministic evidence of record."""

    schema_version: str = DRC_SCHEMA_VERSION
    violation_id: str
    rule_type: ViolationTaxonomy = ViolationTaxonomy.UNKNOWN
    raw_rule_id: Optional[str] = None
    severity: Severity = Severity.MEDIUM
    message: str
    layer: Optional[str] = None
    location: Optional[ViolationLocation] = None
    items: list[ViolationItem] = Field(default_factory=list)
    actual_value: Optional[float] = None
    required_value: Optional[float] = None
    unit: Optional[str] = None
    raw_drc_message: str
    raw: dict[str, Any] = Field(default_factory=dict)
    source: str = "kicad_drc"


class DRCRunResult(BaseModel):
    """Full result of a DRC invocation, preserving the original artifact."""

    schema_version: str = DRC_SCHEMA_VERSION
    board_id: str
    kicad_version: Optional[str] = None
    executed: bool
    exit_code: Optional[int] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    raw_report_path: Optional[str] = None
    raw_report: Optional[dict[str, Any]] = None
    violations: list[DRCViolation] = Field(default_factory=list)
    unconnected_count: int = 0
    error: Optional[str] = None
    fixture_used: bool = False
