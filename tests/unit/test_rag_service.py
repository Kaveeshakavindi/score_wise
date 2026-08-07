from __future__ import annotations

import uuid

import pytest

import app.services.rag_service as rag_service_module
from app.core.exceptions import NotFoundError
from app.services.rag_service import RagService, _chunk_text
from tests.fakes import FakeRagChunkRepository


def test_chunk_text_splits_on_size_with_overlap() -> None:
    text = "a" * 1000
    chunks = list(_chunk_text(text, chunk_size=800, overlap=120))
    assert len(chunks) == 2
    assert all(len(c) <= 800 for c in chunks)


def test_chunk_text_short_text_single_chunk() -> None:
    chunks = list(_chunk_text("hello world", chunk_size=800, overlap=120))
    assert chunks == ["hello world"]


def test_chunk_text_empty_text_no_chunks() -> None:
    assert list(_chunk_text("", chunk_size=800, overlap=120)) == []


def test_chunk_text_zero_chunk_size_returns_empty() -> None:
    assert list(_chunk_text("hello", chunk_size=0, overlap=0)) == []


class _FakeEmbedder:
    pass


async def _fake_get_embedder(model_name: str) -> _FakeEmbedder:
    return _FakeEmbedder()


async def _fake_embed_documents(embedder: _FakeEmbedder, texts: list[str]) -> list[list[float]]:
    return [[0.1, 0.2, 0.3] for _ in texts]


async def _fake_embed_query(embedder: _FakeEmbedder, text: str) -> list[float]:
    return [0.1, 0.2, 0.3]


@pytest.fixture
def rag_service(settings, monkeypatch) -> tuple[RagService, FakeRagChunkRepository]:
    # RagService's methods are thin orchestration over the repository +
    # embedder; both are swapped for fakes so this never loads the real
    # sentence-transformers/torch model or touches Postgres (§13).
    monkeypatch.setattr(rag_service_module, "get_embedder", _fake_get_embedder)
    monkeypatch.setattr(rag_service_module, "embed_documents", _fake_embed_documents)
    monkeypatch.setattr(rag_service_module, "embed_query", _fake_embed_query)
    repo = FakeRagChunkRepository()
    return RagService(repo, settings), repo


async def test_index_text_chunks_and_stores_them(rag_service) -> None:
    service, _ = rag_service
    session_id = uuid.uuid4()

    document = await service.index_text(session_id, "note.txt", "a" * 1000, chunk_size=800, overlap=120)

    assert document.session_id == session_id
    assert await service.chunk_count(document.id) == 2


async def test_index_text_empty_text_creates_document_without_chunks(rag_service) -> None:
    service, _ = rag_service
    document = await service.index_text(uuid.uuid4(), "empty.txt", "")
    assert await service.chunk_count(document.id) == 0


async def test_retrieve_only_returns_chunks_from_the_given_session(rag_service) -> None:
    service, _ = rag_service
    session_a = uuid.uuid4()
    session_b = uuid.uuid4()
    await service.index_text(session_a, "a.txt", "content indexed for session a")
    await service.index_text(session_b, "b.txt", "content indexed for session b")

    results = await service.retrieve(session_a, "query", k=4)

    assert results
    assert all("session a" in chunk for chunk in results)


async def test_list_and_count_documents_scoped_to_session(rag_service) -> None:
    service, _ = rag_service
    session_id = uuid.uuid4()
    await service.index_text(session_id, "a.txt", "text a")
    await service.index_text(session_id, "b.txt", "text b")
    await service.index_text(uuid.uuid4(), "other.txt", "someone else's session")

    documents = await service.list_documents(session_id, limit=20, offset=0)
    total = await service.count_documents(session_id)

    assert total == 2
    assert {d.source for d in documents} == {"a.txt", "b.txt"}


async def test_delete_document_wrong_session_raises_not_found(rag_service) -> None:
    service, _ = rag_service
    session_id = uuid.uuid4()
    document = await service.index_text(session_id, "note.txt", "some text")

    with pytest.raises(NotFoundError):
        await service.delete_document(uuid.uuid4(), document.id)


async def test_delete_document_removes_it_from_the_repository(rag_service) -> None:
    service, repo = rag_service
    session_id = uuid.uuid4()
    document = await service.index_text(session_id, "note.txt", "some text")

    await service.delete_document(session_id, document.id)

    assert await repo.get_document(document.id) is None
