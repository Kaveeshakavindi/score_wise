from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Attempt, AttemptAnswer, Paper


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

    # --- Dashboard reads (DashboardService) -----------------------------

    async def list_recent_with_paper(self, user_id: uuid.UUID, *, limit: int) -> list[tuple[Attempt, Paper]]:
        """Newest-first attempts with their paper (for subject/year), reusing
        idx_attempts_user_created. DashboardService reverses this to
        chronological order for the trend chart."""
        result = await self._session.execute(
            select(Attempt, Paper)
            .join(Paper, Paper.id == Attempt.paper_id)
            .where(Attempt.user_id == user_id)
            .order_by(Attempt.created_at.desc())
            .limit(limit)
        )
        return [(attempt, paper) for attempt, paper in result.all()]

    async def count_by_user(self, user_id: uuid.UUID) -> int:
        result = await self._session.execute(
            select(func.count()).select_from(Attempt).where(Attempt.user_id == user_id)
        )
        return int(result.scalar_one())

    async def subject_accuracy_by_user(self, user_id: uuid.UUID) -> list[tuple[str, int, int]]:
        """(subject, correct, total) per subject, aggregated over every answer
        the user has ever submitted. `is_correct` is already computed and
        stored per answer at submit time (AttemptService.submit), so this
        never needs Question — just AttemptAnswer -> Attempt -> Paper for the
        subject label."""
        result = await self._session.execute(
            select(
                Paper.subject,
                func.count().filter(AttemptAnswer.is_correct.is_(True)).label("correct"),
                func.count().label("total"),
            )
            .select_from(AttemptAnswer)
            .join(Attempt, Attempt.id == AttemptAnswer.attempt_id)
            .join(Paper, Paper.id == Attempt.paper_id)
            .where(Attempt.user_id == user_id)
            .group_by(Paper.subject)
        )
        return [(row.subject, row.correct, row.total) for row in result.all()]

    async def wrong_question_ids_by_user(self, user_id: uuid.UUID) -> list[uuid.UUID]:
        """The question_id of every wrong AttemptAnswer for this user (one
        entry per wrong answer, not deduplicated). Used by DashboardService's
        follow-through-rate calculation, which needs every wrong answer's
        question_id but none of Question's other columns, so this skips that
        join entirely."""
        result = await self._session.execute(
            select(AttemptAnswer.question_id)
            .join(Attempt, Attempt.id == AttemptAnswer.attempt_id)
            .where(Attempt.user_id == user_id, AttemptAnswer.is_correct.is_(False))
        )
        return list(result.scalars().all())
