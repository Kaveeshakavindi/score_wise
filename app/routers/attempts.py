from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.deps import CurrentUser, get_attempt_service, rate_limit_per_user
from app.schemas.attempt import AttemptAnswerResult, AttemptOut, AttemptSubmitRequest
from app.services.attempt_service import AttemptAnswerInput, AttemptService

router = APIRouter(
    prefix="/api/v1/attempts",
    tags=["attempts"],
    dependencies=[Depends(rate_limit_per_user("attempts_generic", limit=60, window_s=60))],
)

AttemptServiceDep = Annotated[AttemptService, Depends(get_attempt_service)]


@router.post("", response_model=AttemptOut, status_code=status.HTTP_201_CREATED)
async def submit_attempt(
    body: AttemptSubmitRequest, current_user: CurrentUser, attempt_service: AttemptServiceDep
) -> AttemptOut:
    """Submit a full attempt (answers array); scores it immediately against
    the stored correct answers and returns per-question correct/incorrect.
    Requires auth. `401`/`404` (paper or a submitted question not found),
    `422` (a submitted question doesn't belong to the paper)."""
    answers = [AttemptAnswerInput(question_id=a.question_id, selected_answer=a.selected_answer) for a in body.answers]
    result = await attempt_service.submit(current_user.id, body.paper_id, answers)
    return AttemptOut(
        id=result.id,
        paper_id=result.paper_id,
        score=result.score,
        total=result.total,
        created_at=result.created_at,
        results=[
            AttemptAnswerResult(
                question_id=r.question_id,
                selected_answer=r.selected_answer,
                correct_answer=r.correct_answer,
                is_correct=r.is_correct,
            )
            for r in result.results
        ],
    )
