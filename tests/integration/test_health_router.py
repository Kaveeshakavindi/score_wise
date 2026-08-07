from __future__ import annotations

import httpx
import pytest

from app.main import app


@pytest.fixture
async def client():
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


async def test_healthz_is_unauthenticated_and_ok(client: httpx.AsyncClient) -> None:
    response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_readyz_reports_status_without_auth(client: httpx.AsyncClient) -> None:
    response = await client.get("/readyz")
    # No live Postgres/Anthropic credentials in the test environment, so this
    # may legitimately come back 503 — the point is it never requires auth
    # and always returns the documented envelope shape (§6.1).
    assert response.status_code in (200, 503)
    body = response.json()
    assert body["status"] == "ready"
    assert set(body["checks"]) == {"db", "llm"}


async def test_version_is_unauthenticated(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/version")
    assert response.status_code == 200
    assert response.json()["api_version"] == "1.0.0"


async def test_protected_route_without_token_returns_error_envelope(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/sessions")
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "unauthorized"
    assert "request_id" in body["error"]
