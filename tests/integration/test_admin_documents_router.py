from __future__ import annotations

import uuid

import httpx
import pytest

import app.services.syllabus_ingestion_service as ingestion_module
from app.core.config import get_settings
from app.core.deps import get_current_user, get_redis, get_syllabus_document_repository
from app.main import app
from app.vectorstore import chroma_client as chroma_client_module
from tests.fakes import FakeRedis, FakeSyllabusDocumentRepository

_HEADERS = {"Authorization": "Bearer test-token"}


@pytest.fixture
async def client(test_user, monkeypatch):
    repo = FakeSyllabusDocumentRepository()

    app.dependency_overrides[get_current_user] = lambda: test_user
    app.dependency_overrides[get_syllabus_document_repository] = lambda: repo
    app.dependency_overrides[get_redis] = lambda: FakeRedis()

    monkeypatch.setattr(ingestion_module, "get_embedder", lambda model_name: _async_value(object()))
    monkeypatch.setattr(ingestion_module, "embed_documents", lambda embedder, texts: _async_value([[0.1] for _ in texts]))
    monkeypatch.setattr(ingestion_module, "extract_text_from_pdf", lambda data: "syllabus content " * 100)

    async def _fake_upsert(settings, *, ids, embeddings, documents, metadatas):
        pass

    deletes: list[str] = []

    async def _fake_delete(settings, *, source_document_id):
        deletes.append(source_document_id)

    monkeypatch.setattr(chroma_client_module, "upsert_chunks", _fake_upsert)
    monkeypatch.setattr(chroma_client_module, "delete_document_chunks", _fake_delete)

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac, repo, deletes

    app.dependency_overrides.clear()


async def _async_value(value):
    return value


async def test_upload_pdf_extracts_chunks_embeds_and_records_upload(client) -> None:
    ac, repo, _ = client
    response = await ac.post(
        "/api/v1/admin/documents",
        files={"file": ("physics-syllabus.pdf", b"%PDF-1.4 fake bytes", "application/pdf")},
        data={"subject": "Physics", "grade_level": "Grade 12"},
        headers=_HEADERS,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["filename"] == "physics-syllabus.pdf"
    assert body["subject"] == "Physics"
    assert body["topic"] == "Grade 12"  # grade_level input stored as topic — see SyllabusDocumentOut docstring
    assert body["chunk_count"] > 0
    assert await repo.get_by_id(uuid.UUID(body["id"])) is not None


async def test_upload_non_pdf_returns_415(client) -> None:
    ac, _, _ = client
    response = await ac.post(
        "/api/v1/admin/documents",
        files={"file": ("notes.txt", b"just text", "text/plain")},
        data={"subject": "Physics", "grade_level": "Grade 12"},
        headers=_HEADERS,
    )
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_media_type"


async def test_upload_oversized_pdf_returns_413(client, monkeypatch) -> None:
    ac, _, _ = client
    monkeypatch.setattr(get_settings(), "max_syllabus_upload_bytes", 10)

    response = await ac.post(
        "/api/v1/admin/documents",
        files={"file": ("big.pdf", b"%PDF-1.4" + b"x" * 100, "application/pdf")},
        data={"subject": "Physics", "grade_level": "Grade 12"},
        headers=_HEADERS,
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"


async def test_upload_with_explicit_uuid_then_duplicate_returns_409(client) -> None:
    ac, _, _ = client
    document_id = uuid.uuid4()

    first = await ac.post(
        "/api/v1/admin/documents",
        files={"file": ("a.pdf", b"%PDF-1.4 aaa", "application/pdf")},
        data={"subject": "Physics", "grade_level": "Grade 12", "uuid": str(document_id)},
        headers=_HEADERS,
    )
    assert first.status_code == 201
    assert first.json()["id"] == str(document_id)

    second = await ac.post(
        "/api/v1/admin/documents",
        files={"file": ("b.pdf", b"%PDF-1.4 bbb", "application/pdf")},
        data={"subject": "Physics", "grade_level": "Grade 12", "uuid": str(document_id)},
        headers=_HEADERS,
    )
    assert second.status_code == 409


async def test_list_documents_returns_uploads(client) -> None:
    ac, repo, _ = client
    await ac.post(
        "/api/v1/admin/documents",
        files={"file": ("a.pdf", b"%PDF-1.4 aaa", "application/pdf")},
        data={"subject": "Physics", "grade_level": "Grade 12"},
        headers=_HEADERS,
    )

    response = await ac.get("/api/v1/admin/documents", headers=_HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["filename"] == "a.pdf"


async def test_delete_document_removes_from_sql_and_chroma(client) -> None:
    ac, repo, deletes = client
    upload = await ac.post(
        "/api/v1/admin/documents",
        files={"file": ("a.pdf", b"%PDF-1.4 aaa", "application/pdf")},
        data={"subject": "Physics", "grade_level": "Grade 12"},
        headers=_HEADERS,
    )
    document_id = upload.json()["id"]

    response = await ac.delete(f"/api/v1/admin/documents/{document_id}", headers=_HEADERS)

    assert response.status_code == 204
    assert deletes == [document_id]
    assert await repo.get_by_id(uuid.UUID(document_id)) is None


async def test_delete_missing_document_returns_404(client) -> None:
    ac, _, _ = client
    response = await ac.delete(f"/api/v1/admin/documents/{uuid.uuid4()}", headers=_HEADERS)
    assert response.status_code == 404


async def test_admin_documents_require_auth() -> None:
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/api/v1/admin/documents")
    assert response.status_code == 401
