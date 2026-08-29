from __future__ import annotations

import uuid

import pytest
from document_extraction import DocumentExtractionError, ExtractionMethod, ExtractionResult

import app.services.syllabus_ingestion_service as ingestion_module
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.services.syllabus_ingestion_service import SyllabusIngestionService
from app.vectorstore import chroma_client as chroma_client_module
from tests.fakes import FakeDocumentExtractionService, FakeSyllabusDocumentRepository


async def _fake_get_embedder(model_name: str):
    return object()


async def _fake_embed_documents(embedder, texts: list[str]) -> list[list[float]]:
    return [[0.1, 0.2] for _ in texts]


@pytest.fixture
def ingestion(settings, monkeypatch):
    repo = FakeSyllabusDocumentRepository()
    document_extraction = FakeDocumentExtractionService(text="a" * 1000)
    service = SyllabusIngestionService(repo, document_extraction, settings)

    # Embedder is swapped for a fake so this never loads the real
    # sentence-transformers model (§13); document extraction is already a
    # fake (never parses real PDF bytes or calls Claude).
    monkeypatch.setattr(ingestion_module, "get_embedder", _fake_get_embedder)
    monkeypatch.setattr(ingestion_module, "embed_documents", _fake_embed_documents)

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


async def test_extraction_failure_is_translated_to_validation_error(ingestion) -> None:
    """Covers both DocumentExtractionService failure modes -- unreadable
    file and a failed vision fallback call -- since both raise the same
    DocumentExtractionError and are translated identically here."""
    service, _, _, _ = ingestion

    class _FailingExtraction:
        async def extract(self, pdf_bytes: bytes, filename: str):
            raise DocumentExtractionError("not a readable PDF")

    service._document_extraction = _FailingExtraction()

    with pytest.raises(ValidationError):
        await service.ingest_pdf(document_id=None, filename="a.pdf", subject="Physics", topic=None, pdf_bytes=b"x")


async def test_blank_extraction_result_raises_validation_error(ingestion) -> None:
    """Even a successful extraction (no exception) with empty/whitespace-only
    text -- e.g. Claude transcribed a genuinely blank scanned page -- must
    not silently proceed to chunk/embed/store nothing."""
    service, _, _, _ = ingestion

    class _BlankExtraction:
        async def extract(self, pdf_bytes: bytes, filename: str) -> ExtractionResult:
            return ExtractionResult(
                text="   ",
                method=ExtractionMethod.VISION,
                raw_pdf_bytes=pdf_bytes,
                page_count=1,
                confidence_hint=None,
                filename=filename,
            )

    service._document_extraction = _BlankExtraction()

    with pytest.raises(ValidationError):
        await service.ingest_pdf(document_id=None, filename="a.pdf", subject="Physics", topic=None, pdf_bytes=b"x")
