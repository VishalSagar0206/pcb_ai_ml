"""Human-readable engineering report generation (Phase 14)."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Optional

from pcb_ai.schemas.diagnosis import ViolationDiagnosis
from pcb_ai.schemas.drc import DRCRunResult, Severity
from pcb_ai.schemas.pcb import PCBDesign

_SEVERITY_ORDER = [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO]


def generate_report(
    pcb: PCBDesign,
    drc_result: DRCRunResult,
    diagnoses: dict[str, ViolationDiagnosis],
    analysis_id: Optional[str] = None,
) -> str:
    lines: list[str] = []
    lines.append("# PCB DRC INTELLIGENCE REPORT")
    lines.append("")
    lines.append(f"Generated: {datetime.now(timezone.utc).isoformat()}")
    if analysis_id:
        lines.append(f"Analysis ID: `{analysis_id}`")
    lines.append("")

    lines.extend(_board_summary_section(pcb, drc_result))
    lines.extend(_drc_summary_section(drc_result, diagnoses))
    lines.extend(_violation_by_violation_section(drc_result, diagnoses))
    lines.extend(_recurring_root_causes_section(drc_result, diagnoses))
    lines.extend(_design_level_observations_section(pcb, drc_result))
    lines.extend(_uncertain_findings_section(drc_result, diagnoses))
    lines.extend(_recommended_actions_section(diagnoses))

    return "\n".join(lines)


def _board_summary_section(pcb: PCBDesign, drc_result: DRCRunResult) -> list[str]:
    lines = ["## 1. Board Summary", ""]
    lines.append(f"- Board: **{pcb.board.title or pcb.board.board_id}** (rev {pcb.board.revision or 'n/a'})")
    lines.append(f"- Layers: {len(pcb.layers)} ({', '.join(pcb.board.layers[:8])}{'...' if len(pcb.board.layers) > 8 else ''})")
    if pcb.board.width_mm and pcb.board.height_mm:
        lines.append(f"- Board outline (bounding box): {pcb.board.width_mm:.2f} x {pcb.board.height_mm:.2f} mm")
    lines.append(f"- Components: {len(pcb.components)}  |  Nets: {len(pcb.nets)}  |  Tracks: {len(pcb.tracks)}  |  Vias: {len(pcb.vias)}  |  Zones: {len(pcb.zones)}")
    lines.append(
        f"- DRC source: {'live kicad-cli execution' if drc_result.executed else ('fixture report (NOT a live run)' if drc_result.fixture_used else 'unavailable')}"
    )
    if drc_result.error:
        lines.append(f"- DRC error: {drc_result.error}")
    lines.append("")
    return lines


def _drc_summary_section(drc_result: DRCRunResult, diagnoses: dict[str, ViolationDiagnosis]) -> list[str]:
    lines = ["## 2. DRC Summary", ""]
    counts = Counter(v.severity for v in drc_result.violations)
    lines.append(f"- Total violations: **{len(drc_result.violations)}**")
    for sev in _SEVERITY_ORDER:
        lines.append(f"  - {sev.value}: {counts.get(sev, 0)}")
    lines.append(f"- Unconnected item groups: {drc_result.unconnected_count}")
    lines.append(f"- Diagnoses generated: {len(diagnoses)}")
    lines.append("")
    return lines


def _violation_by_violation_section(drc_result: DRCRunResult, diagnoses: dict[str, ViolationDiagnosis]) -> list[str]:
    lines = ["## 3. Violation-by-Violation Analysis", ""]
    for violation in drc_result.violations:
        diagnosis = diagnoses.get(violation.violation_id)
        lines.append(f"### Violation `{violation.violation_id}` -- {violation.rule_type.value}")
        lines.append(f"- DRC message: {violation.message}")
        if violation.location:
            lines.append(f"- Location: ({violation.location.x}, {violation.location.y})")
        lines.append(
            f"- Affected objects: "
            + ", ".join(
                f"{item.type}:{item.reference or '?'}{(':' + item.pad) if item.pad else ''}"
                for item in violation.items
            )
        )
        if violation.required_value is not None or violation.actual_value is not None:
            lines.append(
                f"- Required: {violation.required_value} {violation.unit or ''} | Actual: {violation.actual_value} {violation.unit or ''}"
            )

        if diagnosis is None:
            lines.append("- **No diagnosis available for this violation.**")
        else:
            lines.append("")
            lines.append(f"**What happened?** {diagnosis.summary}")
            lines.append("")
            lines.append(f"**Why did it happen?** {diagnosis.root_cause.explanation} (confidence: {diagnosis.root_cause.confidence:.2f})")
            lines.append("")
            lines.append(f"**Engineering impact:** {diagnosis.engineering_impact.description}")
            if diagnosis.engineering_impact.potential_effects:
                for effect in diagnosis.engineering_impact.potential_effects:
                    lines.append(f"  - {effect}")
            lines.append("")
            lines.append(f"**Recommended remediation:** {diagnosis.recommended_fix.description}")
            for action in diagnosis.recommended_fix.actions:
                lines.append(f"  - {action}")
            lines.append("")
            lines.append(
                f"**Evidence:** {len(diagnosis.evidence)} cited item(s) "
                f"({', '.join(sorted({e.source_type for e in diagnosis.evidence}))})"
            )
            lines.append(
                f"**Severity:** deterministic={diagnosis.deterministic_severity.value if diagnosis.deterministic_severity else 'n/a'}, "
                f"llm_assessed={diagnosis.llm_assessed_severity.value if diagnosis.llm_assessed_severity else 'n/a'} "
                f"(policy v{diagnosis.severity_policy_version})"
            )
            lines.append(f"**Confidence:** {diagnosis.classification.confidence:.2f}")
            lines.append(f"**Human review required:** {'YES' if diagnosis.requires_human_review else 'no'}")
            if diagnosis.insufficient_evidence:
                lines.append("**NOTE: insufficient evidence -- this diagnosis is incomplete.**")
            if diagnosis.validation_passed is False:
                lines.append(f"**NOTE: evidence validation FAILED:** {'; '.join(diagnosis.validation_errors)}")
        lines.append("")
    return lines


def _recurring_root_causes_section(drc_result: DRCRunResult, diagnoses: dict[str, ViolationDiagnosis]) -> list[str]:
    lines = ["## 4. Recurring Root Causes", ""]
    total = len(drc_result.violations)
    if total == 0:
        lines.append("No violations to analyze.")
        lines.append("")
        return lines

    by_type = Counter(v.rule_type.value for v in drc_result.violations)
    lines.append("By violation type:")
    for rule_type, count in by_type.most_common():
        pct = 100.0 * count / total
        lines.append(f"- {rule_type}: {count} ({pct:.0f}%)")

    component_hits: Counter[str] = Counter()
    for violation in drc_result.violations:
        for item in violation.items:
            if item.reference:
                component_hits[item.reference] += 1
    if component_hits:
        lines.append("")
        lines.append("Concentration by component:")
        for reference, count in component_hits.most_common(5):
            pct = 100.0 * count / total
            lines.append(f"- {reference}: involved in {count} violation(s) ({pct:.0f}% of total)")
    lines.append("")
    return lines


def _design_level_observations_section(pcb: PCBDesign, drc_result: DRCRunResult) -> list[str]:
    lines = ["## 5. Design-Level Observations", ""]
    net_hits: Counter[str] = Counter()
    for violation in drc_result.violations:
        for item in violation.items:
            if item.net:
                net_hits[item.net] += 1
    if net_hits:
        top_net, count = net_hits.most_common(1)[0]
        lines.append(f"- Net `{top_net}` is implicated in {count} violation(s) -- consider reviewing its routing as a group.")
    unrouted_nets = [n.net_name for n in pcb.nets if n.net_name and not n.connected_pads]
    if unrouted_nets:
        lines.append(f"- {len(unrouted_nets)} net(s) have no connected pads recorded: {', '.join(unrouted_nets[:10])}")
    if not net_hits and not unrouted_nets:
        lines.append("- No cross-cutting design-level patterns detected beyond the per-violation findings above.")
    lines.append("")
    return lines


def _uncertain_findings_section(drc_result: DRCRunResult, diagnoses: dict[str, ViolationDiagnosis]) -> list[str]:
    lines = ["## 6. Uncertain Findings", ""]
    uncertain = [
        d for d in diagnoses.values() if d.insufficient_evidence or d.validation_passed is False or d.uncertainty
    ]
    if not uncertain:
        lines.append("No uncertain findings -- all generated diagnoses passed evidence validation.")
    else:
        for d in uncertain:
            reasons = []
            if d.insufficient_evidence:
                reasons.append("insufficient_evidence")
            if d.validation_passed is False:
                reasons.append("evidence_validation_failed")
            if d.uncertainty:
                reasons.extend(d.uncertainty[:3])
            lines.append(f"- Violation `{d.violation_id}`: {'; '.join(reasons)}")
    lines.append("")
    return lines


def _recommended_actions_section(diagnoses: dict[str, ViolationDiagnosis]) -> list[str]:
    lines = ["## 7. Recommended Next Actions", ""]
    seen: set[str] = set()
    actions: list[str] = []
    for d in diagnoses.values():
        for action in d.recommended_fix.actions:
            key = action.strip().lower()
            if key and key not in seen:
                seen.add(key)
                actions.append(action)
    if not actions:
        lines.append("No specific remediation actions were generated.")
    else:
        for action in actions[:20]:
            lines.append(f"- {action}")
    human_review_count = sum(1 for d in diagnoses.values() if d.requires_human_review)
    lines.append("")
    lines.append(f"**{human_review_count}/{len(diagnoses)} diagnoses are flagged as requiring human engineering review before any fix is applied.**")
    lines.append("")
    return lines
