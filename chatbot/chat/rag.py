from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterable

from sentence_transformers import SentenceTransformer

_ACTIVE_SESSION_ID: str | None = None
_STORE: dict[str, list["Chunk"]] = {}
_EMBEDDER: "LocalEmbedder | None" = None


class LocalEmbedder:
    """Wraps a local sentence-transformers model behind the embed_documents/embed_query
    interface the rest of this module expects (mirrors langchain's Embeddings shape)."""

    def __init__(self, model_name: str) -> None:
        self._model = SentenceTransformer(model_name)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [vec.tolist() for vec in self._model.encode(texts)]

    def embed_query(self, text: str) -> list[float]:
        return self._model.encode(text).tolist()


@dataclass(frozen=True)
class Chunk:
    source: str
    text: str
    embedding: list[float]


def set_active_session(session_id: str) -> None:
    global _ACTIVE_SESSION_ID
    _ACTIVE_SESSION_ID = session_id


def index_text(source: str, text: str, chunk_size: int = 800, overlap: int = 120) -> int:
    session_id = _require_session()
    chunks = list(_chunk_text(text, chunk_size, overlap))
    if not chunks:
        return 0

    embedder = _get_embedder()
    vectors = embedder.embed_documents([c for c in chunks])
    records = [Chunk(source=source, text=chunk, embedding=vec) for chunk, vec in zip(chunks, vectors)]
    _STORE.setdefault(session_id, []).extend(records)
    return len(records)


def retrieve(query: str, k: int = 4) -> list[str]:
    session_id = _require_session()
    records = _STORE.get(session_id, [])
    if not records:
        return []

    embedder = _get_embedder()
    qvec = embedder.embed_query(query)
    scored = [(chunk, _cosine_similarity(qvec, chunk.embedding)) for chunk in records]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [c.text for c, _ in scored[:k]]


def _get_embedder() -> LocalEmbedder:
    global _EMBEDDER
    if _EMBEDDER is None:
        model = os.environ.get("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        _EMBEDDER = LocalEmbedder(model)
    return _EMBEDDER


def _chunk_text(text: str, chunk_size: int, overlap: int) -> Iterable[str]:
    if chunk_size <= 0:
        return []
    step = max(1, chunk_size - overlap)
    for i in range(0, len(text), step):
        chunk = text[i : i + chunk_size].strip()
        if chunk:
            yield chunk


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _require_session() -> str:
    if not _ACTIVE_SESSION_ID:
        raise RuntimeError("No active session set for RAG.")
    return _ACTIVE_SESSION_ID
