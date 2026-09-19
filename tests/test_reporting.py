"""Unit tests for the engineering report generator (Phase 14)."""
from __future__ import annotations

from pcb_ai.reporting.report_generator import generate_report
from pcb_ai.schemas.diagnosis import (
    AffectedObject,
    Classification,
    EngineeringImpact,
    EvidenceItem,
    RecommendedFix,
    RootCause,
    ViolationDiagnosis,
)
from pcb_ai.schemas.drc import Severity


def _diagnosis_for(violation_id: str) -> ViolationDiagnosis:
    return ViolationDiagnosis(
        violation_id=violation_id,
        classification=Classification(type="clearance", severity=Severity.HIGH, confidence=0.9),
        summary="Test summary.",
        affected_objects=[AffectedObject(type="pad", reference="U3", pad="4", net="SPI_CLK")],
        root_cause=RootCause(explanation="Test root cause.", confidence=0.9),
        engineering_impact=EngineeringImpact(description="Test impact.", potential_effects=["effect 1"]),
        recommended_fix=RecommendedFix(description="Test fix.", actions=["do the thing"]),
        evidence=[EvidenceItem(source_type="drc", source_id=violation_id, claim="claim")],
        deterministic_severity=Severity.HIGH,
        llm_assessed_severity=Severity.HIGH,
        validation_passed=True,
    )


def test_report_includes_all_required_sections(sample_pcb, sample_drc_result):
    diagnoses = {v.violation_id: _diagnosis_for(v.violation_id) for v in sample_drc_result.violations}
    report = generate_report(sample_pcb, sample_drc_result, diagnoses, analysis_id="test-report")

    assert "# PCB DRC INTELLIGENCE REPORT" in report
    assert "## 1. Board Summary" in report
    assert "## 2. DRC Summary" in report
    assert "## 3. Violation-by-Violation Analysis" in report
    assert "## 4. Recurring Root Causes" in report
    assert "## 5. Design-Level Observations" in report
    assert "## 6. Uncertain Findings" in report
    assert "## 7. Recommended Next Actions" in report
    for violation_id in diagnoses:
        assert violation_id in report


def test_report_handles_missing_diagnosis_gracefully(sample_pcb, sample_drc_result):
    report = generate_report(sample_pcb, sample_drc_result, {}, analysis_id="test-report-empty")
    assert "No diagnosis available" in report


def test_report_reflects_severity_counts(sample_pcb, sample_drc_result):
    diagnoses = {v.violation_id: _diagnosis_for(v.violation_id) for v in sample_drc_result.violations}
    report = generate_report(sample_pcb, sample_drc_result, diagnoses)
    assert "high:" in report.lower()
