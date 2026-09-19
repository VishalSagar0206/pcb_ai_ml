"""Evaluation harness runner (Phase 17-20): loads a dataset of expert-
labeled DRC violations, runs each configured ablation condition, scores
the results against expert labels, and writes machine-readable results.

Dataset layout expected under `evaluation_dir`:

    <case_name>/
        board.kicad_pcb
        drc.json          (a KiCad-DRC-schema-shaped report; see
                            tests/fixtures/sample_drc_report.json)
        labels.json        (list of EvaluationRecord dicts)
"""
from __future__ import annotations

import csv
import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Union

from pcb_ai.config import Settings, get_settings
from pcb_ai.context.graph import PCBGraph
from pcb_ai.drc.runner import load_fixture_drc_report
from pcb_ai.eval.experiments import EXPERIMENT_CONDITIONS, run_condition
from pcb_ai.eval.metrics import RecordMetrics, aggregate, score_record
from pcb_ai.llm.factory import get_llm_provider
from pcb_ai.parser.kicad_pcb_parser import parse_kicad_pcb_file
from pcb_ai.rag.retriever import KnowledgeRetriever
from pcb_ai.schemas.evaluation import EvaluationRecord

_CONDITION_ARTIFACT_NAMES = {
    "drc_only": "baseline_drc_only.json",
    "raw_kicad": "baseline_raw_kicad.json",
    "pcb_json": "baseline_pcb_json.json",
    "pcb_json_rag": "baseline_rag.json",
    "full_pcb_json": "ablation_full_pcb_json.json",
}


def _discover_cases(evaluation_dir: Path) -> list[Path]:
    cases = []
    for path in sorted(evaluation_dir.iterdir()):
        if path.is_dir() and (path / "board.kicad_pcb").exists() and (path / "labels.json").exists():
            cases.append(path)
    return cases


def run_evaluation(
    evaluation_dir: Union[str, Path],
    out_dir: Union[str, Path],
    settings: Settings | None = None,
    knowledge_dir: Union[str, Path, None] = None,
) -> dict:
    settings = settings or get_settings()
    evaluation_dir = Path(evaluation_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    cases = _discover_cases(evaluation_dir)
    if not cases:
        return {
            "status": "NOT_RUN",
            "reason": f"No evaluation cases found under {evaluation_dir} "
            "(expected <case>/board.kicad_pcb + <case>/labels.json).",
        }

    llm_provider = get_llm_provider(settings)
    knowledge_retriever = KnowledgeRetriever(settings)
    if knowledge_dir:
        knowledge_retriever.index_directory(knowledge_dir)
    else:
        knowledge_retriever.index_directory(settings.knowledge_path)
        knowledge_retriever.index_directory(settings.datasheet_path)

    per_condition_records: dict[str, list[RecordMetrics]] = {c: [] for c in EXPERIMENT_CONDITIONS}
    csv_rows: list[dict] = []
    raw_results: dict[str, list[dict]] = {c: [] for c in EXPERIMENT_CONDITIONS}

    for case_dir in cases:
        board_path = case_dir / "board.kicad_pcb"
        drc_path = case_dir / "drc.json"
        labels_path = case_dir / "labels.json"

        pcb = parse_kicad_pcb_file(board_path)
        graph = PCBGraph(pcb)
        drc_result = load_fixture_drc_report(drc_path, pcb)
        raw_pcb_text = board_path.read_text(encoding="utf-8", errors="replace")

        violations_by_id = {v.violation_id: v for v in drc_result.violations}
        labels = [EvaluationRecord.model_validate(item) for item in json.loads(labels_path.read_text(encoding="utf-8"))]

        for record in labels:
            violation = violations_by_id.get(record.violation_id)
            if violation is None:
                continue

            for condition in EXPERIMENT_CONDITIONS:
                start = time.perf_counter()
                diagnosis, metadata = run_condition(
                    condition,
                    violation,
                    pcb,
                    graph,
                    llm_provider,
                    knowledge_retriever=knowledge_retriever,
                    settings=settings,
                    raw_pcb_text=raw_pcb_text,
                )
                latency_ms = (time.perf_counter() - start) * 1000

                record_metrics = score_record(diagnosis, record, condition, metadata, latency_ms=latency_ms)
                per_condition_records[condition].append(record_metrics)

                raw_results[condition].append(
                    {
                        "case": case_dir.name,
                        "violation_id": record.violation_id,
                        "diagnosis": diagnosis.model_dump(mode="json"),
                        "metadata": metadata,
                        "latency_ms": latency_ms,
                    }
                )

                csv_rows.append(
                    {
                        "model": llm_provider.model_name,
                        "method": condition,
                        "board": case_dir.name,
                        "violation_type": record.violation_type,
                        "accuracy": int(record_metrics.classification_correct),
                        "precision": int(record_metrics.classification_correct),
                        "recall": int(record_metrics.classification_correct),
                        "f1": int(record_metrics.classification_correct),
                        "grounding_score": int(record_metrics.evidence_grounded),
                        "hallucination_rate": int(record_metrics.hallucination_flag),
                        "latency_ms": round(latency_ms, 1),
                        "tokens": record_metrics.total_tokens,
                        "cost": "NOT_COMPUTABLE",
                    }
                )

    for condition, results in raw_results.items():
        artifact_name = _CONDITION_ARTIFACT_NAMES.get(condition, f"{condition}.json")
        (out_dir / artifact_name).write_text(json.dumps(results, indent=2), encoding="utf-8")

    aggregates = {condition: aggregate(records, condition) for condition, records in per_condition_records.items()}
    (out_dir / "ablation_results.json").write_text(
        json.dumps({c: asdict(a) for c, a in aggregates.items()}, indent=2),
        encoding="utf-8",
    )

    if csv_rows:
        with (out_dir / "results.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(csv_rows[0].keys()))
            writer.writeheader()
            writer.writerows(csv_rows)

    return {
        "status": "RUN",
        "cases_evaluated": [c.name for c in cases],
        "conditions": EXPERIMENT_CONDITIONS,
        "total_records_per_condition": {c: len(r) for c, r in per_condition_records.items()},
        "aggregate_summary": {c: asdict(a) for c, a in aggregates.items()},
        "note": (
            "This is a demonstration run over a small synthetic dataset "
            f"({len(cases)} case(s)); it is NOT a validated research-scale "
            "evaluation. See EVALUATION.md for scope and limitations."
        ),
    }
