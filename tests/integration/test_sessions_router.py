from __future__ import annotations

import uuid

import httpx
import pytest

from app.core.deps import get_current_user, get_redis, get_session_repository
from app.main import app
from tests.fakes import FakeRedis, FakeSessionRepository

_HEADERS = {"Authorization": "Bearer test-token"}  # value is irrelevant; get_current_user is overridden


@pytest.fixture
async def client(test_user):
    fake_session_repo = FakeSessionRepository()
    app.dependency_overrides[get_current_user] = lambda: test_user
    app.dependency_overrides[get_session_repository] = lambda: fake_session_repo
    app.dependency_overrides[get_redis] = lambda: FakeRedis()

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac, fake_session_repo

    app.dependency_overrides.clear()


async def test_create_session_returns_201_with_null_title(client) -> None:
    ac, _ = client
    response = await ac.post("/api/v1/sessions", headers=_HEADERS)
    assert response.status_code == 201
    body = response.json()
    assert body["title"] is None
    assert "id" in body


async def test_list_sessions_returns_only_own_newest_active_first(client, test_user) -> None:
    ac, repo = client
    s1 = await repo.create(test_user.id)
    s2 = await repo.create(test_user.id)
    await repo.create(uuid.uuid4())  # someone else's session, must not leak in

    response = await ac.get("/api/v1/sessions", headers=_HEADERS)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert {item["id"] for item in body["items"]} == {str(s1.id), str(s2.id)}


async def test_get_session_returns_owned_session(client, test_user) -> None:
    ac, repo = client
    session = await repo.create(test_user.id)

    response = await ac.get(f"/api/v1/sessions/{session.id}", headers=_HEADERS)
    assert response.status_code == 200
    assert response.json()["id"] == str(session.id)


async def test_get_session_not_owner_returns_404_envelope(client) -> None:
    ac, repo = client
    other_session = await repo.create(uuid.uuid4())

    response = await ac.get(f"/api/v1/sessions/{other_session.id}", headers=_HEADERS)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_get_missing_session_returns_404(client) -> None:
    ac, _ = client
    response = await ac.get(f"/api/v1/sessions/{uuid.uuid4()}", headers=_HEADERS)
    assert response.status_code == 404


async def test_rename_session_updates_title(client, test_user) -> None:
    ac, repo = client
    session = await repo.create(test_user.id)

    response = await ac.patch(f"/api/v1/sessions/{session.id}", json={"title": "New Title"}, headers=_HEADERS)
    assert response.status_code == 200
    assert response.json()["title"] == "New Title"


async def test_rename_session_empty_title_returns_422(client, test_user) -> None:
    ac, repo = client
    session = await repo.create(test_user.id)

    response = await ac.patch(f"/api/v1/sessions/{session.id}", json={"title": ""}, headers=_HEADERS)
    assert response.status_code == 422


async def test_rename_session_not_owner_returns_404(client) -> None:
    ac, repo = client
    other_session = await repo.create(uuid.uuid4())

    response = await ac.patch(f"/api/v1/sessions/{other_session.id}", json={"title": "x"}, headers=_HEADERS)
    assert response.status_code == 404


async def test_delete_session_removes_it(client, test_user) -> None:
    ac, repo = client
    session = await repo.create(test_user.id)

    response = await ac.delete(f"/api/v1/sessions/{session.id}", headers=_HEADERS)
    assert response.status_code == 204
    assert await repo.get_by_id(session.id) is None


async def test_delete_session_not_owner_returns_404_and_leaves_it(client) -> None:
    ac, repo = client
    other_session = await repo.create(uuid.uuid4())

    response = await ac.delete(f"/api/v1/sessions/{other_session.id}", headers=_HEADERS)
    assert response.status_code == 404
    assert await repo.get_by_id(other_session.id) is not None


async def test_delete_all_sessions_only_removes_own(client, test_user) -> None:
    ac, repo = client
    await repo.create(test_user.id)
    await repo.create(test_user.id)
    other = await repo.create(uuid.uuid4())

    response = await ac.delete("/api/v1/sessions", headers=_HEADERS)
    assert response.status_code == 204
    _, total = await repo.list_by_user(test_user.id, limit=20, offset=0), await repo.count_by_user(test_user.id)
    assert total == 0
    assert await repo.get_by_id(other.id) is not None


async def test_sessions_routes_require_auth(client) -> None:
    ac, _ = client
    app.dependency_overrides.pop(get_current_user, None)

    response = await ac.post("/api/v1/sessions")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"
