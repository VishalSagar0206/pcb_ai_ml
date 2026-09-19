"""Evidence validation (Phase 12): sanity-checks the LLM's structured
diagnosis against the deterministic evidence it was given, before the
result is accepted as final. Never trusts the LLM's self-reported
confidence -- every check here is implemented in plain Python against the
PCB graph, the raw DRC violation, and the exact knowledge chunks supplied.
"""
from __future__ import annotations

from typing import Optional

from pcb_ai.context.graph import PCBGraph
from pcb_ai.schemas.diagnosis import ViolationDiagnosis
from pcb_ai.schemas.drc import DRCViolation

_NUMERIC_TOLERANCE_ABS = 0.01  # mm
_NUMERIC_TOLERANCE_REL = 0.05  # 5%


def _numbers_match(reported: Optional[float], expected: Optional[float]) -> bool:
    if reported is None or expected is None:
        return True  # nothing to compare -- not a mismatch
    diff = abs(reported - expected)
    if diff <= _NUMERIC_TOLERANCE_ABS:
        return True
    if expected != 0 and diff / abs(expected) <= _NUMERIC_TOLERANCE_REL:
        return True
    return False


def _to_float(value) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_known_pcb_reference(source_id: str, graph: PCBGraph) -> bool:
    """Lenient PCB-evidence source check: accepts exact component/net/pad
    identifiers, and a small set of generic category labels models
    sometimes use (e.g. "nets", "components") instead of a specific id.
    Rejects anything that looks like a specific but non-existent object."""
    if not source_id:
        return False
    generic_labels = {
        "nets", "net", "components", "component", "pads", "pad", "tracks", "track",
        "vias", "via", "zones", "zone", "pcb", "board",
        "pcb-context", "pcb_context", "context", "pcb context",
    }
    if source_id.lower() in generic_labels:
        return True
    if graph.get_component(source_id) is not None:
        return True
    if graph.get_net(source_id) is not None:
        return True
    if ":" in source_id:
        ref, _, pad_number = source_id.partition(":")
        if graph.get_pad(ref, pad_number) is not None:
            return True
    if graph.resolve_uuid(source_id) is not None:
        return True
    return False


def validate_diagnosis(
    diagnosis: ViolationDiagnosis,
    violation: DRCViolation,
    graph: PCBGraph,
    known_knowledge_chunk_ids: set[str],
) -> ViolationDiagnosis:
    """Validates `diagnosis` in place (returns the same, possibly amended,
    object) and sets `validation_passed` / `validation_errors`."""
    errors: list[str] = []

    # 1-3: every referenced component/pad/net must actually exist on the board.
    for obj in diagnosis.affected_objects:
        if obj.reference and graph.get_component(obj.reference) is None:
            errors.append(f"affected_objects references unknown component '{obj.reference}'")
            continue
        if obj.reference and obj.pad and graph.get_pad(obj.reference, obj.pad) is None:
            errors.append(f"affected_objects references unknown pad '{obj.reference}:{obj.pad}'")
        if obj.net and graph.get_net(obj.net) is None:
            errors.append(f"affected_objects references unknown net '{obj.net}'")

    # 4: numeric claims in driving_rule must match the deterministic DRC evidence.
    if diagnosis.driving_rule is not None:
        reported_required = _to_float(diagnosis.driving_rule.required_value)
        reported_actual = _to_float(diagnosis.driving_rule.actual_value)
        if not _numbers_match(reported_required, violation.required_value):
            errors.append(
                f"driving_rule.required_value ({diagnosis.driving_rule.required_value}) does not match "
                f"DRC evidence ({violation.required_value})"
            )
        if not _numbers_match(reported_actual, violation.actual_value):
            errors.append(
                f"driving_rule.actual_value ({diagnosis.driving_rule.actual_value}) does not match "
                f"DRC evidence ({violation.actual_value})"
            )

    # 5-7: every evidence item must cite a source we actually supplied -- no
    # fabricated datasheet/engineering-document/DRC references.
    for item in diagnosis.evidence:
        if item.source_type == "drc" and item.source_id != violation.violation_id:
            errors.append(f"evidence cites DRC source_id '{item.source_id}' but violation_id is '{violation.violation_id}'")
        elif item.source_type in ("datasheet", "engineering_document"):
            if item.source_id not in known_knowledge_chunk_ids:
                errors.append(
                    f"evidence cites {item.source_type} source_id '{item.source_id}' which was not "
                    "among the retrieved knowledge chunks"
                )
        elif item.source_type == "pcb":
            if not _is_known_pcb_reference(item.source_id, graph):
                errors.append(f"evidence cites pcb source_id '{item.source_id}' which does not match any known PCB object")

    diagnosis.validation_errors = errors
    diagnosis.validation_passed = len(errors) == 0

    if errors:
        diagnosis.requires_human_review = True
        diagnosis.classification.confidence = round(diagnosis.classification.confidence * 0.5, 4)
        diagnosis.root_cause.confidence = round(diagnosis.root_cause.confidence * 0.5, 4)
        diagnosis.uncertainty.extend([f"evidence_validation_failed: {e}" for e in errors])

    return diagnosis
