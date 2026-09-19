"""FastAPI application exposing the PCB DRC intelligence pipeline (Phase 15)."""
from __future__ import annotations

import asyncio
import json
import shutil
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from pcb_ai.agent.query_agent import InteractiveQueryAgent
from pcb_ai.agent.tools import AgentToolbox
from pcb_ai.config import get_settings
from pcb_ai.context.graph import PCBGraph
from pcb_ai.context.retriever import PCBContextRetriever
from pcb_ai.observability.logging_config import configure_logging
from pcb_ai.research.knowledge_showcase import KnowledgeBaseShowcase
from pcb_ai.research.pcb_qa_reference import get_pcb_qa_reference
from pcb_ai.service import AnalysisService

app = FastAPI(
    title="PCB DRC Intelligence API",
    description=(
        "Evidence-grounded PCB DRC interpretation: deterministic KiCad DRC "
        "+ structured PCB representation + engineering RAG + tool-using LLM "
        "diagnosis. The LLM never replaces the deterministic DRC engine."
    ),
    version="0.1.0",
)

configure_logging()
_settings = get_settings()
_service = AnalysisService(settings=_settings)
_knowledge_showcase = KnowledgeBaseShowcase(settings=_settings)
_knowledge_showcase_lock = asyncio.Lock()

app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registry of bundled sample boards for the frontend's "sample board switcher".
# Each entry pairs a `.kicad_pcb` file with its recorded DRC fixture so the
# demo/showcase experience works without a live KiCad install. "small" is the
# original demo board (kept at its own path/id for backward compatibility
# with the existing `/pcb/demo` endpoint); "medium" and "large" were added to
# stress-test the frontend (canvas zoom/pan, violation-list scrolling, and a
# wider spread of DRC taxonomy/severity badges) at bigger board scales.
_SAMPLE_BOARDS: dict[str, dict] = {
    "small": {
        "name": "Small Reference Board",
        "description": (
            "Compact hand-authored board covering the core DRC taxonomy "
            "(clearance, silkscreen, footprint, unconnected nets)."
        ),
        "board_file": "sample_board.kicad_pcb",
        "drc_file": "sample_drc_report.json",
        "base_dir": "demo",
    },
    "medium": {
        "name": "Medium Complexity Board",
        "description": (
            "13-component board (MCU, regulator, connector, crystal) with 8 "
            "violations spanning clearance, annular ring, courtyard overlap, "
            "differential pair, zone clearance, a CRITICAL short circuit, "
            "and minimum drill size."
        ),
        "board_file": "medium_board.kicad_pcb",
        "drc_file": "medium_drc_report.json",
        "base_dir": "samples",
    },
    "large": {
        "name": "Large Multi-IC Board",
        "description": (
            "26-component board (4 ICs + 20 passives) for stress-testing "
            "canvas zoom/pan and violation-list scrolling at scale."
        ),
        "board_file": "large_board.kicad_pcb",
        "drc_file": "large_drc_report.json",
        "base_dir": "samples",
    },
}
# Per-sample cache of the completed analysis id, and a per-sample lock so
# concurrent requests for the *same* sample can't both see an empty cache and
# each kick off a redundant, expensive multi-violation LLM diagnosis run.
_sample_analysis_ids: dict[str, str] = {}
_sample_analysis_locks: dict[str, asyncio.Lock] = {sample_id: asyncio.Lock() for sample_id in _SAMPLE_BOARDS}


def _sample_base_dir(sample_id: str) -> Path:
    return _settings.demo_path if _SAMPLE_BOARDS[sample_id]["base_dir"] == "demo" else _settings.samples_path


async def _analyze_sample(sample_id: str):
    """Run (once, then cache) the full pipeline against a bundled sample
    board + recorded DRC fixture. Shared by `/pcb/demo` (back-compat alias
    for the "small" sample) and `/pcb/samples/{sample_id}/analyze`."""
    spec = _SAMPLE_BOARDS.get(sample_id)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"Unknown sample id '{sample_id}'")
    lock = _sample_analysis_locks[sample_id]
    async with lock:
        cached_id = _sample_analysis_ids.get(sample_id)
        if cached_id is not None and _service.get(cached_id) is not None:
            return _service.get(cached_id)
        base_dir = _sample_base_dir(sample_id)
        board_path = base_dir / spec["board_file"]
        drc_path = base_dir / spec["drc_file"]
        if not board_path.exists() or not drc_path.exists():
            raise HTTPException(status_code=500, detail=f"Sample data not found for '{sample_id}' under {base_dir}")
        try:
            result = await run_in_threadpool(
                _service.analyze, board_path, drc_fixture_path=drc_path, analysis_id=f"sample-{sample_id}"
            )
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=500, detail=f"Failed to analyze sample '{sample_id}': {exc}") from exc
        _sample_analysis_ids[sample_id] = result.analysis_id
        return result


class AnalyzeResponse(BaseModel):
    analysis_id: str
    violation_count: int
    kicad_executed: bool
    kicad_available: bool


class QueryRequest(BaseModel):
    analysis_id: str
    question: str


