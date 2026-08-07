from __future__ import annotations

import uuid

import httpx
import pytest

import app.routers.documents as documents_module
from app.core.deps import get_current_user, get_rag_service, get_redis, get_session_repository
from app.main import app
from app.services.url_fetch import FetchResult
from tests.fakes import FakeRagService, FakeRedis, FakeSessionRepository

_HEADERS = {"Authorization": "Bearer test-token"}


@pytest.fixture
async def client(test_user, monkeypatch):
    fake_session_repo = FakeSessionRepository()
    fake_rag_service = FakeRagService()

    app.dependency_overrides[get_current_user] = lambda: test_user
    app.dependency_overrides[get_session_repository] = lambda: fake_session_repo
    app.dependency_overrides[get_rag_service] = lambda: fake_rag_service
    app.dependency_overrides[get_redis] = lambda: FakeRedis()

    async def _fake_fetch_url_safely(url: str, *, max_bytes: int, timeout_s: float = 8.0) -> FetchResult:
        return FetchResult(content_type="text/html; charset=utf-8", text="<html><body>Hello world</body></html>")

    monkeypatch.setattr(documents_module, "fetch_url_safely", _fake_fetch_url_safely)

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac, fake_session_repo, fake_rag_service

    app.dependency_overrides.clear()


async def test_ingest_url_strips_html_and_indexes_it(client, test_user) -> None:
    ac, session_repo, rag_service = client
    session = await session_repo.create(test_user.id)

    response = await ac.post(
        f"/api/v1/sessions/{session.id}/documents",
        json={"url": "https://example.com/page"},
        headers=_HEADERS,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["source"] == "https://example.com/page"

    assert len(rag_service.indexed) == 1
    _, source, text = rag_service.indexed[0]
    assert source == "https://example.com/page"
    assert "<html>" not in text
    assert "Hello world" in text


async def test_ingest_file_upload_indexes_raw_bytes(client, test_user) -> None:
    ac, session_repo, rag_service = client
    session = await session_repo.create(test_user.id)

    response = await ac.post(
        f"/api/v1/sessions/{session.id}/documents",
        files={"file": ("notes.txt", b"hello from a file", "text/plain")},
        headers=_HEADERS,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["source"] == "notes.txt"
    assert rag_service.indexed[-1][2] == "hello from a file"


async def test_ingest_document_not_owner_returns_404(client) -> None:
    ac, session_repo, _ = client
    other_session = await session_repo.create(uuid.uuid4())

    response = await ac.post(
        f"/api/v1/sessions/{other_session.id}/documents",
        json={"url": "https://example.com"},
        headers=_HEADERS,
    )
    assert response.status_code == 404


async def test_list_documents_returns_indexed_sources(client, test_user) -> None:
    ac, session_repo, rag_service = client
    session = await session_repo.create(test_user.id)
    await rag_service.index_text(session.id, "https://example.com", "some text")

    response = await ac.get(f"/api/v1/sessions/{session.id}/documents", headers=_HEADERS)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["source"] == "https://example.com"
    assert body["items"][0]["chunk_count"] == 1


async def test_delete_document_removes_it(client, test_user) -> None:
    ac, session_repo, rag_service = client
    session = await session_repo.create(test_user.id)
    document = await rag_service.index_text(session.id, "https://example.com", "text")

    response = await ac.delete(f"/api/v1/sessions/{session.id}/documents/{document.id}", headers=_HEADERS)
    assert response.status_code == 204

    listing = await ac.get(f"/api/v1/sessions/{session.id}/documents", headers=_HEADERS)
    assert listing.json()["total"] == 0


async def test_delete_document_not_found_returns_404(client, test_user) -> None:
    ac, session_repo, _ = client
    session = await session_repo.create(test_user.id)

    response = await ac.delete(f"/api/v1/sessions/{session.id}/documents/{uuid.uuid4()}", headers=_HEADERS)
    assert response.status_code == 404
