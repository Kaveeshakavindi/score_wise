from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import PasswordResetToken


class PasswordResetTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, user_id: uuid.UUID, token_hash: str, expires_at: datetime) -> PasswordResetToken:
        token = PasswordResetToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
        self._session.add(token)
        await self._session.flush()
        return token

    async def get_by_hash(self, token_hash: str) -> PasswordResetToken | None:
        result = await self._session.execute(
            select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def mark_used(self, token_id: uuid.UUID, used_at: datetime) -> None:
        await self._session.execute(
            update(PasswordResetToken).where(PasswordResetToken.id == token_id).values(used_at=used_at)
        )
