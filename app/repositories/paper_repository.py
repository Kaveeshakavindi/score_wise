from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Paper, Question


class PaperRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_by_subject(self, subject: str | None, *, limit: int, offset: int) -> list[Paper]:
        stmt = select(Paper).order_by(Paper.year.desc())
        if subject:
            stmt = stmt.where(Paper.subject == subject)
        result = await self._session.execute(stmt.limit(limit).offset(offset))
        return list(result.scalars().all())

    async def count_by_subject(self, subject: str | None) -> int:
        stmt = select(func.count()).select_from(Paper)
        if subject:
            stmt = stmt.where(Paper.subject == subject)
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def get_by_id(self, paper_id: uuid.UUID) -> Paper | None:
        return await self._session.get(Paper, paper_id)

    async def count_questions_by_paper_ids(self, paper_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
        """Batched question count per paper, for a page of list_by_subject
        results — one query regardless of how many papers are on the page,
        never N+1 (mirrors QuestionRepository.get_many_by_ids's batching)."""
        if not paper_ids:
            return {}
        result = await self._session.execute(
            select(Question.paper_id, func.count())
            .where(Question.paper_id.in_(paper_ids))
            .group_by(Question.paper_id)
        )
        return {paper_id: count for paper_id, count in result.all()}
