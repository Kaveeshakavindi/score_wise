from __future__ import annotations

import pytest

from app.core.exceptions import ConflictError, UnauthorizedError
from app.services.auth_service import AuthService
from tests.fakes import FakeRefreshTokenRepository, FakeUserRepository


@pytest.fixture
def auth_service(settings) -> AuthService:
    return AuthService(FakeUserRepository(), FakeRefreshTokenRepository(), settings)


async def test_register_creates_user(auth_service: AuthService) -> None:
    user = await auth_service.register(name="Ada", nickname="ada", password="password123", age=30)
    assert user.nickname == "ada"
    assert user.password_hash != "password123"


async def test_register_duplicate_nickname_raises_conflict(auth_service: AuthService) -> None:
    await auth_service.register(name="Ada", nickname="ada", password="password123", age=30)
    with pytest.raises(ConflictError):
        await auth_service.register(name="Ada2", nickname="ada", password="password456", age=31)


async def test_login_success_issues_token_pair(auth_service: AuthService) -> None:
    await auth_service.register(name="Ada", nickname="ada", password="password123", age=30)
    result = await auth_service.login(nickname="ada", password="password123")
    assert result.access_token
    assert result.refresh_token
    assert result.expires_in > 0


async def test_login_wrong_password_raises_unauthorized(auth_service: AuthService) -> None:
    await auth_service.register(name="Ada", nickname="ada", password="password123", age=30)
    with pytest.raises(UnauthorizedError):
        await auth_service.login(nickname="ada", password="wrong-password")


async def test_login_unknown_nickname_raises_unauthorized(auth_service: AuthService) -> None:
    with pytest.raises(UnauthorizedError):
        await auth_service.login(nickname="ghost", password="whatever123")


async def test_refresh_rotates_token(auth_service: AuthService) -> None:
    await auth_service.register(name="Ada", nickname="ada", password="password123", age=30)
    first = await auth_service.login(nickname="ada", password="password123")

    rotated = await auth_service.refresh(refresh_token=first.refresh_token)
    assert rotated.refresh_token != first.refresh_token


async def test_refresh_replay_of_rotated_token_is_rejected(auth_service: AuthService) -> None:
    await auth_service.register(name="Ada", nickname="ada", password="password123", age=30)
    first = await auth_service.login(nickname="ada", password="password123")
    await auth_service.refresh(refresh_token=first.refresh_token)

    # Reusing the already-rotated (now-revoked) refresh token must fail —
    # detects theft/replay (§5).
    with pytest.raises(UnauthorizedError):
        await auth_service.refresh(refresh_token=first.refresh_token)


async def test_logout_revokes_refresh_token(auth_service: AuthService) -> None:
    await auth_service.register(name="Ada", nickname="ada", password="password123", age=30)
    tokens = await auth_service.login(nickname="ada", password="password123")

    await auth_service.logout(refresh_token=tokens.refresh_token)

    with pytest.raises(UnauthorizedError):
        await auth_service.refresh(refresh_token=tokens.refresh_token)
