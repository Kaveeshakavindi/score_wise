from __future__ import annotations

import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, *, name: str, nickname: str, password_hash: str, age: int, email: str) -> User:
        user = User(name=name, nickname=nickname, password_hash=password_hash, age=age, email=email)
        self._session.add(user)
        await self._session.flush()
        return user

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return await self._session.get(User, user_id)

    async def get_by_nickname(self, nickname: str) -> User | None:
        result = await self._session.execute(select(User).where(User.nickname == nickname))
        return result.scalar_one_or_none()

    async def exists_by_nickname(self, nickname: str) -> bool:
        result = await self._session.execute(select(User.id).where(User.nickname == nickname))
        return result.scalar_one_or_none() is not None

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def update_password(self, user_id: uuid.UUID, password_hash: str) -> None:
        await self._session.execute(update(User).where(User.id == user_id).values(password_hash=password_hash))
