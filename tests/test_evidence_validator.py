"""Unit tests for evidence validation (Phase 12)."""
from __future__ import annotations

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
from pcb_ai.validation.evidence_validator import validate_diagnosis


def _base_diagnosis(violation_id: str) -> ViolationDiagnosis:
    return ViolationDiagnosis(
        violation_id=violation_id,
        classification=Classification(type="clearance", severity=Severity.HIGH, confidence=0.9),
        summary="test",
        affected_objects=[AffectedObject(type="pad", reference="U3", pad="4", net="SPI_CLK")],
        root_cause=RootCause(explanation="test", confidence=0.9),
        engineering_impact=EngineeringImpact(description="test"),
        recommended_fix=RecommendedFix(description="test"),
        evidence=[EvidenceItem(source_type="drc", source_id=violation_id, claim="test")],
    )


def test_valid_diagnosis_passes_validation(sample_graph, sample_drc_result):
    violation = next(v for v in sample_drc_result.violations if v.rule_type.value == "clearance")
    diagnosis = _base_diagnosis(violation.violation_id)
    validate_diagnosis(diagnosis, violation, sample_graph, known_knowledge_chunk_ids=set())
    assert diagnosis.validation_passed is True
    assert diagnosis.validation_errors == []


def test_fabricated_component_reference_fails_validation(sample_graph, sample_drc_result):
    violation = next(v for v in sample_drc_result.violations if v.rule_type.value == "clearance")
    diagnosis = _base_diagnosis(violation.violation_id)
    diagnosis.affected_objects.append(AffectedObject(type="component", reference="U999_DOES_NOT_EXIST"))
    validate_diagnosis(diagnosis, violation, sample_graph, known_knowledge_chunk_ids=set())
    assert diagnosis.validation_passed is False
    assert any("U999_DOES_NOT_EXIST" in e for e in diagnosis.validation_errors)
    assert diagnosis.requires_human_review is True


def test_fabricated_knowledge_citation_fails_validation(sample_graph, sample_drc_result):
    violation = next(v for v in sample_drc_result.violations if v.rule_type.value == "clearance")
    diagnosis = _base_diagnosis(violation.violation_id)
    diagnosis.evidence.append(
        EvidenceItem(source_type="datasheet", source_id="nonexistent-chunk-id", claim="fabricated claim")
    )
    validate_diagnosis(diagnosis, violation, sample_graph, known_knowledge_chunk_ids={"real-chunk-1"})
    assert diagnosis.validation_passed is False


def test_generic_pcb_context_label_is_accepted(sample_graph, sample_drc_result):
    """Live testing against the configured LLM showed it commonly cites a
    generic 'pcb-context' label instead of a specific component/net/pad id
    when the claim draws on the overall retrieved context rather than one
    object. This should be accepted, not penalized as fabricated."""
    violation = next(v for v in sample_drc_result.violations if v.rule_type.value == "clearance")
    diagnosis = _base_diagnosis(violation.violation_id)
    diagnosis.evidence.append(
        EvidenceItem(source_type="pcb", source_id="pcb-context", claim="Both pads belong to net SPI_CLK")
    )
    validate_diagnosis(diagnosis, violation, sample_graph, known_knowledge_chunk_ids=set())
    assert diagnosis.validation_passed is True


def test_validation_failure_reduces_confidence(sample_graph, sample_drc_result):
    violation = next(v for v in sample_drc_result.violations if v.rule_type.value == "clearance")
    diagnosis = _base_diagnosis(violation.violation_id)
    original_confidence = diagnosis.classification.confidence
    diagnosis.affected_objects.append(AffectedObject(type="component", reference="FAKE"))
    validate_diagnosis(diagnosis, violation, sample_graph, known_knowledge_chunk_ids=set())
    assert diagnosis.classification.confidence < original_confidence
