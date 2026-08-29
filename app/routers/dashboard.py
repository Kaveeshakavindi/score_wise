from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.deps import CurrentUser, get_dashboard_service, rate_limit_per_user
from app.schemas.common import Page
from app.schemas.dashboard import (
    DailyActivityOut,
    DashboardSummaryOut,
    SubjectAccuracyOut,
    TopicCountOut,
    TrendPointOut,
    TutorHelpedQuestionOut,
)
from app.schemas.tutor import TutorMessageOut
from app.services.dashboard_service import DashboardService

router = APIRouter(
    prefix="/api/v1/dashboard",
    tags=["dashboard"],
    dependencies=[Depends(rate_limit_per_user("dashboard_generic", limit=60, window_s=60))],
)

DashboardServiceDep = Annotated[DashboardService, Depends(get_dashboard_service)]


@router.get("/summary", response_model=DashboardSummaryOut)
async def get_summary(current_user: CurrentUser, dashboard_service: DashboardServiceDep) -> DashboardSummaryOut:
    """This student's performance overview: accuracy overall and per subject,
    a score trend across their most recent attempts, and how much of their
    tutor follow-up they've actually done. Requires auth."""
    summary = await dashboard_service.get_summary(current_user.id)
    return DashboardSummaryOut(
        overall_correct=summary.overall_correct,
        overall_total=summary.overall_total,
        attempts_count=summary.attempts_count,
        subjects=[SubjectAccuracyOut(subject=s.subject, correct=s.correct, total=s.total) for s in summary.subjects],
        trend=[
            TrendPointOut(
                attempt_id=t.attempt_id,
                paper_id=t.paper_id,
                subject=t.subject,
                year=t.year,
                score=t.score,
                total=t.total,
                created_at=t.created_at,
            )
            for t in summary.trend
        ],
        mistakes_total=summary.mistakes_total,
        mistakes_unreviewed=summary.mistakes_unreviewed,
        follow_through_rate=summary.follow_through_rate,
        tutor_helped_count=summary.tutor_helped_count,
        top_topics=[TopicCountOut(topic=t.topic, count=t.count) for t in summary.top_topics],
        tutor_activity=[DailyActivityOut(date=a.day, count=a.count) for a in summary.tutor_activity],
    )


@router.get("/tutor-history", response_model=Page[TutorHelpedQuestionOut])
async def list_tutor_history(
    current_user: CurrentUser,
    dashboard_service: DashboardServiceDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[TutorHelpedQuestionOut]:
    """Questions this student has viewed AI tutor feedback for, most
    recently viewed first, each with its saved feedback message. Requires
    auth."""
    helped, total = await dashboard_service.list_tutor_history(current_user.id, limit=limit, offset=offset)
    items = [
        TutorHelpedQuestionOut(
            question_id=h.question_id,
            subject=h.subject,
            year=h.year,
            question_number=h.question_number,
            question_text=h.question_text,
            last_discussed_at=h.last_discussed_at,
            messages=[TutorMessageOut.model_validate(m) for m in h.messages],
        )
        for h in helped
    ]
    return Page(items=items, total=total, limit=limit, offset=offset)
