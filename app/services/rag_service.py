from __future__ import annotations

import uuid
from collections.abc import Iterable

from app.core.config import Settings
from app.core.exceptions import NotFoundError
from app.db.models import RagDocument
from app.llm.embedder import embed_documents, embed_query, get_embedder
from app.repositories.rag_chunk_repository import RagChunkRepository


class RagService:
    """Chunk/embed/store/retrieve, backed by pgvector (§9) — the persistent,
    multi-worker-safe replacement for chat/rag.py's in-memory `_STORE`."""

    def __init__(self, repo: RagChunkRepository, settings: Settings) -> None:
        self._repo = repo
        self._settings = settings

    async def index_text(
        self, session_id: uuid.UUID, source: str, text: str, *, chunk_size: int = 800, overlap: int = 120
    ) -> RagDocument:
        chunks = list(_chunk_text(text, chunk_size, overlap))
        document = await self._repo.create_document(session_id, source)
        if not chunks:
            return document

        embedder = await get_embedder(self._settings.embedding_model)
        vectors = await embed_documents(embedder, chunks)
        await self._repo.create_chunks(document.id, session_id, chunks, vectors)
        return document

    async def retrieve(self, session_id: uuid.UUID, query: str, k: int = 4) -> list[str]:
        embedder = await get_embedder(self._settings.embedding_model)
        query_vector = await embed_query(embedder, query)
        return await self._repo.retrieve(session_id, query_vector, k)

    async def list_documents(self, session_id: uuid.UUID, *, limit: int, offset: int):
        return await self._repo.list_documents(session_id, limit=limit, offset=offset)

    async def count_documents(self, session_id: uuid.UUID) -> int:
        return await self._repo.count_documents(session_id)

    async def chunk_count(self, document_id: uuid.UUID) -> int:
        return await self._repo.chunk_count(document_id)

    async def delete_document(self, session_id: uuid.UUID, document_id: uuid.UUID) -> None:
        document = await self._repo.get_document(document_id)
        if document is None or document.session_id != session_id:
            raise NotFoundError(f"Document {document_id} was not found.")
        await self._repo.delete_document(document_id)


def _chunk_text(text: str, chunk_size: int, overlap: int) -> Iterable[str]:
    if chunk_size <= 0:
        return []
    step = max(1, chunk_size - overlap)
    for i in range(0, len(text), step):
        chunk = text[i : i + chunk_size].strip()
        if chunk:
            yield chunk
