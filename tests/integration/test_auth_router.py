from __future__ import annotations

import httpx
import pytest

from app.core.deps import get_auth_service, get_redis, get_user_repository
from app.main import app
from app.services.auth_service import AuthService
from tests.fakes import FakeRedis, FakeRefreshTokenRepository, FakeUserRepository


@pytest.fixture
async def client(settings):
    # Shared fake user store: get_current_user (used by /me) resolves its own
    # UserRepository independently of AuthService, so both must see the same
    # in-memory data for a token issued via /login to validate at /me.
    fake_user_repo = FakeUserRepository()
    fake_auth_service = AuthService(fake_user_repo, FakeRefreshTokenRepository(), settings)
    app.dependency_overrides[get_auth_service] = lambda: fake_auth_service
    app.dependency_overrides[get_user_repository] = lambda: fake_user_repo
    app.dependency_overrides[get_redis] = lambda: FakeRedis()

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

    app.dependency_overrides.clear()


async def test_register_then_login_returns_token_pair(client: httpx.AsyncClient) -> None:
    register_response = await client.post(
        "/api/v1/auth/register",
        json={"name": "Ada Lovelace", "nickname": "ada", "password": "supersecret1", "age": 30},
    )
    assert register_response.status_code == 201
    body = register_response.json()
    assert body["nickname"] == "ada"
    assert "password" not in body and "password_hash" not in body

    login_response = await client.post(
        "/api/v1/auth/login", data={"username": "ada", "password": "supersecret1"}
    )
    assert login_response.status_code == 200
    tokens = login_response.json()
    assert tokens["token_type"] == "bearer"
    assert tokens["access_token"]
    assert tokens["refresh_token"]


async def test_register_duplicate_nickname_returns_409_envelope(client: httpx.AsyncClient) -> None:
    payload = {"name": "Ada", "nickname": "ada", "password": "supersecret1", "age": 30}
    await client.post("/api/v1/auth/register", json=payload)
    response = await client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


async def test_login_wrong_password_returns_401_envelope(client: httpx.AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={"name": "Ada", "nickname": "ada", "password": "supersecret1", "age": 30},
    )
    response = await client.post("/api/v1/auth/login", data={"username": "ada", "password": "wrong"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


async def test_register_invalid_body_returns_422_validation_error(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={"name": "Ada", "nickname": "a", "password": "short", "age": 5},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_me_requires_a_valid_token(client: httpx.AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={"name": "Ada", "nickname": "ada", "password": "supersecret1", "age": 30},
    )
    login_response = await client.post(
        "/api/v1/auth/login", data={"username": "ada", "password": "supersecret1"}
    )
    access_token = login_response.json()["access_token"]

    response = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert response.status_code == 200
    assert response.json()["nickname"] == "ada"
