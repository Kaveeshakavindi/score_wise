from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel

from app.schemas.tutor import TutorMessageOut


class SubjectAccuracyOut(BaseModel):
    subject: str
    correct: int
    total: int


class TrendPointOut(BaseModel):
    attempt_id: UUID
    paper_id: UUID
    subject: str
    year: int
    score: int
    total: int
    created_at: datetime


class TopicCountOut(BaseModel):
    topic: str
    count: int


class DailyActivityOut(BaseModel):
    date: date
    count: int


class DashboardSummaryOut(BaseModel):
    overall_correct: int
    overall_total: int
    attempts_count: int
    subjects: list[SubjectAccuracyOut]
    # Oldest -> newest, at most the last N attempts (see DashboardService).
    trend: list[TrendPointOut]
    mistakes_total: int
    mistakes_unreviewed: int
    # 0.0 if mistakes_total == 0 (nothing to have followed up on yet).
    follow_through_rate: float
    # Distinct wrong answers the student has viewed AI tutor feedback for.
    tutor_helped_count: int
    top_topics: list[TopicCountOut]
    # Explanations viewed per day, last 14 days, zero-filled, oldest -> newest
    # — the "AI Tutor activity" engagement chart. Every outcome counts, not
    # just mistakes (see DashboardService.get_summary).
    tutor_activity: list[DailyActivityOut]


class TutorHelpedQuestionOut(BaseModel):
    """One question the student has viewed AI tutor feedback for: just
    enough question context to place it, plus the saved feedback message
    (read-only — regenerating it happens through POST /questions/{id}/tutor,
    same as /exam, but it's idempotent so this is just a cached view)."""

    question_id: UUID
    subject: str
    year: int
    question_number: int
    question_text: str
    last_discussed_at: datetime
    messages: list[TutorMessageOut]
