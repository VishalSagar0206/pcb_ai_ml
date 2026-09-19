"""Deterministic baseline severity model (Phase 13).

The LLM may propose its own severity assessment, but it must never silently
replace the deterministic baseline computed here. Both are preserved on the
final `ViolationDiagnosis` (`deterministic_severity` and
`llm_assessed_severity`).
"""
from __future__ import annotations

from pcb_ai.schemas.drc import DRCViolation, Severity, ViolationTaxonomy

SEVERITY_POLICY_VERSION = "1.0"

_SEVERITY_ORDER: list[Severity] = [Severity.INFO, Severity.LOW, Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL]

# Baseline severity by normalized violation type, per the policy described
# in Phase 13. "critical" is reserved for short circuits / catastrophic
# electrical-safety violations; "high" for major clearance/power/thermal
# constraints; "medium" for routing/design constraints; "low" for
# cosmetic/silkscreen issues; "info" is not assigned a baseline here since
# no current taxonomy entry is purely informational.
_TAXONOMY_BASELINE_SEVERITY: dict[ViolationTaxonomy, Severity] = {
    ViolationTaxonomy.SHORT_CIRCUIT: Severity.CRITICAL,
    ViolationTaxonomy.CLEARANCE: Severity.HIGH,
    ViolationTaxonomy.ZONE_CLEARANCE: Severity.HIGH,
    ViolationTaxonomy.COPPER_TO_EDGE: Severity.HIGH,
    ViolationTaxonomy.UNCONNECTED: Severity.HIGH,
    ViolationTaxonomy.MISSING_CONNECTION: Severity.HIGH,
    ViolationTaxonomy.IMPEDANCE: Severity.HIGH,
    ViolationTaxonomy.BOARD_EDGE: Severity.HIGH,
    ViolationTaxonomy.TRACK_WIDTH: Severity.MEDIUM,
    ViolationTaxonomy.MIN_TRACK_WIDTH: Severity.MEDIUM,
    ViolationTaxonomy.MIN_VIA_DIAMETER: Severity.MEDIUM,
    ViolationTaxonomy.MIN_DRILL: Severity.MEDIUM,
    ViolationTaxonomy.HOLE_TO_HOLE: Severity.MEDIUM,
    ViolationTaxonomy.DIFF_PAIR: Severity.MEDIUM,
    ViolationTaxonomy.LENGTH_MISMATCH: Severity.MEDIUM,
    ViolationTaxonomy.ANNULAR_RING: Severity.MEDIUM,
    ViolationTaxonomy.OTHER: Severity.MEDIUM,
    ViolationTaxonomy.UNKNOWN: Severity.MEDIUM,
    ViolationTaxonomy.COURTYARD: Severity.LOW,
    ViolationTaxonomy.SILKSCREEN_OVERLAP: Severity.LOW,
    ViolationTaxonomy.FOOTPRINT_LIBRARY: Severity.LOW,
}


def taxonomy_baseline_severity(rule_type: ViolationTaxonomy) -> Severity:
    return _TAXONOMY_BASELINE_SEVERITY.get(rule_type, Severity.MEDIUM)


def compute_deterministic_severity(violation: DRCViolation) -> Severity:
    """Combine the taxonomy baseline with KiCad's own reported severity,
    never downgrading below whichever source considers it more severe."""
    baseline = taxonomy_baseline_severity(violation.rule_type)
    reported = violation.severity
    return max(baseline, reported, key=_SEVERITY_ORDER.index)
