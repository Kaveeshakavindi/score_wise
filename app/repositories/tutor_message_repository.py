from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import TutorMessage


class TutorMessageRepository:
    """Threaded by (question_id, user_id) — one implicit tutor thread per
    student per question, no separate session concept (see TutorMessage)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        question_id: uuid.UUID,
        user_id: uuid.UUID,
        role: str,
        content: str,
        citations: list[dict] | None = None,
    ) -> TutorMessage:
        message = TutorMessage(
            question_id=question_id, user_id=user_id, role=role, content=content, citations=citations
        )
        self._session.add(message)
        await self._session.flush()
        return message

    async def history(self, *, question_id: uuid.UUID, user_id: uuid.UUID) -> list[TutorMessage]:
        result = await self._session.execute(
            select(TutorMessage)
            .where(TutorMessage.question_id == question_id, TutorMessage.user_id == user_id)
            .order_by(TutorMessage.created_at.asc())
        )
        return list(result.scalars().all())