class QueryResponse(BaseModel):
    answer: str
    tool_calls: list[str]
    iterations: int


@app.post("/pcb/analyze", response_model=AnalyzeResponse)
async def analyze_pcb(file: UploadFile) -> AnalyzeResponse:
    if not file.filename or not file.filename.endswith(".kicad_pcb"):
        raise HTTPException(status_code=400, detail="Upload must be a .kicad_pcb file")

    upload_dir = Path(_settings.datasheet_path).parent / "pcb_uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest_path = upload_dir / f"{uuid.uuid4().hex}_{file.filename}"
    with dest_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        # `AnalysisService.analyze` makes blocking (synchronous) network
        # calls to the LLM provider; running it directly in this `async
        # def` handler would block FastAPI's single event loop for the
        # entire multi-violation diagnosis duration, stalling every other
        # concurrent request (including unrelated ones like /health).
        # `run_in_threadpool` offloads it to a worker thread instead.
        result = await run_in_threadpool(_service.analyze, dest_path)
    except Exception as exc:  # noqa: BLE001 - surface parse/DRC failures to the API caller
        raise HTTPException(status_code=422, detail=f"Failed to analyze PCB: {exc}") from exc

    return AnalyzeResponse(
        analysis_id=result.analysis_id,
        violation_count=len(result.drc_result.violations),
        kicad_executed=result.drc_result.executed,
        kicad_available=_service.kicad_available(),
    )


@app.get("/pcb/analyze/{analysis_id}")
async def get_analysis(analysis_id: str) -> dict:
    result = _require_result(analysis_id)
    return {
        "analysis_id": result.analysis_id,
        "board": result.pcb.board.model_dump(mode="json"),
        "violation_count": len(result.drc_result.violations),
        "kicad_executed": result.drc_result.executed,
        "fixture_used": result.drc_result.fixture_used,
        "diagnosis_count": len(result.diagnoses),
    }


@app.get("/pcb/board/{analysis_id}")
async def get_board(analysis_id: str) -> dict:
    """Full structured PCB JSON (board/layers/components/pads/nets/tracks/
    vias/zones/rules) for a prior analysis -- everything the frontend's
    interactive board canvas needs to render the physical layout."""
    result = _require_result(analysis_id)
    return result.pcb.model_dump(mode="json")


@app.get("/pcb/violations/{analysis_id}")
async def list_violations(analysis_id: str) -> list[dict]:
    result = _require_result(analysis_id)
    return [v.model_dump(mode="json") for v in result.drc_result.violations]


@app.get("/pcb/diagnoses/{analysis_id}")
async def list_diagnoses_summary(analysis_id: str) -> list[dict]:
    """Lightweight per-violation diagnosis summary (classification,
    confidence, deterministic/LLM-assessed severity, human-review flag) --
    enough for the frontend to compute dashboard-level aggregate stats
    (average confidence, human-review count, severity breakdown) without
    fetching every violation's full evidence/trace payload individually."""
    result = _require_result(analysis_id)
    return [
        {
            "violation_id": violation_id,
            "classification": diagnosis.classification.model_dump(mode="json"),
            "deterministic_severity": diagnosis.deterministic_severity,
            "llm_assessed_severity": diagnosis.llm_assessed_severity,
            "requires_human_review": diagnosis.requires_human_review,
            "insufficient_evidence": diagnosis.insufficient_evidence,
            "validation_passed": diagnosis.validation_passed,
        }
        for violation_id, diagnosis in result.diagnoses.items()
    ]


@app.get("/pcb/violations/{analysis_id}/{violation_id}")
async def get_violation(analysis_id: str, violation_id: str) -> dict:
    result = _require_result(analysis_id)
    violation = next((v for v in result.drc_result.violations if v.violation_id == violation_id), None)
    if violation is None:
        raise HTTPException(status_code=404, detail=f"Unknown violation_id: {violation_id}")
    diagnosis = result.diagnoses.get(violation_id)
    trace = result.traces.get(violation_id)
    return {
        "violation": violation.model_dump(mode="json"),
        "diagnosis": diagnosis.model_dump(mode="json") if diagnosis else None,
        "trace": trace.model_dump(mode="json") if trace else None,
    }


@app.get("/pcb/report/{analysis_id}", response_class=PlainTextResponse)
async def get_report(analysis_id: str) -> str:
    result = _require_result(analysis_id)
    return result.report_markdown


@app.post("/pcb/query", response_model=QueryResponse)
async def query_pcb(request: QueryRequest) -> QueryResponse:
    result = _require_result(request.analysis_id)
    graph = PCBGraph(result.pcb)
    context_retriever = PCBContextRetriever(graph, _settings)
    violations_by_id = {v.violation_id: v for v in result.drc_result.violations}
    toolbox = AgentToolbox(graph, context_retriever, _service.knowledge_retriever, violations_by_id)
    agent = InteractiveQueryAgent(_service.llm_provider, toolbox)
    # See analyze_pcb() above: offload the blocking tool-calling LLM loop
    # to a worker thread so it doesn't stall the event loop.
    answer = await run_in_threadpool(agent.answer, request.question)
    return QueryResponse(answer=answer.answer, tool_calls=answer.tool_calls, iterations=answer.iterations)


