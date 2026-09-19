"""Engineering knowledge chunk schema for the RAG layer (Phase 6)."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

KNOWLEDGE_SCHEMA_VERSION = "1.0"


class KnowledgeChunk(BaseModel):
    schema_version: str = KNOWLEDGE_SCHEMA_VERSION
    document_id: str
    document_name: str
    source: str  # datasheet | design_guideline | app_note | internal_doc | ipc | other
    page: Optional[int] = None
    section: Optional[str] = None
    chunk_id: str
    text: str
    component_references: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    similarity: Optional[float] = None
