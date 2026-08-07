from __future__ import annotations

import asyncio

from sentence_transformers import SentenceTransformer

_embedder: "LocalEmbedder | None" = None
_embedder_lock = asyncio.Lock()


class LocalEmbedder:
    """Wraps a local sentence-transformers model (all-MiniLM-L6-v2, 384-dim, no
    external API — Anthropic doesn't offer an embeddings endpoint). Loaded once
    per worker process and kept warm as a module-level singleton (§14)."""

    def __init__(self, model_name: str) -> None:
        self._model = SentenceTransformer(model_name)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [vec.tolist() for vec in self._model.encode(texts)]

    def embed_query(self, text: str) -> list[float]:
        return self._model.encode(text).tolist()


async def get_embedder(model_name: str) -> LocalEmbedder:
    global _embedder
    if _embedder is None:
        async with _embedder_lock:
            if _embedder is None:
                # sentence-transformers/torch model loading is CPU-bound and
                # blocking; run it off the event loop thread.
                _embedder = await asyncio.to_thread(LocalEmbedder, model_name)
    return _embedder


async def embed_documents(embedder: LocalEmbedder, texts: list[str]) -> list[list[float]]:
    return await asyncio.to_thread(embedder.embed_documents, texts)


async def embed_query(embedder: LocalEmbedder, text: str) -> list[float]:
    return await asyncio.to_thread(embedder.embed_query, text)
