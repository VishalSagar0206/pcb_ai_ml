"""End-to-end orchestration: PCB -> DRC -> context -> RAG -> LLM diagnosis
-> validation -> report. Used by both the API (Phase 15) and CLI (Phase 29)
so neither reimplements the pipeline wiring.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union

from pcb_ai.agent.pipeline import ViolationDiagnosisAgent
from pcb_ai.config import Settings, get_settings
from pcb_ai.context.graph import PCBGraph
from pcb_ai.drc.runner import find_kicad_cli, load_fixture_drc_report, run_kicad_drc
from pcb_ai.llm.base import BaseLLMProvider
from pcb_ai.llm.factory import get_llm_provider
from pcb_ai.observability.tracing import record_trace
from pcb_ai.parser.kicad_pcb_parser import parse_kicad_pcb_file
from pcb_ai.rag.retriever import KnowledgeRetriever
from pcb_ai.reporting.report_generator import generate_report
from pcb_ai.schemas.context import AnalysisTrace
from pcb_ai.schemas.diagnosis import ViolationDiagnosis
from pcb_ai.schemas.drc import DRCRunResult
from pcb_ai.schemas.pcb import PCBDesign


@dataclass
class AnalysisResult:
    analysis_id: str
    pcb: PCBDesign
    drc_result: DRCRunResult
    diagnoses: dict[str, ViolationDiagnosis] = field(default_factory=dict)
    traces: dict[str, AnalysisTrace] = field(default_factory=dict)
    report_markdown: str = ""


class AnalysisService:
    def __init__(
        self,
        settings: Optional[Settings] = None,
        llm_provider: Optional[BaseLLMProvider] = None,
        knowledge_retriever: Optional[KnowledgeRetriever] = None,
    ):
        self.settings = settings or get_settings()
        self._llm_provider = llm_provider
        self._knowledge_retriever = knowledge_retriever
        self._store: dict[str, AnalysisResult] = {}

    @property
    def llm_provider(self) -> BaseLLMProvider:
        if self._llm_provider is None:
            self._llm_provider = get_llm_provider(self.settings)
        return self._llm_provider

    @property
    def knowledge_retriever(self) -> KnowledgeRetriever:
        if self._knowledge_retriever is None:
            kr = KnowledgeRetriever(self.settings)
            kr.index_directory(self.settings.knowledge_path)
            kr.index_directory(self.settings.datasheet_path)
            self._knowledge_retriever = kr
        return self._knowledge_retriever

    def parse_and_drc(
        self,
        pcb_path: Union[str, Path],
        drc_fixture_path: Optional[Union[str, Path]] = None,
    ) -> tuple[PCBDesign, DRCRunResult]:
        """Parse + run/load DRC only, skipping the (LLM-costly) per-violation
        diagnosis loop. Used by callers -- e.g. the `query` CLI command --
        that only need the board/violations, not pre-computed diagnoses."""
        pcb = parse_kicad_pcb_file(pcb_path)
        if drc_fixture_path is not None:
            drc_result = load_fixture_drc_report(drc_fixture_path, pcb)
        else:
            drc_result = run_kicad_drc(pcb_path, pcb, settings=self.settings)
        return pcb, drc_result

    def analyze(
        self,
        pcb_path: Union[str, Path],
        drc_fixture_path: Optional[Union[str, Path]] = None,
        analysis_id: Optional[str] = None,
    ) -> AnalysisResult:
        analysis_id = analysis_id or str(uuid.uuid4())
        pcb = parse_kicad_pcb_file(pcb_path)
        graph = PCBGraph(pcb)

        if drc_fixture_path is not None:
            drc_result = load_fixture_drc_report(drc_fixture_path, pcb)
        else:
            drc_result = run_kicad_drc(pcb_path, pcb, settings=self.settings)

        agent = ViolationDiagnosisAgent(
            self.llm_provider,
            knowledge_retriever=self.knowledge_retriever,
            settings=self.settings,
        )

        diagnoses: dict[str, ViolationDiagnosis] = {}
        traces: dict[str, AnalysisTrace] = {}
        for violation in drc_result.violations:
            diagnosis, trace = agent.diagnose(violation, graph, analysis_id=analysis_id)
            record_trace(trace, settings=self.settings)
            diagnoses[violation.violation_id] = diagnosis
            traces[violation.violation_id] = trace

        report = generate_report(pcb, drc_result, diagnoses, analysis_id=analysis_id)

        result = AnalysisResult(
            analysis_id=analysis_id,
            pcb=pcb,
            drc_result=drc_result,
            diagnoses=diagnoses,
            traces=traces,
            report_markdown=report,
        )
        self._store[analysis_id] = result
        return result

    def get(self, analysis_id: str) -> Optional[AnalysisResult]:
        return self._store.get(analysis_id)

    def kicad_available(self) -> bool:
        return find_kicad_cli(self.settings) is not None
