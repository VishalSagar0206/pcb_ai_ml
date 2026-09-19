"""Structured LLM diagnosis output schema (Phase 9).

This is the strict contract the LLM reasoning agent must produce. It is
validated both structurally (pydantic) and semantically (Phase 12 evidence
validation, implemented in `pcb_ai.validation`).
"""
from __future__ import annotations

from typing import Optional, Union

from pydantic import BaseModel, Field

from pcb_ai.schemas.drc import Severity

DIAGNOSIS_SCHEMA_VERSION = "1.0"


class Classification(BaseModel):
    type: str
    severity: Severity
    confidence: float = Field(ge=0.0, le=1.0)


class AffectedObject(BaseModel):
    type: str
    reference: Optional[str] = None
    pad: Optional[str] = None
    net: Optional[str] = None


class DrivingRule(BaseModel):
    rule_name: str
    required_value: Optional[Union[str, float, int]] = None
    actual_value: Optional[Union[str, float, int]] = None
    unit: Optional[str] = None


class RootCause(BaseModel):
    explanation: str
    confidence: float = Field(ge=0.0, le=1.0)


class EngineeringImpact(BaseModel):
    description: str
    potential_effects: list[str] = Field(default_factory=list)


class RecommendedFix(BaseModel):
    description: str
    actions: list[str] = Field(default_factory=list)


class EvidenceItem(BaseModel):
    source_type: str  # drc | pcb | datasheet | engineering_document
    source_id: str
    location: Optional[str] = None
    claim: str


class ViolationDiagnosis(BaseModel):
    """Strict structured output produced by the LLM reasoning agent for a
    single DRC violation. See Phase 9 of the architecture spec."""

    schema_version: str = DIAGNOSIS_SCHEMA_VERSION
    violation_id: str

    classification: Classification
    summary: str
    affected_objects: list[AffectedObject] = Field(default_factory=list)
    driving_rule: Optional[DrivingRule] = None
    root_cause: RootCause
    engineering_impact: EngineeringImpact
    recommended_fix: RecommendedFix
    evidence: list[EvidenceItem] = Field(default_factory=list)
    uncertainty: list[str] = Field(default_factory=list)
    requires_human_review: bool = True

    # Preserved separately per Phase 13: never silently overwritten.
    deterministic_severity: Optional[Severity] = None
    llm_assessed_severity: Optional[Severity] = None
    severity_policy_version: Optional[str] = None

    insufficient_evidence: bool = False
    validation_passed: Optional[bool] = None
    validation_errors: list[str] = Field(default_factory=list)
