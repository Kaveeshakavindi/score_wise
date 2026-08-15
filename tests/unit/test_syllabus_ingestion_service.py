from __future__ import annotations

import uuid

import pytest

import app.services.syllabus_ingestion_service as ingestion_module
from app.core.exceptions import ConflictError, NotFoundError
from app.services.syllabus_ingestion_service import SyllabusIngestionService
from app.vectorstore import chroma_client as chroma_client_module
from tests.fakes import FakeSyllabusDocumentRepository


async def _fake_get_embedder(model_name: str):
    return object()


async def _fake_embed_documents(embedder, texts: list[str]) -> list[list[float]]:
    return [[0.1, 0.2] for _ in texts]


@pytest.fixture
def ingestion(settings, monkeypatch):
    repo = FakeSyllabusDocumentRepository()
    service = SyllabusIngestionService(repo, settings)

    # Embedder and PDF extraction are swapped for fakes so this never loads
    # the real sentence-transformers model or parses real PDF bytes (§13).
    monkeypatch.setattr(ingestion_module, "get_embedder", _fake_get_embedder)
    monkeypatch.setattr(ingestion_module, "embed_documents", _fake_embed_documents)
    monkeypatch.setattr(ingestion_module, "extract_text_from_pdf", lambda data: "a" * 1000)

    upserts: list[dict] = []
    deletes: list[str] = []

    async def _fake_upsert(settings, *, ids, embeddings, documents, metadatas):
        upserts.append({"ids": ids, "documents": documents, "metadatas": metadatas})

    async def _fake_delete(settings, *, source_document_id):
        deletes.append(source_document_id)

    monkeypatch.setattr(chroma_client_module, "upsert_chunks", _fake_upsert)
    monkeypatch.setattr(chroma_client_module, "delete_document_chunks", _fake_delete)

    return service, repo, upserts, deletes


async def test_ingest_pdf_chunks_embeds_and_stores_in_chroma_and_sql(ingestion) -> None:
    service, repo, upserts, _ = ingestion

    document = await service.ingest_pdf(
        document_id=None, filename="syllabus.pdf", subject="Physics", topic="Grade 12", pdf_bytes=b"%PDF-fake"
    )

    assert document.chunk_count == 2  # 1000 "a" chars @ chunk_size=800/overlap=120 -> 2 chunks
    assert len(upserts) == 1
    assert upserts[0]["metadatas"][0]["subject"] == "Physics"
    assert upserts[0]["metadatas"][0]["topic"] == "Grade 12"
    assert upserts[0]["metadatas"][0]["source_document_id"] == str(document.id)
    assert await repo.get_by_id(document.id) is not None


async def test_ingest_pdf_with_explicit_uuid_uses_it_as_the_document_id(ingestion) -> None:
    service, _, _, _ = ingestion
    document_id = uuid.uuid4()

    document = await service.ingest_pdf(
        document_id=document_id, filename="a.pdf", subject="Chemistry", topic=None, pdf_bytes=b"x"
    )

    assert document.id == document_id


async def test_ingest_pdf_duplicate_uuid_raises_conflict(ingestion) -> None:
    service, _, _, _ = ingestion
    document_id = uuid.uuid4()
    await service.ingest_pdf(document_id=document_id, filename="a.pdf", subject="Chemistry", topic=None, pdf_bytes=b"x")

    with pytest.raises(ConflictError):
        await service.ingest_pdf(
            document_id=document_id, filename="b.pdf", subject="Chemistry", topic=None, pdf_bytes=b"y"
        )


async def test_list_documents_returns_all_uploads(ingestion) -> None:
    service, _, _, _ = ingestion
    await service.ingest_pdf(document_id=None, filename="a.pdf", subject="Physics", topic=None, pdf_bytes=b"x")
    await service.ingest_pdf(document_id=None, filename="b.pdf", subject="Chemistry", topic=None, pdf_bytes=b"y")

    items, total = await service.list_documents(limit=20, offset=0)

    assert total == 2
    assert {d.filename for d in items} == {"a.pdf", "b.pdf"}


async def test_delete_document_removes_from_sql_and_chroma(ingestion) -> None:
    service, repo, _, deletes = ingestion
    document = await service.ingest_pdf(
        document_id=None, filename="a.pdf", subject="Physics", topic=None, pdf_bytes=b"x"
    )

    await service.delete_document(document.id)

    assert await repo.get_by_id(document.id) is None
    assert deletes == [str(document.id)]


async def test_delete_missing_document_raises_not_found(ingestion) -> None:
    service, _, _, _ = ingestion
    with pytest.raises(NotFoundError):
        await service.delete_document(uuid.uuid4())
