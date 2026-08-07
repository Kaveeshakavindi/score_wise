from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Message


class MessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, session_id: uuid.UUID, role: str, content: str) -> Message:
        message = Message(session_id=session_id, role=role, content=content)
        self._session.add(message)
        await self._session.flush()
        return message

    async def list_by_session(self, session_id: uuid.UUID, *, limit: int, offset: int) -> list[Message]:
        result = await self._session.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def count_by_session(self, session_id: uuid.UUID) -> int:
        result = await self._session.execute(
            select(func.count()).select_from(Message).where(Message.session_id == session_id)
        )
        return int(result.scalar_one())

    async def history(self, session_id: uuid.UUID) -> list[Message]:
        """Full history oldest -> newest, used to build the LLM prompt."""
        result = await self._session.execute(
            select(Message).where(Message.session_id == session_id).order_by(Message.created_at.asc())
        )
        return list(result.scalars().all())
