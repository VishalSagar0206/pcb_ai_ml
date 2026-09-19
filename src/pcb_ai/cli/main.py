"""Command-line interface (Phase 29)."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import typer

from pcb_ai.agent.query_agent import InteractiveQueryAgent
from pcb_ai.agent.tools import AgentToolbox
from pcb_ai.config import get_settings
from pcb_ai.context.graph import PCBGraph
from pcb_ai.context.retriever import PCBContextRetriever
from pcb_ai.drc.runner import find_kicad_cli
from pcb_ai.observability.logging_config import configure_logging
from pcb_ai.rag.retriever import KnowledgeRetriever
from pcb_ai.service import AnalysisService

# LLM output can contain Unicode punctuation (e.g. narrow no-break spaces)
# that Windows' legacy console codepage (cp1252) cannot encode. Force
# UTF-8 stdout/stderr with a lossless-as-possible fallback so `pcb-ai`
# never crashes on otherwise-successful LLM output.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

app = typer.Typer(
    name="pcb-ai",
    help="Evidence-grounded PCB DRC intelligence: deterministic KiCad DRC + "
    "structured PCB context + engineering RAG + tool-using LLM diagnosis.",
)
configure_logging()


def _make_service() -> AnalysisService:
    return AnalysisService(settings=get_settings())


@app.command()
def analyze(
    board: Path = typer.Argument(..., help="Path to a .kicad_pcb file"),
    fixture_drc: Optional[Path] = typer.Option(
        None, "--fixture-drc", help="Use a pre-recorded DRC JSON report instead of invoking kicad-cli (offline testing)."
    ),
    out_dir: Path = typer.Option(Path("results"), "--out", help="Directory to write report/diagnoses/trace JSON."),
) -> None:
    """Run the full pipeline: parse -> DRC -> context -> RAG -> LLM diagnosis -> report."""
    service = _make_service()
    result = service.analyze(board, drc_fixture_path=fixture_drc)

    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / f"{result.analysis_id}_report.md"
    diagnoses_path = out_dir / f"{result.analysis_id}_diagnoses.json"
    traces_path = out_dir / f"{result.analysis_id}_traces.json"

    report_path.write_text(result.report_markdown, encoding="utf-8")
    diagnoses_path.write_text(
        json.dumps({k: v.model_dump(mode="json") for k, v in result.diagnoses.items()}, indent=2),
        encoding="utf-8",
    )
    traces_path.write_text(
        json.dumps({k: v.model_dump(mode="json") for k, v in result.traces.items()}, indent=2),
        encoding="utf-8",
    )

    typer.echo(f"analysis_id: {result.analysis_id}")
    typer.echo(f"violations: {len(result.drc_result.violations)}")
    typer.echo(f"kicad_executed: {result.drc_result.executed} (fixture_used: {result.drc_result.fixture_used})")
    typer.echo(f"report: {report_path}")
    typer.echo(f"diagnoses: {diagnoses_path}")
    typer.echo(f"traces: {traces_path}")


@app.command()
def drc(
    board: Path = typer.Argument(..., help="Path to a .kicad_pcb file"),
    fixture_drc: Optional[Path] = typer.Option(None, "--fixture-drc", help="Use a pre-recorded DRC JSON report."),
) -> None:
    """Run (or load) deterministic DRC only and print normalized violations."""
    from pcb_ai.context.graph import PCBGraph
    from pcb_ai.drc.runner import load_fixture_drc_report, run_kicad_drc
    from pcb_ai.parser.kicad_pcb_parser import parse_kicad_pcb_file

    settings = get_settings()
    pcb = parse_kicad_pcb_file(board)
    graph = PCBGraph(pcb)  # noqa: F841 - constructed for parity/future use, uuids resolved inside runner
    if fixture_drc:
        result = load_fixture_drc_report(fixture_drc, pcb)
    else:
        result = run_kicad_drc(board, pcb, settings=settings)

    if result.error:
        typer.echo(f"DRC error: {result.error}")
    typer.echo(f"executed={result.executed} fixture_used={result.fixture_used} violations={len(result.violations)}")
    for v in result.violations:
        typer.echo(f"- [{v.severity.value}] {v.violation_id} ({v.rule_type.value}): {v.message}")


@app.command()
def explain(
    board: Path = typer.Argument(..., help="Path to a .kicad_pcb file"),
    violation: str = typer.Option(..., "--violation", help="violation_id to explain"),
    fixture_drc: Optional[Path] = typer.Option(None, "--fixture-drc", help="Use a pre-recorded DRC JSON report."),
) -> None:
    """Run the full pipeline but only print the diagnosis for one violation_id."""
    service = _make_service()
    result = service.analyze(board, drc_fixture_path=fixture_drc)
    diagnosis = result.diagnoses.get(violation)
    if diagnosis is None:
        typer.echo(f"No such violation_id: {violation}. Known ids: {list(result.diagnoses.keys())}")
        raise typer.Exit(code=1)
    typer.echo(json.dumps(diagnosis.model_dump(mode="json"), indent=2))


@app.command()
def report(
    board: Path = typer.Argument(..., help="Path to a .kicad_pcb file"),
    fixture_drc: Optional[Path] = typer.Option(None, "--fixture-drc", help="Use a pre-recorded DRC JSON report."),
    out: Optional[Path] = typer.Option(None, "--out", help="Write report to this file instead of stdout."),
) -> None:
    """Run the full pipeline and print (or save) the human-readable report."""
    service = _make_service()
    result = service.analyze(board, drc_fixture_path=fixture_drc)
    if out:
        out.write_text(result.report_markdown, encoding="utf-8")
        typer.echo(f"Report written to {out}")
    else:
        typer.echo(result.report_markdown)


@app.command("index-knowledge")
def index_knowledge(
    directory: Path = typer.Argument(..., help="Directory of .txt/.md/.pdf engineering documents to ingest."),
    out: Path = typer.Option(Path("data/knowledge_index.json"), "--out", help="Where to save the persisted chunk index."),
) -> None:
    """Ingest and chunk a directory of engineering documents/datasheets."""
    settings = get_settings()
    kr = KnowledgeRetriever(settings)
    chunks = kr.index_directory(directory)
    out.parent.mkdir(parents=True, exist_ok=True)
    kr.save(out)
    typer.echo(f"Indexed {len(chunks)} chunks from {directory} -> {out}")


@app.command()
def query(
    board: Path = typer.Argument(..., help="Path to a .kicad_pcb file"),
    question: str = typer.Option(..., "--question", help="Free-form question, e.g. 'Why is U3 pad 4 failing DRC?'"),
    fixture_drc: Optional[Path] = typer.Option(None, "--fixture-drc", help="Use a pre-recorded DRC JSON report."),
) -> None:
    """Ask a free-form question; the LLM agent uses tools to gather evidence before answering."""
    service = _make_service()
    pcb, drc_result = service.parse_and_drc(board, drc_fixture_path=fixture_drc)
    graph = PCBGraph(pcb)
    settings = get_settings()
    context_retriever = PCBContextRetriever(graph, settings)
    violations_by_id = {v.violation_id: v for v in drc_result.violations}
    toolbox = AgentToolbox(graph, context_retriever, service.knowledge_retriever, violations_by_id)
    agent = InteractiveQueryAgent(service.llm_provider, toolbox)
    answer = agent.answer(question)
    typer.echo(answer.answer)
    typer.echo(f"\n[tool calls used: {answer.tool_calls}]")


@app.command()
def evaluate(
    evaluation_dir: Path = typer.Argument(..., help="Directory containing an evaluation dataset (see EVALUATION.md)."),
    out_dir: Path = typer.Option(Path("results"), "--out", help="Directory to write experiment result JSON/CSV."),
) -> None:
    """Run the baseline/ablation evaluation experiments over a dataset."""
    from pcb_ai.eval.runner import run_evaluation

    summary = run_evaluation(evaluation_dir, out_dir, settings=get_settings())
    typer.echo(json.dumps(summary, indent=2))


@app.command()
def doctor() -> None:
    """Report environment status: kicad-cli, LLM provider, knowledge directories."""
    settings = get_settings()
    typer.echo(f"kicad-cli: {find_kicad_cli(settings) or 'NOT FOUND'}")
    typer.echo(f"LLM provider: {settings.caf_model_provider} @ {settings.caf_model_base_url or '(unset)'}")
    typer.echo(f"LLM analysis model: {settings.caf_model_analysis}")
    typer.echo(f"knowledge_dir: {settings.knowledge_path} (exists={settings.knowledge_path.exists()})")
    typer.echo(f"datasheet_dir: {settings.datasheet_path} (exists={settings.datasheet_path.exists()})")


if __name__ == "__main__":
    app()
