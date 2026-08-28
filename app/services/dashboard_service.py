from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from app.db.models import TutorMessage
from app.repositories.attempt_repository import AttemptRepository
from app.repositories.question_repository import QuestionRepository
from app.repositories.tutor_message_repository import TutorMessageRepository

DEFAULT_TREND_ATTEMPTS = 12
DEFAULT_TOP_TOPICS = 5


@dataclass(frozen=True)
class SubjectAccuracy:
    subject: str
    correct: int
    total: int


@dataclass(frozen=True)
class TrendPoint:
    attempt_id: uuid.UUID
    paper_id: uuid.UUID
    subject: str
    year: int
    score: int
    total: int
    created_at: datetime


@dataclass(frozen=True)
class TopicCount:
    topic: str
    count: int


@dataclass(frozen=True)
class DashboardSummary:
    overall_correct: int
    overall_total: int
    attempts_count: int
    subjects: list[SubjectAccuracy]
    trend: list[TrendPoint]
    mistakes_total: int
    mistakes_unreviewed: int
    follow_through_rate: float
    # Distinct questions ever discussed with the tutor — the dashboard's
    # "Tutor helped with" figure.
    tutor_helped_count: int
    top_topics: list[TopicCount]


@dataclass(frozen=True)
class TutorHelpedQuestion:
    """One question the student has viewed AI tutor feedback for, question
    details plus the saved feedback message(s) — read-only, this is a past
    view, not a live generation (that happens via POST /questions/{id}/tutor,
    same as /exam, but it's idempotent so this is just a cached read).
    `messages` are the ORM rows directly, the router validates them into
    TutorMessageOut itself."""

    question_id: uuid.UUID
    subject: str
    year: int
    question_number: int
    question_text: str
    last_discussed_at: datetime
    messages: list[TutorMessage]


class DashboardService:
    def __init__(
        self,
        attempt_repo: AttemptRepository,
        tutor_message_repo: TutorMessageRepository,
        question_repo: QuestionRepository,
    ) -> None:
        self._attempts = attempt_repo
        self._tutor_messages = tutor_message_repo
        self._questions = question_repo

    async def get_summary(self, user_id: uuid.UUID) -> DashboardSummary:
        recent = await self._attempts.list_recent_with_paper(user_id, limit=DEFAULT_TREND_ATTEMPTS)
        # list_recent_with_paper is newest-first; the trend chart reads
        # oldest -> newest.
        trend = [
            TrendPoint(
                attempt_id=attempt.id,
                paper_id=attempt.paper_id,
                subject=paper.subject,
                year=paper.year,
                score=attempt.score,
                total=attempt.total,
                created_at=attempt.created_at,
            )
            for attempt, paper in reversed(recent)
        ]

        attempts_count = await self._attempts.count_by_user(user_id)

        subject_rows = await self._attempts.subject_accuracy_by_user(user_id)
        subjects = [SubjectAccuracy(subject=s, correct=c, total=t) for s, c, t in subject_rows]
        overall_correct = sum(c for _, c, _ in subject_rows)
        overall_total = sum(t for _, _, t in subject_rows)

        # Every wrong answer's question_id (not deduplicated — mistakes_total
        # counts wrong-answer instances), checked in one batch against which
        # of those questions have ever been discussed with the tutor, for the
        # follow-through-rate meter.
        wrong_question_ids = await self._attempts.wrong_question_ids_by_user(user_id)
        mistakes_total = len(wrong_question_ids)
        reviewed_ids = await self._tutor_messages.reviewed_question_ids(user_id, list(set(wrong_question_ids)))
        mistakes_unreviewed = sum(1 for qid in wrong_question_ids if qid not in reviewed_ids)
        follow_through_rate = (
            (mistakes_total - mistakes_unreviewed) / mistakes_total if mistakes_total > 0 else 0.0
        )

        # Distinct *mistakes* reviewed, not every question the student has
        # viewed feedback for — reviewed_ids is already scoped to
        # wrong_question_ids above, so a correct-answer feedback view (which
        # every question now gets, not just wrong ones) doesn't inflate this.
        tutor_helped_count = len(reviewed_ids)

        topic_rows = await self._tutor_messages.top_cited_topics_by_user(user_id, limit=DEFAULT_TOP_TOPICS)
        top_topics = [TopicCount(topic=t, count=c) for t, c in topic_rows]

        return DashboardSummary(
            overall_correct=overall_correct,
            overall_total=overall_total,
            attempts_count=attempts_count,
            subjects=subjects,
            trend=trend,
            mistakes_total=mistakes_total,
            mistakes_unreviewed=mistakes_unreviewed,
            follow_through_rate=follow_through_rate,
            tutor_helped_count=tutor_helped_count,
            top_topics=top_topics,
        )

    async def list_tutor_history(
        self, user_id: uuid.UUID, *, limit: int, offset: int
    ) -> tuple[list[TutorHelpedQuestion], int]:
        """Questions the tutor has helped with, most recently discussed
        first, each with its full saved conversation."""
        question_ids = await self._tutor_messages.list_threaded_question_ids_by_user(
            user_id, limit=limit, offset=offset
        )
        total = await self._tutor_messages.count_threaded_questions_by_user(user_id)
        if not question_ids:
            return [], total

        questions_by_id = await self._questions.get_many_by_ids(question_ids)

        results: list[TutorHelpedQuestion] = []
        for question_id in question_ids:
            question = questions_by_id.get(question_id)
            if question is None:
                continue
            messages = await self._tutor_messages.history(question_id=question_id, user_id=user_id)
            last_discussed_at = messages[-1].created_at if messages else question.created_at
            results.append(
                TutorHelpedQuestion(
                    question_id=question_id,
                    subject=question.subject,
                    year=question.year,
                    question_number=question.question_number,
                    question_text=question.question_text,
                    last_discussed_at=last_discussed_at,
                    messages=messages,
                )
            )
        return results, total
