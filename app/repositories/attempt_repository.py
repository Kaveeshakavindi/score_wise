from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Attempt, AttemptAnswer


class AttemptRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, *, user_id: uuid.UUID, paper_id: uuid.UUID, score: int, total: int) -> Attempt:
        attempt = Attempt(user_id=user_id, paper_id=paper_id, score=score, total=total)
        self._session.add(attempt)
        await self._session.flush()
        return attempt

    async def add_answer(
        self, *, attempt_id: uuid.UUID, question_id: uuid.UUID, selected_answer: int | None, is_correct: bool
    ) -> AttemptAnswer:
        answer = AttemptAnswer(
            attempt_id=attempt_id,
            question_id=question_id,
            selected_answer=selected_answer,
            is_correct=is_correct,
        )
        self._session.add(answer)
        await self._session.flush()
        return answer
