"""Knowledge Base showcase (separate from the live diagnosis pipeline's
retriever): indexes a curated set of REAL component datasheets from the
reference `pcb_qa-4FEE` benchmark repository, so the frontend can
demonstrate the hybrid-retrieval RAG layer (Phase 6/7) against genuine
manufacturer PDFs instead of only the small synthetic fixture used by the
demo board's diagnosis pipeline.

Deliberately kept isolated from `AnalysisService.knowledge_retriever`:
the pcb_qa-4FEE datasheets are for entirely different real hardware
projects (e.g. AcornRobotElectronics' actual "U3"), and the bundled demo
board also happens to have a component named "U3" (a synthetic MCU). If
both were indexed into the same retriever, a reference-based search for
the demo board's "U3" clearance violation could retrieve and cite the
real AcornRobotElectronics U3 datasheet -- a completely different part --
which would silently corrupt the evidence-grounding guarantee the whole
pipeline is built around. Keeping this as a separate, read-only showcase
avoids that failure mode entirely while still letting the RAG layer be
demonstrated against rich, real-world content.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from pcb_ai.config import Settings, get_settings
from pcb_ai.rag.retriever import KnowledgeRetriever
from pcb_ai.schemas.knowledge import KnowledgeChunk

# (project_dir_under_outputs, datasheet_filename, human label) -- a curated,
# size-bounded selection spanning multiple real hardware projects and
# component categories (regulators, switches, connectors, diodes, motor
# drivers, passives), chosen to keep first-request indexing latency
# reasonable (a few seconds total) while still being genuinely
# representative real-world content. Verified against the actual files
# present under each project's `outputs/<project>/datasheets/` directory.
CURATED_DATASHEETS: list[tuple[str, str, str]] = [
    ("AcornRobotElectronics", "U28.pdf", "U28 IC (AcornRobotElectronics)"),
    ("AcornRobotElectronics", "U6.pdf", "U6 IC (AcornRobotElectronics)"),
    ("CF-Chef", "D1.pdf", "D1 Diode (CF-Chef)"),
    ("CF-Chef", "U8.pdf", "U8 IC (CF-Chef)"),
    ("HadesFCS", "REG1.pdf", "REG1 Voltage Regulator (HadesFCS)"),
    ("HadesFCS", "SW2.pdf", "SW2 Switch (HadesFCS)"),
    ("HadesFCS", "U4.pdf", "U4 IC (HadesFCS)"),
    ("Meshinger", "J2.pdf", "J2 Connector (Meshinger)"),
    ("Meshinger", "S1.pdf", "S1 Switch (Meshinger)"),
    ("Meshinger", "U6.pdf", "U6 IC (Meshinger)"),
    ("OPNhydro-r2", "M1.pdf", "M1 Motor Driver (OPNhydro-r2)"),
    ("PortalHardware", "C2.pdf", "C2 Capacitor (PortalHardware)"),
]


@dataclass
class ShowcaseDocument:
    document_id: str
    document_name: str
    label: str
    project: str
    source: str
    chunk_count: int
    page_count: Optional[int]


class KnowledgeBaseShowcase:
    """Lazily indexes `CURATED_DATASHEETS` on first use, then serves
    document listing and hybrid search against them."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self._retriever: Optional[KnowledgeRetriever] = None
        self._documents: list[ShowcaseDocument] = []

    def _ensure_indexed(self) -> None:
        if self._retriever is not None:
            return
        retriever = KnowledgeRetriever(self.settings)
        documents: list[ShowcaseDocument] = []
        base_dir = self.settings.pcb_qa_reference_path / "outputs"

        for project, filename, label in CURATED_DATASHEETS:
            pdf_path = base_dir / project / "datasheets" / filename
            if not pdf_path.exists():
                continue
            document_id = f"{project.lower()}-{Path(filename).stem.lower()}"
            chunks = retriever.index_document(
                _safe_extract(pdf_path),
                document_name=f"{project}/{filename}",
                source="datasheet",
                document_id=document_id,
            )
            page_numbers = {c.page for c in chunks if c.page is not None}
            documents.append(
                ShowcaseDocument(
                    document_id=document_id,
                    document_name=filename,
                    label=label,
                    project=project,
                    source="datasheet",
                    chunk_count=len(chunks),
                    page_count=max(page_numbers) if page_numbers else None,
                )
            )

        self._retriever = retriever
        self._documents = documents

    @property
    def documents(self) -> list[ShowcaseDocument]:
        self._ensure_indexed()
        return self._documents

    @property
    def total_chunks(self) -> int:
        self._ensure_indexed()
        return sum(d.chunk_count for d in self._documents)

    def search(self, query: str, top_k: int = 8) -> list[KnowledgeChunk]:
        self._ensure_indexed()
        assert self._retriever is not None
        return self._retriever.search(query, top_k=top_k)


def _safe_extract(pdf_path: Path) -> str:
    from pcb_ai.rag.pdf_utils import extract_pdf_text

    try:
        return extract_pdf_text(pdf_path)
    except Exception:  # noqa: BLE001 - a single unparsable PDF must not break the showcase
        return ""
