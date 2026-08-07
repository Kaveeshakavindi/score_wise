from __future__ import annotations

import httpx
import pytest

from app.core.deps import get_current_user, get_redis
from app.main import app
from tests.fakes import FakeRedis

_HEADERS = {"Authorization": "Bearer test-token"}


@pytest.fixture
async def client(test_user):
    app.dependency_overrides[get_current_user] = lambda: test_user
    app.dependency_overrides[get_redis] = lambda: FakeRedis()

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

    app.dependency_overrides.clear()


async def test_list_tools_requires_auth() -> None:
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/api/v1/tools")
    assert response.status_code == 401


async def test_list_tools_returns_all_definitions_with_json_schema(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/tools", headers=_HEADERS)
    assert response.status_code == 200
    body = response.json()

    names = {tool["name"] for tool in body}
    assert names == {"get_current_time", "read_file", "fetch_url", "read_url"}
    for tool in body:
        assert tool["description"]
        assert tool["parameters"]["type"] == "object"


async def test_list_tools_does_not_expose_a_direct_invoke_route(client: httpx.AsyncClient) -> None:
    # §6.6 explicit non-goal: tools are introspection-only, never directly
    # invocable by an API client.
    response = await client.post("/api/v1/tools/get_current_time/invoke", headers=_HEADERS)
    assert response.status_code == 404
