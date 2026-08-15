from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Question


class QuestionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_by_paper(self, paper_id: uuid.UUID, *, limit: int, offset: int) -> list[Question]:
        result = await self._session.execute(
            select(Question)
            .where(Question.paper_id == paper_id)
            .order_by(Question.question_number.asc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def count_by_paper(self, paper_id: uuid.UUID) -> int:
        result = await self._session.execute(
            select(func.count()).select_from(Question).where(Question.paper_id == paper_id)
        )
        return int(result.scalar_one())

    async def get_by_id(self, question_id: uuid.UUID) -> Question | None:
        return await self._session.get(Question, question_id)

    async def get_many_by_ids(self, question_ids: list[uuid.UUID]) -> dict[uuid.UUID, Question]:
        """Used by AttemptService to validate+score a whole submitted answers
        array in one round trip rather than N sequential lookups."""
        if not question_ids:
            return {}
        result = await self._session.execute(select(Question).where(Question.id.in_(question_ids)))
        return {q.id: q for q in result.scalars().all()}
