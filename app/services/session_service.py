from __future__ import annotations

import uuid

from app.core.exceptions import NotFoundError
from app.db.models import ChatSession
from app.repositories.session_repository import SessionRepository


class SessionService:
    def __init__(self, repo: SessionRepository) -> None:
        self._repo = repo

    async def create(self, user_id: uuid.UUID) -> ChatSession:
        return await self._repo.create(user_id)

    async def list_for_user(self, user_id: uuid.UUID, *, limit: int, offset: int) -> tuple[list[ChatSession], int]:
        items = await self._repo.list_by_user(user_id, limit=limit, offset=offset)
        total = await self._repo.count_by_user(user_id)
        return items, total

    async def get_owned(self, user_id: uuid.UUID, session_id: uuid.UUID) -> ChatSession:
        """Every session-scoped read/write verifies ownership first, returning
        404 (not 403) on mismatch to avoid confirming resource existence to
        non-owners (§5)."""
        session = await self._repo.get_by_id(session_id)
        if session is None or session.user_id != user_id:
            raise NotFoundError(f"Session {session_id} was not found.")
        return session

    async def rename(self, user_id: uuid.UUID, session_id: uuid.UUID, title: str) -> ChatSession:
        session = await self.get_owned(user_id, session_id)
        await self._repo.set_title(session_id, title)
        session.title = title
        return session

    async def delete(self, user_id: uuid.UUID, session_id: uuid.UUID) -> None:
        await self.get_owned(user_id, session_id)
        await self._repo.delete(session_id)

    async def delete_all(self, user_id: uuid.UUID) -> None:
        await self._repo.delete_all_for_user(user_id)
