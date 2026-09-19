"""Read-only reader for the reference PCB-QA benchmark repository
(`pcb_qa-4FEE`), used only to surface "research lineage" context in the
frontend (project names, circuit sizes, sample benchmark questions). This
module never feeds pcb_qa-4FEE data into the DRC diagnosis pipeline itself
-- that repository contains schematic/netlist-level hierarchical circuit
JSON (no physical layout / component positions), so it is not compatible
with the PCB-board renderer or the DRC pipeline, which both require an
actual `.kicad_pcb`.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional


def _safe_load_json(path: Path) -> Optional[Any]:
    try:
        # pcb_qa-4FEE JSON files were authored on macOS and contain
        # characters (e.g. "±", "°") outside the cp1252 codepage Windows
        # defaults to; read as UTF-8 with lossless-as-possible fallback.
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (json.JSONDecodeError, OSError):
        return None


def _find_circuit_json(project_dir: Path) -> Optional[Path]:
    """Find the hierarchical circuit JSON file in a project's output
    directory. File names vary per project (e.g. `cm4-robot.json`,
    `Hades.json`, `PCB.json`), so we identify it by shape (has both
    `components` and `nets` top-level keys) rather than by naming
    convention, skipping the SPICE-circuit and questions JSON files."""
    for candidate in sorted(project_dir.glob("*.json")):
        stem_lower = candidate.stem.lower()
        if "spice_circuit" in stem_lower or "questions" in stem_lower:
            continue
        data = _safe_load_json(candidate)
        if isinstance(data, dict) and "components" in data and "nets" in data:
            return candidate
    return None


def _find_questions_json(project_dir: Path) -> Optional[Path]:
    candidates = [
        p
        for p in project_dir.glob("*questions*.json")
        if "copy" not in p.stem.lower()
    ]
    return candidates[0] if candidates else None


def get_pcb_qa_reference(pcb_qa_dir: Path, sample_questions_per_project: int = 3) -> dict:
    """Summarize the pcb_qa-4FEE benchmark repository for display in the
    frontend's "Research Lineage" section. Returns an empty `projects` list
    (with `available: False`) if the reference repository isn't present at
    the configured path, rather than raising -- this is optional context,
    not a pipeline dependency."""
    outputs_dir = pcb_qa_dir / "outputs"
    if not outputs_dir.exists():
        return {"available": False, "projects": []}

    projects: list[dict] = []
    for project_dir in sorted(p for p in outputs_dir.iterdir() if p.is_dir()):
        circuit_path = _find_circuit_json(project_dir)
        questions_path = _find_questions_json(project_dir)

        circuit_data = _safe_load_json(circuit_path) if circuit_path else None
        questions_data = _safe_load_json(questions_path) if questions_path else None

        entry: dict[str, Any] = {"project": project_dir.name}
        if circuit_data:
            entry["circuit_name"] = circuit_data.get("name")
            entry["component_count"] = len(circuit_data.get("components", {}) or {})
            entry["net_count"] = len(circuit_data.get("nets", {}) or {})
            entry["subcircuit_count"] = len(circuit_data.get("subcircuits", []) or [])
        if isinstance(questions_data, list):
            entry["question_count"] = len(questions_data)
            entry["sample_questions"] = questions_data[:sample_questions_per_project]

        if len(entry) > 1:  # more than just the "project" key
            projects.append(entry)

    return {"available": True, "projects": projects}
