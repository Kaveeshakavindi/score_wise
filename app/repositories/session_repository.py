from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChatSession


class SessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, user_id: uuid.UUID) -> ChatSession:
        chat_session = ChatSession(user_id=user_id)
        self._session.add(chat_session)
        await self._session.flush()
        return chat_session

    async def get_by_id(self, session_id: uuid.UUID) -> ChatSession | None:
        return await self._session.get(ChatSession, session_id)

    async def list_by_user(self, user_id: uuid.UUID, *, limit: int, offset: int) -> list[ChatSession]:
        result = await self._session.execute(
            select(ChatSession)
            .where(ChatSession.user_id == user_id)
            .order_by(ChatSession.last_active.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def count_by_user(self, user_id: uuid.UUID) -> int:
        result = await self._session.execute(
            select(func.count()).select_from(ChatSession).where(ChatSession.user_id == user_id)
        )
        return int(result.scalar_one())

    async def set_title(self, session_id: uuid.UUID, title: str) -> None:
        """Unconditional rename, used by PATCH /sessions/{id}."""
        chat_session = await self._session.get(ChatSession, session_id)
        if chat_session is not None:
            chat_session.title = title

    async def set_title_if_null(self, session_id: uuid.UUID, title: str) -> None:
        """Mirrors the CLI's set_session_title: only fills the title once,
        after the first turn (chatbot/db/sessions.py)."""
        if not title:
            return
        chat_session = await self._session.get(ChatSession, session_id)
        if chat_session is not None and chat_session.title is None:
            chat_session.title = title

    async def touch(self, session_id: uuid.UUID) -> None:
        chat_session = await self._session.get(ChatSession, session_id)
        if chat_session is not None:
            chat_session.last_active = datetime.now(timezone.utc)

    async def delete(self, session_id: uuid.UUID) -> None:
        await self._session.execute(delete(ChatSession).where(ChatSession.id == session_id))

    async def delete_all_for_user(self, user_id: uuid.UUID) -> None:
        await self._session.execute(delete(ChatSession).where(ChatSession.user_id == user_id))
