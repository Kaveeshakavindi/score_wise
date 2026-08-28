from __future__ import annotations

import pytest

from app.core.exceptions import ConflictError, UnauthorizedError
from app.services.auth_service import AuthService
from tests.fakes import (
    FakeEmailSender,
    FakePasswordResetTokenRepository,
    FakeRefreshTokenRepository,
    FakeUserRepository,
)


@pytest.fixture
def email_sender() -> FakeEmailSender:
    return FakeEmailSender()


@pytest.fixture
def auth_service(settings, email_sender: FakeEmailSender) -> AuthService:
    return AuthService(
        FakeUserRepository(), FakeRefreshTokenRepository(), FakePasswordResetTokenRepository(), email_sender, settings
    )


async def test_register_creates_user(auth_service: AuthService) -> None:
    user = await auth_service.register(name="Ada", nickname="ada", password="password123", age=30, email="ada@example.com")
    assert user.nickname == "ada"
    assert user.email == "ada@example.com"
    assert user.password_hash != "password123"


async def test_register_lowercases_email(auth_service: AuthService) -> None:
    user = await auth_service.register(name="Ada", nickname="ada", password="password123", age=30, email="Ada@Example.COM")
    assert user.email == "ada@example.com"


async def test_register_duplicate_nickname_raises_conflict(auth_service: AuthService) -> None:
    await auth_service.register(name="Ada", nickname="ada", password="password123", age=30, email="ada@example.com")
    with pytest.raises(ConflictError):
        await auth_service.register(name="Ada2", nickname="ada", password="password456", age=31, email="ada2@example.com")


async def test_login_success_issues_token_pair(auth_service: AuthService) -> None:
    await auth_service.register(name="Ada", nickname="ada", password="password123", age=30, email="ada@example.com")
    result = await auth_service.login(nickname="ada", password="password123")
    assert result.access_token
    assert result.refresh_token
    assert result.expires_in > 0


async def test_login_wrong_password_raises_unauthorized(auth_service: AuthService) -> None:
    await auth_service.register(name="Ada", nickname="ada", password="password123", age=30, email="ada@example.com")
    with pytest.raises(UnauthorizedError):
        await auth_service.login(nickname="ada", password="wrong-password")


async def test_login_unknown_nickname_raises_unauthorized(auth_service: AuthService) -> None:
    with pytest.raises(UnauthorizedError):
        await auth_service.login(nickname="ghost", password="whatever123")


async def test_refresh_rotates_token(auth_service: AuthService) -> None:
    await auth_service.register(name="Ada", nickname="ada", password="password123", age=30, email="ada@example.com")
    first = await auth_service.login(nickname="ada", password="password123")

    rotated = await auth_service.refresh(refresh_token=first.refresh_token)
    assert rotated.refresh_token != first.refresh_token


async def test_refresh_replay_of_rotated_token_is_rejected(auth_service: AuthService) -> None:
    await auth_service.register(name="Ada", nickname="ada", password="password123", age=30, email="ada@example.com")
    first = await auth_service.login(nickname="ada", password="password123")
    await auth_service.refresh(refresh_token=first.refresh_token)

    # Reusing the already-rotated (now-revoked) refresh token must fail —
    # detects theft/replay (§5).
    with pytest.raises(UnauthorizedError):
        await auth_service.refresh(refresh_token=first.refresh_token)


async def test_logout_revokes_refresh_token(auth_service: AuthService) -> None:
    await auth_service.register(name="Ada", nickname="ada", password="password123", age=30, email="ada@example.com")
    tokens = await auth_service.login(nickname="ada", password="password123")

    await auth_service.logout(refresh_token=tokens.refresh_token)

    with pytest.raises(UnauthorizedError):
        await auth_service.refresh(refresh_token=tokens.refresh_token)


# --- Password reset ------------------------------------------------------


async def test_request_password_reset_sends_email_for_known_address(
    auth_service: AuthService, email_sender: FakeEmailSender
) -> None:
    await auth_service.register(name="Ada", nickname="ada", password="password123", age=30, email="ada@example.com")

    await auth_service.request_password_reset(email="ada@example.com")

    assert len(email_sender.sent) == 1
    to, reset_url = email_sender.sent[0]
    assert to == "ada@example.com"
    assert "/reset-password?token=" in reset_url


async def test_request_password_reset_matches_email_case_insensitively(
    auth_service: AuthService, email_sender: FakeEmailSender
) -> None:
    await auth_service.register(name="Ada", nickname="ada", password="password123", age=30, email="ada@example.com")

    await auth_service.request_password_reset(email="ADA@EXAMPLE.COM")

    assert len(email_sender.sent) == 1


async def test_request_password_reset_unknown_email_sends_nothing_and_does_not_raise(
    auth_service: AuthService, email_sender: FakeEmailSender
) -> None:
    # Anti-enumeration: no exception, no email sent, silently no-ops.
    await auth_service.request_password_reset(email="ghost@example.com")
    assert email_sender.sent == []


async def test_request_password_reset_swallows_email_send_failure(
    auth_service: AuthService, email_sender: FakeEmailSender
) -> None:
    await auth_service.register(name="Ada", nickname="ada", password="password123", age=30, email="ada@example.com")
    email_sender.fail_next = True

    # Must not propagate — a send failure must never surface differently than
    # the "email not found" case, or the response becomes an enumeration oracle.
    await auth_service.request_password_reset(email="ada@example.com")


async def test_reset_password_with_valid_token_changes_password_and_revokes_sessions(
    auth_service: AuthService, email_sender: FakeEmailSender
) -> None:
    await auth_service.register(name="Ada", nickname="ada", password="password123", age=30, email="ada@example.com")
    old_tokens = await auth_service.login(nickname="ada", password="password123")

    await auth_service.request_password_reset(email="ada@example.com")
    _, reset_url = email_sender.sent[0]
    token = reset_url.split("token=")[1]

    await auth_service.reset_password(token=token, new_password="newpassword456")

    # Old password no longer works, new one does.
    with pytest.raises(UnauthorizedError):
        await auth_service.login(nickname="ada", password="password123")
    result = await auth_service.login(nickname="ada", password="newpassword456")
    assert result.access_token

    # Every refresh token issued before the reset is revoked.
    with pytest.raises(UnauthorizedError):
        await auth_service.refresh(refresh_token=old_tokens.refresh_token)


async def test_reset_password_token_is_single_use(auth_service: AuthService, email_sender: FakeEmailSender) -> None:
    await auth_service.register(name="Ada", nickname="ada", password="password123", age=30, email="ada@example.com")
    await auth_service.request_password_reset(email="ada@example.com")
    _, reset_url = email_sender.sent[0]
    token = reset_url.split("token=")[1]

    await auth_service.reset_password(token=token, new_password="newpassword456")

    with pytest.raises(UnauthorizedError):
        await auth_service.reset_password(token=token, new_password="anotherpassword789")


async def test_reset_password_unknown_token_raises_unauthorized(auth_service: AuthService) -> None:
    with pytest.raises(UnauthorizedError):
        await auth_service.reset_password(token="not-a-real-token", new_password="newpassword456")
