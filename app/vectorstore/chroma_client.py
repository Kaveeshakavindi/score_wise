from __future__ import annotations

import asyncio
from functools import lru_cache
from typing import Any

import chromadb
from chromadb.api import ClientAPI
from chromadb.api.models.Collection import Collection

from app.core.config import Settings

# One shared collection for every subject/topic — retrieval scopes to a
# subject via a Chroma `where` metadata filter (§3 of the tutor RAG spec)
# rather than one collection per subject, so onboarding a new subject never
# requires provisioning anything new.
SYLLABUS_COLLECTION_NAME = "syllabus_chunks"

_collection_lock = asyncio.Lock()
_collection: Collection | None = None


@lru_cache
def _http_client(host: str, port: int) -> ClientAPI:
    # chromadb.HttpClient talks to the standalone `chromadb` container defined
    # in docker-compose.yml, not an embedded on-disk client. Gunicorn runs
    # multiple worker processes (§14 of api.md); an embedded/SQLite-backed
    # Chroma client would hit write contention across those workers the same
    # way an in-process RAG store would, which is exactly what §9 of api.md
    # moved the generic chatbot's RAG store away from.
    return chromadb.HttpClient(host=host, port=port)


async def get_syllabus_collection(settings: Settings) -> Collection:
    """Lazily creates (or reconnects to) the shared syllabus collection once
    per process and keeps it warm — mirrors app/llm/embedder.py's
    module-level singleton for the local embedding model."""
    global _collection
    if _collection is None:
        async with _collection_lock:
            if _collection is None:
                client = _http_client(settings.chroma_host, settings.chroma_port)
                _collection = await asyncio.to_thread(
                    client.get_or_create_collection,
                    name=SYLLABUS_COLLECTION_NAME,
                    metadata={"hnsw:space": "cosine"},
                )
    return _collection


async def upsert_chunks(
    settings: Settings,
    *,
    ids: list[str],
    embeddings: list[list[float]],
    documents: list[str],
    metadatas: list[dict[str, Any]],
) -> None:
    """Stores chunk text + embedding + metadata (subject, topic,
    source_document_id, chunk_index — §2 step 4) for one syllabus document."""
    collection = await get_syllabus_collection(settings)
    await asyncio.to_thread(
        collection.upsert, ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas
    )


async def query_chunks(
    settings: Settings,
    *,
    query_embedding: list[float],
    subject: str,
    k: int,
) -> list[dict[str, Any]]:
    """Top-k syllabus chunks ranked by semantic similarity, filtered to the
    given subject (§3 step 2). Each result carries its stored metadata
    (subject/topic/source_document_id/chunk_index) alongside the chunk text
    so callers can build citations, not just prompt context."""
    collection = await get_syllabus_collection(settings)
    result = await asyncio.to_thread(
        collection.query,
        query_embeddings=[query_embedding],
        n_results=k,
        where={"subject": subject},
    )
    documents = (result.get("documents") or [[]])[0]
    metadatas = (result.get("metadatas") or [[]])[0]
    return [
        {"text": doc, **(meta or {})}
        for doc, meta in zip(documents, metadatas)
    ]


async def delete_document_chunks(settings: Settings, *, source_document_id: str) -> None:
    """Removes every chunk belonging to one syllabus document — the ChromaDB
    side of DELETE /api/v1/admin/documents/{document_id} (§2)."""
    collection = await get_syllabus_collection(settings)
    await asyncio.to_thread(collection.delete, where={"source_document_id": source_document_id})
