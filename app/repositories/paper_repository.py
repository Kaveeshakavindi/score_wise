from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Paper


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
