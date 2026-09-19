"""PDF text extraction for datasheet ingestion. Inserts explicit page
markers so the chunker can preserve page-level provenance (Phase 6)."""
from __future__ import annotations

from pathlib import Path
from typing import Union


def extract_pdf_text(path: Union[str, Path]) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - dependency declared in pyproject
        raise RuntimeError("pypdf is required to ingest PDF datasheets (pip install pypdf)") from exc

    reader = PdfReader(str(path))
    parts: list[str] = []
    for page_number, page in enumerate(reader.pages, start=1):
        parts.append(f"--- page {page_number} ---")
        parts.append(page.extract_text() or "")
    return "\n".join(parts)
