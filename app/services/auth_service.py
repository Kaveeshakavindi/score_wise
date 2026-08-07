from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.core.config import Settings
from app.core.exceptions import ConflictError, NotFoundError, UnauthorizedError
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.db.models import User
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository


@dataclass(frozen=True)
class TokenPairResult:
    access_token: str
    refresh_token: str
    expires_in: int


class AuthService:
    def __init__(
        self, user_repo: UserRepository, refresh_token_repo: RefreshTokenRepository, settings: Settings
    ) -> None:
        self._users = user_repo
        self._refresh_tokens = refresh_token_repo
        self._settings = settings

    async def register(self, *, name: str, nickname: str, password: str, age: int) -> User:
        if await self._users.exists_by_nickname(nickname):
            raise ConflictError(f"Nickname '{nickname}' is already taken.")
        return await self._users.create(
            name=name, nickname=nickname, password_hash=hash_password(password), age=age
        )

    async def login(self, *, nickname: str, password: str) -> TokenPairResult:
        user = await self._users.get_by_nickname(nickname)
        if user is None or not verify_password(password, user.password_hash):
            raise UnauthorizedError("Invalid nickname or password.")
        return await self._issue_token_pair(user)

    async def refresh(self, *, refresh_token: str) -> TokenPairResult:
        token_hash = hash_refresh_token(refresh_token)
        stored = await self._refresh_tokens.get_by_hash(token_hash)
        now = datetime.now(timezone.utc)

        if stored is None:
            raise UnauthorizedError("Invalid refresh token.")
        if stored.revoked_at is not None:
            # Reuse of an already-rotated token indicates possible theft;
            # revoke the whole family defensively (§5).
            await self._refresh_tokens.revoke_all_for_user(stored.user_id, now)
            raise UnauthorizedError("Refresh token has been revoked.")
        if stored.expires_at.replace(tzinfo=timezone.utc) < now:
            raise UnauthorizedError("Refresh token has expired.")

        user = await self._users.get_by_id(stored.user_id)
        if user is None:
            raise UnauthorizedError("Invalid refresh token.")

        await self._refresh_tokens.revoke(stored.id, now)
        return await self._issue_token_pair(user)

    async def logout(self, *, refresh_token: str) -> None:
        token_hash = hash_refresh_token(refresh_token)
        stored = await self._refresh_tokens.get_by_hash(token_hash)
        if stored is not None and stored.revoked_at is None:
            await self._refresh_tokens.revoke(stored.id, datetime.now(timezone.utc))

    async def get_user(self, user_id: uuid.UUID) -> User:
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise NotFoundError(f"User {user_id} was not found.")
        return user

    async def _issue_token_pair(self, user: User) -> TokenPairResult:
        access_token, expires_in = create_access_token(str(user.id), user.nickname, self._settings)

        refresh_token = generate_refresh_token()
        expires_at = datetime.now(timezone.utc) + timedelta(days=self._settings.refresh_token_expire_days)
        await self._refresh_tokens.create(user.id, hash_refresh_token(refresh_token), expires_at)

        return TokenPairResult(access_token=access_token, refresh_token=refresh_token, expires_in=expires_in)
