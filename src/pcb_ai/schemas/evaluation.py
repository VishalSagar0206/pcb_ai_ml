"""Evaluation dataset record schema (Phase 17)."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

EVALUATION_SCHEMA_VERSION = "1.0"


class EvaluationRecord(BaseModel):
    """One expert-labeled DRC violation used to evaluate the pipeline."""

    schema_version: str = EVALUATION_SCHEMA_VERSION
    board_id: str
    violation_id: str
    violation_type: str
    drc_ground_truth: dict[str, Any] = Field(default_factory=dict)
    pcb_context: dict[str, Any] = Field(default_factory=dict)
    engineering_context: list[dict[str, Any]] = Field(default_factory=list)
    expert_root_cause: str
    expert_impact: str
    expert_recommendation: str
    severity_ground_truth: str
    requires_human_review: bool = True
    manually_verified: bool = False
