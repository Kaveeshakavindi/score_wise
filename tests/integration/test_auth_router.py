from __future__ import annotations

import httpx
import pytest

from app.core.deps import get_auth_service, get_redis, get_user_repository
from app.main import app
from app.services.auth_service import AuthService
from tests.fakes import (
    FakeEmailSender,
    FakePasswordResetTokenRepository,
    FakeRedis,
    FakeRefreshTokenRepository,
    FakeUserRepository,
)

_VALID_PAYLOAD = {"name": "Ada Lovelace", "nickname": "ada", "password": "supersecret1", "age": 30, "email": "ada@example.com"}


@pytest.fixture
async def client(settings):
    # Shared fake user store: get_current_user (used by /me) resolves its own
    # UserRepository independently of AuthService, so both must see the same
    # in-memory data for a token issued via /login to validate at /me.
    fake_user_repo = FakeUserRepository()
    fake_email_sender = FakeEmailSender()
    fake_auth_service = AuthService(
        fake_user_repo, FakeRefreshTokenRepository(), FakePasswordResetTokenRepository(), fake_email_sender, settings
    )
    app.dependency_overrides[get_auth_service] = lambda: fake_auth_service
    app.dependency_overrides[get_user_repository] = lambda: fake_user_repo
    app.dependency_overrides[get_redis] = lambda: FakeRedis()

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac, fake_email_sender

    app.dependency_overrides.clear()


async def test_register_then_login_returns_token_pair(client) -> None:
    ac, _ = client
    register_response = await ac.post("/api/v1/auth/register", json=_VALID_PAYLOAD)
    assert register_response.status_code == 201
    body = register_response.json()
    assert body["nickname"] == "ada"
    assert body["email"] == "ada@example.com"
    assert "password" not in body and "password_hash" not in body

    login_response = await ac.post("/api/v1/auth/login", data={"username": "ada", "password": "supersecret1"})
    assert login_response.status_code == 200
    tokens = login_response.json()
    assert tokens["token_type"] == "bearer"
    assert tokens["access_token"]
    assert tokens["refresh_token"]


async def test_register_duplicate_nickname_returns_409_envelope(client) -> None:
    ac, _ = client
    await ac.post("/api/v1/auth/register", json=_VALID_PAYLOAD)
    response = await ac.post("/api/v1/auth/register", json={**_VALID_PAYLOAD, "email": "ada2@example.com"})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


async def test_login_wrong_password_returns_401_envelope(client) -> None:
    ac, _ = client
    await ac.post("/api/v1/auth/register", json=_VALID_PAYLOAD)
    response = await ac.post("/api/v1/auth/login", data={"username": "ada", "password": "wrong"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


async def test_register_invalid_body_returns_422_validation_error(client) -> None:
    ac, _ = client
    response = await ac.post(
        "/api/v1/auth/register",
        json={"name": "Ada", "nickname": "a", "password": "short", "age": 5, "email": "not-an-email"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_me_requires_a_valid_token(client) -> None:
    ac, _ = client
    await ac.post("/api/v1/auth/register", json=_VALID_PAYLOAD)
    login_response = await ac.post("/api/v1/auth/login", data={"username": "ada", "password": "supersecret1"})
    access_token = login_response.json()["access_token"]

    response = await ac.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert response.status_code == 200
    assert response.json()["nickname"] == "ada"
    assert response.json()["email"] == "ada@example.com"


# --- Password reset ------------------------------------------------------


async def test_forgot_password_response_is_identical_for_known_and_unknown_email(client) -> None:
    ac, email_sender = client
    await ac.post("/api/v1/auth/register", json=_VALID_PAYLOAD)

    known = await ac.post("/api/v1/auth/forgot-password", json={"email": "ada@example.com"})
    unknown = await ac.post("/api/v1/auth/forgot-password", json={"email": "ghost@example.com"})

    assert known.status_code == 200
    assert unknown.status_code == 200
    assert known.json() == unknown.json()
    # ...but only the real account actually got an email.
    assert len(email_sender.sent) == 1
    assert email_sender.sent[0][0] == "ada@example.com"


async def test_full_reset_flow_changes_password_and_revokes_old_sessions(client) -> None:
    ac, email_sender = client
    await ac.post("/api/v1/auth/register", json=_VALID_PAYLOAD)
    old_login = await ac.post("/api/v1/auth/login", data={"username": "ada", "password": "supersecret1"})
    old_refresh_token = old_login.json()["refresh_token"]

    await ac.post("/api/v1/auth/forgot-password", json={"email": "ada@example.com"})
    _, reset_url = email_sender.sent[0]
    token = reset_url.split("token=")[1]

    reset_response = await ac.post(
        "/api/v1/auth/reset-password", json={"token": token, "new_password": "newpassword456"}
    )
    assert reset_response.status_code == 204

    old_password_login = await ac.post("/api/v1/auth/login", data={"username": "ada", "password": "supersecret1"})
    assert old_password_login.status_code == 401

    new_password_login = await ac.post("/api/v1/auth/login", data={"username": "ada", "password": "newpassword456"})
    assert new_password_login.status_code == 200

    old_refresh_response = await ac.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh_token})
    assert old_refresh_response.status_code == 401


async def test_reset_password_invalid_token_returns_401_envelope(client) -> None:
    ac, _ = client
    response = await ac.post(
        "/api/v1/auth/reset-password", json={"token": "bogus", "new_password": "newpassword456"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"
