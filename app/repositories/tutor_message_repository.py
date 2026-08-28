from __future__ import annotations

import uuid

from sqlalchemy import column, func, select, true
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import TutorMessage


class TutorMessageRepository:
    """At most one feedback row per (question_id, user_id, selected_answer) —
    see TutorMessage. `history()` and the dashboard reads below still operate
    over a list, both for compatibility with the handful of pre-redesign rows
    that predate this invariant, and because a student can now legitimately
    accumulate more than one row per question (one per distinct answer
    they've had feedback generated for, e.g. across retakes)."""

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
        selected_answer: int | None = None,
        is_correct: bool | None = None,
    ) -> TutorMessage:
        message = TutorMessage(
            question_id=question_id,
            user_id=user_id,
            role=role,
            content=content,
            citations=citations,
            selected_answer=selected_answer,
            is_correct=is_correct,
        )
        self._session.add(message)
        await self._session.flush()
        return message

    async def history(self, *, question_id: uuid.UUID, user_id: uuid.UUID) -> list[TutorMessage]:
        """The feedback message(s) for this (question, user) — used only for
        display (the dashboard's "Tutor helped with" detail view). Scoped to
        role="assistant" so a student with legacy role="user" rows from the
        pre-redesign free-form chat never has their own old question
        rendered back to them as if it were the tutor's feedback."""
        result = await self._session.execute(
            select(TutorMessage)
            .where(
                TutorMessage.question_id == question_id,
                TutorMessage.user_id == user_id,
                TutorMessage.role == "assistant",
            )
            .order_by(TutorMessage.created_at.asc())
        )
        return list(result.scalars().all())

    async def get_one(
        self, *, question_id: uuid.UUID, user_id: uuid.UUID, selected_answer: int | None = None
    ) -> TutorMessage | None:
        """The cached feedback for this (question, user, selected_answer), if
        it's already been generated — lets generate_feedback skip the LLM
        call entirely when asked again about the exact same answer, while
        still generating fresh feedback whenever the current selected_answer
        differs from what's cached (e.g. a retake where the student picked
        something else). Scoped to role="assistant" and is_correct IS NOT
        NULL so it only ever matches a genuine structured feedback row: a
        student who used the old free-form chat before this redesign may
        have legacy role="user" rows (or unstructured role="assistant"
        replies with no is_correct) sitting in this same thread, and
        surfacing those as "the cached feedback" would show a stale chat
        message — or the student's own question — as if it were the tutor's
        answer."""
        result = await self._session.execute(
            select(TutorMessage)
            .where(
                TutorMessage.question_id == question_id,
                TutorMessage.user_id == user_id,
                TutorMessage.role == "assistant",
                TutorMessage.is_correct.is_not(None),
                TutorMessage.selected_answer.is_(selected_answer)
                if selected_answer is None
                else TutorMessage.selected_answer == selected_answer,
            )
            .order_by(TutorMessage.created_at.desc())
            .limit(1)
        )
        return result.scalars().first()

    # --- Dashboard reads (DashboardService) -----------------------------

    async def reviewed_question_ids(self, user_id: uuid.UUID, question_ids: list[uuid.UUID]) -> set[uuid.UUID]:
        """Which of these question_ids has at least one tutor message from
        this user — one batch query instead of one per row, for annotating a
        wrong-answer list with a reviewed/not-reviewed flag."""
        if not question_ids:
            return set()
        result = await self._session.execute(
            select(TutorMessage.question_id)
            .where(TutorMessage.user_id == user_id, TutorMessage.question_id.in_(question_ids))
            .distinct()
        )
        return set(result.scalars().all())

    async def count_threaded_questions_by_user(self, user_id: uuid.UUID) -> int:
        """Distinct questions this user has ever viewed feedback for
        (correct or wrong) — the total behind list_tutor_history's
        pagination. Not the same as the dashboard summary's
        tutor_helped_count, which DashboardService scopes to mistakes only."""
        result = await self._session.execute(
            select(func.count(func.distinct(TutorMessage.question_id))).where(TutorMessage.user_id == user_id)
        )
        return int(result.scalar_one())

    async def list_threaded_question_ids_by_user(
        self, user_id: uuid.UUID, *, limit: int, offset: int
    ) -> list[uuid.UUID]:
        """Question ids this user has discussed with the tutor, most
        recently-discussed first — one row per question regardless of how
        many messages that thread has."""
        result = await self._session.execute(
            select(TutorMessage.question_id)
            .where(TutorMessage.user_id == user_id)
            .group_by(TutorMessage.question_id)
            .order_by(func.max(TutorMessage.created_at).desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def top_cited_topics_by_user(self, user_id: uuid.UUID, *, limit: int = 5) -> list[tuple[str, int]]:
        """Ranks syllabus topics by how often they appear in this user's
        tutor citations, scoped to feedback on mistakes (is_correct=False) —
        a topic cited on a question the student already got right isn't a
        weak area. Unnests the `citations` JSONB array (one row per message)
        via a LATERAL jsonb_array_elements and groups on the ->>'topic' text."""
        citation = func.jsonb_array_elements(TutorMessage.citations).table_valued(column("value", JSONB)).lateral()
        topic = citation.c.value["topic"].astext

        result = await self._session.execute(
            select(topic.label("topic"), func.count().label("count"))
            .select_from(TutorMessage)
            .join(citation, true())
            .where(
                TutorMessage.user_id == user_id,
                TutorMessage.role == "assistant",
                TutorMessage.is_correct.is_(False),
                TutorMessage.citations.is_not(None),
            )
            .group_by(topic)
            .having(topic.is_not(None))
            .order_by(func.count().desc())
            .limit(limit)
        )
        return [(row.topic, row.count) for row in result.all()]
