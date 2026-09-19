"""Engineering knowledge retriever (Phase 6/7): a `KnowledgeRetriever`
abstraction over document ingestion + hybrid retrieval.

Hybrid retrieval combines (per Phase 7):
  1. deterministic metadata filtering (component reference / net mentions)
  2. violation-type keyword filtering
  3. keyword search (BM25)
  4. sparse "semantic" vector retrieval (TF-IDF cosine similarity)

The vector backend is intentionally abstracted behind this class so a real
embedding-model-backed vector store (FAISS/Chroma/Qdrant/pgvector) can be
substituted later without changing the public interface used by the agent
tools (Phase 22: RAG abstraction).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, Union

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from pcb_ai.config import Settings, get_settings
from pcb_ai.rag.chunker import chunk_text
from pcb_ai.rag.pdf_utils import extract_pdf_text
from pcb_ai.schemas.knowledge import KnowledgeChunk

try:
    from rank_bm25 import BM25Okapi
except ImportError:  # pragma: no cover - declared dependency
    BM25Okapi = None  # type: ignore[assignment]

_SLUG_RE = re.compile(r"[^a-z0-9]+")

_DIR_SOURCE_HINTS: dict[str, str] = {
    "datasheet": "datasheet",
    "datasheets": "datasheet",
    "guideline": "design_guideline",
    "guidelines": "design_guideline",
    "appnote": "app_note",
    "app_notes": "app_note",
    "ipc": "ipc",
    "internal": "internal_doc",
}


def _slugify(name: str) -> str:
    return _SLUG_RE.sub("-", name.lower()).strip("-") or "document"


def _infer_source(path: Path) -> str:
    for parent in path.parents:
        hint = _DIR_SOURCE_HINTS.get(parent.name.lower())
        if hint:
            return hint
    return "engineering_document"


class KnowledgeRetriever:
    """In-process hybrid knowledge retriever backed by BM25 + TF-IDF.

    Not tied to a specific vector database; see module docstring.
    """

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self._chunks: list[KnowledgeChunk] = []
        self._documents: dict[str, dict] = {}
        self._vectorizer: Optional[TfidfVectorizer] = None
        self._tfidf_matrix = None
        self._bm25 = None
        self._dirty = True

    # --- ingestion ---------------------------------------------------------
    def index_document(
        self,
        text: str,
        document_name: str,
        source: str,
        document_id: Optional[str] = None,
    ) -> list[KnowledgeChunk]:
        document_id = document_id or _slugify(document_name)
        chunks = chunk_text(
            text,
            document_id=document_id,
            document_name=document_name,
            source=source,
            chunk_size_tokens=self.settings.chunk_size_tokens,
            overlap_tokens=self.settings.chunk_overlap_tokens,
        )
        self._chunks.extend(chunks)
        self._documents[document_id] = {
            "document_id": document_id,
            "document_name": document_name,
            "source": source,
            "chunk_count": len(chunks),
        }
        self._dirty = True
        return chunks

    def index_file(self, path: Union[str, Path]) -> list[KnowledgeChunk]:
        path = Path(path)
        suffix = path.suffix.lower()
        document_id = _slugify(path.stem)
        source = _infer_source(path)
        if suffix == ".pdf":
            text = extract_pdf_text(path)
        else:
            text = path.read_text(encoding="utf-8", errors="replace")
        return self.index_document(text, document_name=path.name, source=source, document_id=document_id)

    def index_directory(self, directory: Union[str, Path]) -> list[KnowledgeChunk]:
        directory = Path(directory)
        all_chunks: list[KnowledgeChunk] = []
        if not directory.exists():
            return all_chunks
        for path in sorted(directory.rglob("*")):
            if path.is_file() and path.suffix.lower() in {".txt", ".md", ".pdf"}:
                all_chunks.extend(self.index_file(path))
        return all_chunks

    def get_source(self, document_id: str) -> Optional[dict]:
        return self._documents.get(document_id)

    @property
    def chunk_count(self) -> int:
        return len(self._chunks)

    def save(self, path: Union[str, Path]) -> None:
        """Persist ingested chunks to a JSON file (Phase 29 `index-knowledge`)."""
        import json as json_lib

        data = [c.model_dump(mode="json") for c in self._chunks]
        Path(path).write_text(json_lib.dumps(data, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Union[str, Path], settings: Optional[Settings] = None) -> "KnowledgeRetriever":
        import json as json_lib

        kr = cls(settings)
        data = json_lib.loads(Path(path).read_text(encoding="utf-8"))
        kr._chunks = [KnowledgeChunk.model_validate(item) for item in data]
        kr._documents = {
            c.document_id: {"document_id": c.document_id, "document_name": c.document_name, "source": c.source}
            for c in kr._chunks
        }
        kr._dirty = True
        return kr

    # --- retrieval -----------------------------------------------------------
    def _rebuild_index(self) -> None:
        if not self._dirty:
            return
        texts = [c.text for c in self._chunks]
        if texts:
            self._vectorizer = TfidfVectorizer(stop_words="english")
            self._tfidf_matrix = self._vectorizer.fit_transform(texts)
            if BM25Okapi is not None:
                tokenized = [t.lower().split() for t in texts]
                self._bm25 = BM25Okapi(tokenized)
        else:
            self._vectorizer = None
            self._tfidf_matrix = None
            self._bm25 = None
        self._dirty = False

    def _score(self, query: str, candidate_indices: list[int]) -> dict[int, float]:
        scores: dict[int, float] = {}
        bm25_scores = []
        max_bm25 = 1.0
        if self._bm25 is not None:
            bm25_scores = self._bm25.get_scores(query.lower().split())
            max_bm25 = max(bm25_scores) if len(bm25_scores) and max(bm25_scores) > 0 else 1.0
        cos_scores = []
        if self._vectorizer is not None and self._tfidf_matrix is not None:
            query_vec = self._vectorizer.transform([query])
            cos_scores = cosine_similarity(query_vec, self._tfidf_matrix)[0]
        for i in candidate_indices:
            bm25_score = (bm25_scores[i] / max_bm25) if len(bm25_scores) else 0.0
            cos_score = float(cos_scores[i]) if len(cos_scores) else 0.0
            scores[i] = 0.5 * bm25_score + 0.5 * cos_score
        return scores

    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        component_references: Optional[list[str]] = None,
        violation_type: Optional[str] = None,
        net_names: Optional[list[str]] = None,
    ) -> list[KnowledgeChunk]:
        self._rebuild_index()
        if not self._chunks:
            return []
        top_k = top_k or self.settings.retrieval_top_k

        candidates = list(range(len(self._chunks)))

        # 1 & 2. deterministic metadata filtering (component / net mentions).
        for terms, label in ((component_references, "component"), (net_names, "net")):
            if not terms:
                continue
            terms_lower = [t.lower() for t in terms if t]
            if not terms_lower:
                continue
            filtered = [
                i
                for i in candidates
                if any(t in self._chunks[i].text.lower() for t in terms_lower)
                or any(t in [r.lower() for r in self._chunks[i].component_references] for t in terms_lower)
            ]
            if filtered:
                candidates = filtered

        # 3. violation-type keyword filtering.
        if violation_type:
            vt = violation_type.lower().replace("_", " ")
            filtered = [
                i
                for i in candidates
                if vt in self._chunks[i].text.lower()
                or any(vt in k.lower() for k in self._chunks[i].keywords)
            ]
            if filtered:
                candidates = filtered

        # 4/5. keyword (BM25) + sparse vector (TF-IDF cosine) hybrid scoring.
        scores = self._score(query, candidates)
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)

        results: list[KnowledgeChunk] = []
        for i, score in ranked[:top_k]:
            if score < self.settings.retrieval_similarity_threshold:
                continue
            results.append(self._chunks[i].model_copy(update={"similarity": round(score, 4)}))
        return results

    def search_by_component(self, reference: str, top_k: Optional[int] = None) -> list[KnowledgeChunk]:
        return self.search(reference, top_k=top_k, component_references=[reference])

    def search_by_violation_type(self, violation_type: str, top_k: Optional[int] = None) -> list[KnowledgeChunk]:
        return self.search(violation_type.replace("_", " "), top_k=top_k, violation_type=violation_type)
