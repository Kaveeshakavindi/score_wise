from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.core.deps import CurrentUser, get_tutor_rag_service, rate_limit_per_user
from app.schemas.tutor import TutorFeedbackRequest, TutorFeedbackResponse, TutorMessageOut
from app.services.tutor_rag_service import TutorRagService

router = APIRouter(prefix="/api/v1/questions/{question_id}/tutor", tags=["tutor"])

TutorServiceDep = Annotated[TutorRagService, Depends(get_tutor_rag_service)]


@router.post(
    "",
    response_model=TutorFeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit_per_user("tutor_feedback", limit=20, window_s=60))],
)
async def get_tutor_feedback(
    question_id: UUID, body: TutorFeedbackRequest, current_user: CurrentUser, tutor_service: TutorServiceDep
) -> TutorFeedbackResponse:
    """Structured, grounded feedback on this student's answer to this
    question — not a chat: pass whatever `selected_answer` they submitted
    (or omit it if they left the question blank) and get back a fixed-shape
    explanation of why it was correct, wrong, or what the right answer was,
    plus the citations (retrieved syllabus chunks) that grounded it.
    Idempotent — the first call generates and caches the feedback; every
    later call for this (question, student) pair returns the same cached
    result without another LLM call, so the results screen can call this on
    every question without worrying about cost from repeat views. Requires
    auth. `404` if the question doesn't exist. 20 req/min per user — each
    *first* call is a paid LLM request, same budget as the generic chat's
    POST /messages (§8)."""
    feedback = await tutor_service.generate_feedback(current_user.id, question_id, body.selected_answer)
    return TutorFeedbackResponse(feedback=TutorMessageOut.model_validate(feedback))
