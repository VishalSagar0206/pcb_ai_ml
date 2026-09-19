"""Unit tests for the knowledge chunker and retriever (Phase 6/7)."""
from __future__ import annotations

from pathlib import Path

from pcb_ai.rag.chunker import chunk_text, split_into_blocks
from pcb_ai.rag.retriever import KnowledgeRetriever

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_split_into_blocks_respects_page_markers_and_headers():
    text = "--- page 1 ---\n# Intro\nHello world\n--- page 2 ---\n## Details\nMore text here"
    blocks = split_into_blocks(text)
    pages = [b[0] for b in blocks]
    assert 1 in pages
    assert 2 in pages
    sections = [b[1] for b in blocks]
    assert "Intro" in sections
    assert "Details" in sections


def test_chunk_text_respects_size_and_overlap():
    text = " ".join(f"word{i}" for i in range(1000))
    chunks = chunk_text(text, "doc1", "Doc One", "engineering_document", chunk_size_tokens=100, overlap_tokens=20)
    assert len(chunks) > 1
    assert all(c.document_id == "doc1" for c in chunks)
    # consecutive chunks should overlap by exactly `overlap_tokens` words
    first_words = chunks[0].text.split()
    second_words = chunks[1].text.split()
    assert first_words[-20:] == second_words[:20]


def test_retriever_indexes_and_searches_fixture_documents():
    kr = KnowledgeRetriever()
    kr.index_directory(FIXTURES_DIR / "knowledge")
    kr.index_directory(FIXTURES_DIR / "datasheets")
    assert kr.chunk_count > 0

    results = kr.search_by_violation_type("track_width", top_k=3)
    assert len(results) > 0
    assert any("track width" in r.text.lower() for r in results)


def test_retriever_component_filter_narrows_results():
    kr = KnowledgeRetriever()
    kr.index_directory(FIXTURES_DIR / "datasheets")
    results = kr.search_by_component("U3", top_k=5)
    assert len(results) > 0
    assert all("u3" in r.text.lower() or "u3" in r.document_name.lower() for r in results)


def test_retriever_save_and_load_round_trip(tmp_path):
    kr = KnowledgeRetriever()
    kr.index_directory(FIXTURES_DIR / "knowledge")
    save_path = tmp_path / "index.json"
    kr.save(save_path)

    loaded = KnowledgeRetriever.load(save_path)
    assert loaded.chunk_count == kr.chunk_count
    results = loaded.search("clearance", top_k=3)
    assert len(results) > 0
