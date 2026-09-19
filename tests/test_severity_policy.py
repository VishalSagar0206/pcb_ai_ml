"""Unit tests for the deterministic severity policy (Phase 13)."""
from __future__ import annotations

from pcb_ai.schemas.drc import Severity, ViolationTaxonomy
from pcb_ai.severity.policy import compute_deterministic_severity, taxonomy_baseline_severity


def test_short_circuit_is_always_critical():
    assert taxonomy_baseline_severity(ViolationTaxonomy.SHORT_CIRCUIT) == Severity.CRITICAL


def test_silkscreen_is_low_baseline():
    assert taxonomy_baseline_severity(ViolationTaxonomy.SILKSCREEN_OVERLAP) == Severity.LOW


def test_deterministic_severity_never_downgrades_kicad_reported_severity(sample_drc_result):
    silkscreen_violation = next(v for v in sample_drc_result.violations if v.rule_type == ViolationTaxonomy.OTHER)
    # KiCad reported this as a "warning" (-> MEDIUM); even though our
    # taxonomy baseline for OTHER is MEDIUM too, the combination must never
    # be lower than either source.
    result = compute_deterministic_severity(silkscreen_violation)
    assert result in (Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL)


def test_unknown_taxonomy_defaults_to_medium():
    assert taxonomy_baseline_severity(ViolationTaxonomy.UNKNOWN) == Severity.MEDIUM