@app.post("/pcb/demo", response_model=AnalyzeResponse)
async def analyze_demo_board() -> AnalyzeResponse:
    """Run (once, then cache) the full pipeline against the bundled demo
    board + recorded DRC fixture, so the frontend has an instant, populated
    "showcase" view without requiring a live KiCad install or waiting on a
    fresh set of LLM calls on every page load. Live analysis of a real
    user-uploaded board is still available via `POST /pcb/analyze`. Kept as
    a dedicated route (an alias for `POST /pcb/samples/small/analyze`) for
    backward compatibility with the original frontend integration."""
    result = await _analyze_sample("small")
    return AnalyzeResponse(
        analysis_id=result.analysis_id,
        violation_count=len(result.drc_result.violations),
        kicad_executed=result.drc_result.executed,
        kicad_available=_service.kicad_available(),
    )


@app.get("/pcb/samples")
async def list_samples() -> dict:
    """List the bundled sample boards (small/medium/large) available for the
    frontend's sample-board switcher, along with whether each has already
    been analyzed and cached in this server process."""
    samples = []
    for sample_id, spec in _SAMPLE_BOARDS.items():
        cached_id = _sample_analysis_ids.get(sample_id)
        samples.append(
            {
                "id": sample_id,
                "name": spec["name"],
                "description": spec["description"],
                "cached": cached_id is not None and _service.get(cached_id) is not None,
            }
        )
    return {"samples": samples}


@app.post("/pcb/samples/{sample_id}/analyze", response_model=AnalyzeResponse)
async def analyze_sample_board(sample_id: str) -> AnalyzeResponse:
    """Run (once, then cache) the full pipeline against a named bundled
    sample board. See `_SAMPLE_BOARDS` for the available ids."""
    result = await _analyze_sample(sample_id)
    return AnalyzeResponse(
        analysis_id=result.analysis_id,
        violation_count=len(result.drc_result.violations),
        kicad_executed=result.drc_result.executed,
        kicad_available=_service.kicad_available(),
    )


@app.get("/eval/summary")
async def get_eval_summary() -> dict:
    """Aggregate ablation/baseline metrics from the most recent
    `pcb-ai evaluate` run (Phase 17-20), for the evaluation dashboard.
    Returns `available: False` (not an error) if no evaluation has been
    run yet in this environment -- the frontend should show a helpful
    empty state rather than a broken chart."""
    summary_path = _settings.results_path / "ablation_results.json"
    if not summary_path.exists():
        return {"available": False, "conditions": {}}
    try:
        data = json.loads(summary_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read evaluation summary: {exc}") from exc
    return {"available": True, "conditions": data}


@app.get("/research/pcb-qa-reference")
async def get_research_reference() -> dict:
    """Read-only summary of the reference PCB-QA benchmark repository
    (component/net counts, sample questions per project) for the frontend's
    "Research Lineage" section. See `pcb_ai.research.pcb_qa_reference` for
    why this data is display-only and never feeds the DRC pipeline."""
    return get_pcb_qa_reference(_settings.pcb_qa_reference_path)


class KnowledgeSearchRequest(BaseModel):
    query: str
    top_k: int = 8


@app.get("/knowledge/showcase/summary")
async def get_knowledge_showcase_summary() -> dict:
    """List of real component datasheets (from pcb_qa-4FEE) indexed into the
    standalone Knowledge Base showcase, demonstrating the hybrid-retrieval
    RAG layer (Phase 6/7) against genuine manufacturer PDFs. Indexed lazily
    on first request (offloaded to a worker thread) and cached thereafter.
    Deliberately isolated from the live diagnosis pipeline's own knowledge
    retriever -- see `pcb_ai.research.knowledge_showcase` module docstring."""
    async with _knowledge_showcase_lock:
        documents = await run_in_threadpool(lambda: _knowledge_showcase.documents)
        total_chunks = _knowledge_showcase.total_chunks
    return {
        "document_count": len(documents),
        "total_chunks": total_chunks,
        "documents": [
            {
                "document_id": d.document_id,
                "document_name": d.document_name,
                "label": d.label,
                "project": d.project,
                "source": d.source,
                "chunk_count": d.chunk_count,
                "page_count": d.page_count,
            }
            for d in documents
        ],
    }


@app.post("/knowledge/showcase/search")
async def search_knowledge_showcase(request: KnowledgeSearchRequest) -> dict:
    """Hybrid (metadata-filter + BM25 + TF-IDF) search over the real
    datasheet Knowledge Base showcase. Returns ranked chunks with
    document/page/section provenance and similarity scores."""
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="query must not be empty")
    async with _knowledge_showcase_lock:
        chunks = await run_in_threadpool(_knowledge_showcase.search, request.query, request.top_k)
    return {"query": request.query, "results": [c.model_dump(mode="json") for c in chunks]}


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "kicad_available": _service.kicad_available()}


def _require_result(analysis_id: str):
    result = _service.get(analysis_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Unknown analysis_id: {analysis_id}")
    return result
