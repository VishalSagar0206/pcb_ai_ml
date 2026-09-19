"""Normalization of raw KiCad DRC JSON reports into our `DRCViolation`
schema (Phase 2/3). Preserves the original message verbatim as evidence
and enriches each violation with deterministic PCB-object references
resolved via KiCad object uuids -- never via LLM guesswork.

Expected raw report shape (KiCad 7+ `kicad-cli pcb drc --format json`):

    {
      "$schema": "https://schemas.kicad.org/drc.v1.json",
      "coordinate_units": "mm",
      "kicad_version": "...",
      "source": "board.kicad_pcb",
      "violations": [
        {
          "type": "clearance",
          "severity": "error" | "warning" | "ignore",
          "description": "...",
          "excluded": false,
          "items": [{"description": "...", "pos": {"x":.., "y":..}, "uuid": "..."}]
        }
      ],
      "unconnected_items": [...]
    }
"""
from __future__ import annotations

import re
from typing import Any, Optional

from pcb_ai.context.graph import PCBGraph
from pcb_ai.schemas.drc import (
    KICAD_RULE_ID_TAXONOMY_MAP,
    DRCViolation,
    Severity,
    ViolationItem,
    ViolationLocation,
    ViolationTaxonomy,
)
from pcb_ai.schemas.pcb import PCBDesign

_KICAD_SEVERITY_MAP: dict[str, Severity] = {
    "error": Severity.HIGH,
    "warning": Severity.MEDIUM,
    "ignore": Severity.INFO,
}

# KiCad violation description text commonly contains one or two "<label>
# X.XXXXmm" style numbers (e.g. "clearance 0.2000mm; actual 0.1200mm").
# We do not know KiCad's exact phrasing across all rule types up front, so
# we extract *all* "<number>mm" occurrences and treat the first as the
# required/limit value and the last as the actual/measured value when two
# or more are present. This is a heuristic, clearly best-effort -- it never
# overrides the raw message, which is always preserved separately.
_MM_VALUE_RE = re.compile(r"(-?\d+(?:\.\d+)?)\s*mm")


def _extract_numeric_values(description: str) -> tuple[Optional[float], Optional[float]]:
    matches = _MM_VALUE_RE.findall(description)
    if len(matches) >= 2:
        return float(matches[0]), float(matches[-1])
    if len(matches) == 1:
        return None, float(matches[0])
    return None, None


def _classify(raw_type: Optional[str]) -> ViolationTaxonomy:
    if not raw_type:
        return ViolationTaxonomy.UNKNOWN
    return KICAD_RULE_ID_TAXONOMY_MAP.get(raw_type, ViolationTaxonomy.OTHER)


def _severity_for(raw_severity: Optional[str], rule_type: ViolationTaxonomy) -> Severity:
    base = _KICAD_SEVERITY_MAP.get((raw_severity or "").lower(), Severity.MEDIUM)
    if rule_type == ViolationTaxonomy.SHORT_CIRCUIT:
        return Severity.CRITICAL
    return base


def _resolve_item(raw_item: dict[str, Any], graph: Optional[PCBGraph]) -> ViolationItem:
    description = raw_item.get("description")
    uuid = raw_item.get("uuid")
    resolved = graph.resolve_uuid(uuid) if (graph and uuid) else None
    if resolved:
        return ViolationItem(
            type=resolved.kind,
            reference=resolved.reference,
            pad=resolved.pad,
            net=resolved.net,
            description=description,
        )
    return ViolationItem(type="unknown", description=description)


def normalize_drc_report(
    raw_report: dict[str, Any],
    pcb_design: Optional[PCBDesign] = None,
    include_excluded: bool = False,
) -> list[DRCViolation]:
    graph = PCBGraph(pcb_design) if pcb_design is not None else None
    violations: list[DRCViolation] = []

    raw_violations = raw_report.get("violations", []) or []
    for idx, raw in enumerate(raw_violations):
        if raw.get("excluded") and not include_excluded:
            continue

        raw_type = raw.get("type")
        rule_type = _classify(raw_type)
        description = raw.get("description", "")
        severity = _severity_for(raw.get("severity"), rule_type)

        raw_items = raw.get("items", []) or []
        items = [_resolve_item(item, graph) for item in raw_items]

        location = None
        layer = None
        if raw_items:
            first_pos = raw_items[0].get("pos")
            if isinstance(first_pos, dict):
                location = ViolationLocation(x=first_pos.get("x"), y=first_pos.get("y"))

        required_value, actual_value = _extract_numeric_values(description)

        violation_id = raw.get("violation_id") or f"drc-{idx}"
        violations.append(
            DRCViolation(
                violation_id=violation_id,
                rule_type=rule_type,
                raw_rule_id=raw_type,
                severity=severity,
                message=description,
                layer=layer,
                location=location,
                items=items,
                actual_value=actual_value,
                required_value=required_value,
                unit="mm" if (required_value is not None or actual_value is not None) else None,
                raw_drc_message=description,
                raw=raw,
                source="kicad_drc",
            )
        )

    # Unconnected items are reported by KiCad separately from `violations`.
    # We still normalize each into a DRCViolation (taxonomy: UNCONNECTED) so
    # the rest of the pipeline (context retrieval, RAG, LLM diagnosis) can
    # treat them uniformly instead of as an opaque count.
    raw_unconnected = raw_report.get("unconnected_items", []) or []
    for idx, raw in enumerate(raw_unconnected):
        description = raw.get("description", "Unconnected items")
        raw_items = raw.get("items", []) or []
        items = [_resolve_item(item, graph) for item in raw_items]
        location = None
        if raw_items:
            first_pos = raw_items[0].get("pos")
            if isinstance(first_pos, dict):
                location = ViolationLocation(x=first_pos.get("x"), y=first_pos.get("y"))
        violations.append(
            DRCViolation(
                violation_id=raw.get("violation_id") or f"drc-unconnected-{idx}",
                rule_type=ViolationTaxonomy.UNCONNECTED,
                raw_rule_id="unconnected_items",
                severity=Severity.MEDIUM,
                message=description,
                location=location,
                items=items,
                raw_drc_message=description,
                raw=raw,
                source="kicad_drc",
            )
        )

    return violations
