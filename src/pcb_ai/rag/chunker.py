"""Document chunking for the engineering-knowledge RAG layer (Phase 6).

Chunking is section/page-aware rather than an arbitrary fixed-size split:
we first split on explicit page markers (`--- page N ---`, inserted by the
PDF extractor) and Markdown-style section headers, then group the words
within each (page, section) block into ~chunk_size_tokens chunks with
overlap, so provenance (page/section) is preserved per chunk.
"""
from __future__ import annotations

import re
from typing import Optional

from pcb_ai.schemas.knowledge import KnowledgeChunk

_SECTION_HEADER_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_PAGE_MARKER_RE = re.compile(r"^-{2,}\s*page\s+(\d+)\s*-{2,}$", re.IGNORECASE)


def split_into_blocks(text: str) -> list[tuple[Optional[int], Optional[str], str]]:
    """Split raw text into (page, section, content) blocks."""
    lines = text.splitlines()
    blocks: list[tuple[Optional[int], Optional[str], str]] = []
    current_page: Optional[int] = None
    current_section: Optional[str] = None
    buffer: list[str] = []

    def flush() -> None:
        content = "\n".join(buffer).strip()
        if content:
            blocks.append((current_page, current_section, content))
        buffer.clear()

    for line in lines:
        page_match = _PAGE_MARKER_RE.match(line.strip())
        if page_match:
            flush()
            current_page = int(page_match.group(1))
            continue
        header_match = _SECTION_HEADER_RE.match(line)
        if header_match:
            flush()
            current_section = header_match.group(2).strip()
            continue
        buffer.append(line)
    flush()

    if not blocks and text.strip():
        blocks.append((None, None, text.strip()))
    return blocks


def chunk_text(
    text: str,
    document_id: str,
    document_name: str,
    source: str,
    chunk_size_tokens: int = 350,
    overlap_tokens: int = 60,
) -> list[KnowledgeChunk]:
    """Chunk `text` into `KnowledgeChunk`s, one per ~chunk_size_tokens words
    within each (page, section) block, with `overlap_tokens` word overlap
    between consecutive chunks of the same block."""
    if chunk_size_tokens <= 0:
        raise ValueError("chunk_size_tokens must be positive")
    if overlap_tokens < 0 or overlap_tokens >= chunk_size_tokens:
        overlap_tokens = min(max(overlap_tokens, 0), chunk_size_tokens // 2)

    chunks: list[KnowledgeChunk] = []
    idx = 0
    for page, section, content in split_into_blocks(text):
        words = content.split()
        if not words:
            continue
        start = 0
        while start < len(words):
            end = min(start + chunk_size_tokens, len(words))
            chunk_words = words[start:end]
            chunk_id = f"{document_id}::chunk{idx}"
            chunks.append(
                KnowledgeChunk(
                    document_id=document_id,
                    document_name=document_name,
                    source=source,
                    page=page,
                    section=section,
                    chunk_id=chunk_id,
                    text=" ".join(chunk_words),
                )
            )
            idx += 1
            if end == len(words):
                break
            start = end - overlap_tokens
    return chunks
