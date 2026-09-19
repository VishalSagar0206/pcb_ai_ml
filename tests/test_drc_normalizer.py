"""Unit tests for DRC report normalization (Phase 2/3)."""
from __future__ import annotations

from pcb_ai.drc.normalizer import normalize_drc_report
from pcb_ai.schemas.drc import Severity, ViolationTaxonomy


def test_normalizes_clearance_violation_with_uuid_resolution(sample_pcb, sample_drc_result):
    clearance = next(v for v in sample_drc_result.violations if v.rule_type == ViolationTaxonomy.CLEARANCE)
    assert clearance.required_value == 0.2
    assert clearance.actual_value == 0.09
    assert clearance.severity == Severity.HIGH

    refs = {(item.reference, item.pad) for item in clearance.items}
    assert ("U3", "4") in refs
    assert ("R8", "1") in refs


def test_preserves_raw_message_verbatim(sample_drc_result):
    for violation in sample_drc_result.violations:
        assert violation.raw_drc_message == violation.message
        assert violation.raw  # raw dict preserved


def test_unconnected_items_normalized_as_violations(sample_drc_result):
    unconnected = [v for v in sample_drc_result.violations if v.rule_type == ViolationTaxonomy.UNCONNECTED]
    assert len(unconnected) == 1
    refs = {(item.reference, item.pad) for item in unconnected[0].items}
    assert ("R8", "2") in refs
    assert ("R9", "1") in refs


def test_unknown_rule_type_falls_back_to_other(sample_pcb):
    raw_report = {
        "violations": [
            {
                "type": "some_future_kicad_rule",
                "severity": "warning",
                "description": "A brand new rule KiCad added later.",
                "items": [],
            }
        ]
    }
    violations = normalize_drc_report(raw_report, sample_pcb)
    assert len(violations) == 1
    assert violations[0].rule_type == ViolationTaxonomy.OTHER
    assert violations[0].raw_rule_id == "some_future_kicad_rule"


def test_excluded_violations_are_skipped_by_default(sample_pcb):
    raw_report = {
        "violations": [
            {"type": "clearance", "severity": "error", "description": "excluded one", "excluded": True, "items": []}
        ]
    }
    assert normalize_drc_report(raw_report, sample_pcb) == []
    included = normalize_drc_report(raw_report, sample_pcb, include_excluded=True)
    assert len(included) == 1
