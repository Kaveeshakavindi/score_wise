from __future__ import annotations

import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RagChunk, RagDocument


class RagChunkRepository:
    """Persistent, multi-worker-safe replacement for chat/rag.py's in-process
    `_STORE` dict (§9). Retrieval is an indexed pgvector nearest-neighbor query
    instead of the CLI's O(n) Python cosine-similarity loop."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_document(self, session_id: uuid.UUID, source: str) -> RagDocument:
        document = RagDocument(session_id=session_id, source=source)
        self._session.add(document)
        await self._session.flush()
        return document

    async def create_chunks(
        self, document_id: uuid.UUID, session_id: uuid.UUID, chunks: list[str], embeddings: list[list[float]]
    ) -> int:
        for index, (content, embedding) in enumerate(zip(chunks, embeddings)):
            self._session.add(
                RagChunk(
                    document_id=document_id,
                    session_id=session_id,
                    chunk_index=index,
                    content=content,
                    embedding=embedding,
                )
            )
        await self._session.flush()
        return len(chunks)

    async def list_documents(self, session_id: uuid.UUID, *, limit: int, offset: int) -> list[RagDocument]:
        result = await self._session.execute(
            select(RagDocument)
            .where(RagDocument.session_id == session_id)
            .order_by(RagDocument.indexed_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def count_documents(self, session_id: uuid.UUID) -> int:
        result = await self._session.execute(
            select(func.count()).select_from(RagDocument).where(RagDocument.session_id == session_id)
        )
        return int(result.scalar_one())

    async def get_document(self, document_id: uuid.UUID) -> RagDocument | None:
        return await self._session.get(RagDocument, document_id)

    async def chunk_count(self, document_id: uuid.UUID) -> int:
        result = await self._session.execute(
            select(func.count()).select_from(RagChunk).where(RagChunk.document_id == document_id)
        )
        return int(result.scalar_one())

    async def delete_document(self, document_id: uuid.UUID) -> None:
        await self._session.execute(delete(RagDocument).where(RagDocument.id == document_id))

    async def retrieve(self, session_id: uuid.UUID, query_embedding: list[float], k: int) -> list[str]:
        """Nearest-neighbor search scoped to a session, via pgvector's cosine
        distance operator (`<=>`), backed by the ivfflat index (§9)."""
        result = await self._session.execute(
            select(RagChunk.content)
            .where(RagChunk.session_id == session_id)
            .order_by(RagChunk.embedding.cosine_distance(query_embedding))
            .limit(k)
        )
        return list(result.scalars().all())
