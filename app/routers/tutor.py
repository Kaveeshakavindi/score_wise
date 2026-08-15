from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.core.deps import CurrentUser, get_tutor_rag_service, rate_limit_per_user
from app.schemas.tutor import TutorMessageOut, TutorMessageRequest, TutorReplyResponse
from app.services.tutor_rag_service import TutorRagService

router = APIRouter(prefix="/api/v1/questions/{question_id}/tutor", tags=["tutor"])

TutorServiceDep = Annotated[TutorRagService, Depends(get_tutor_rag_service)]


@router.post(
    "",
    response_model=TutorReplyResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit_per_user("tutor_messages", limit=20, window_s=60))],
)
async def send_tutor_message(
    question_id: UUID, body: TutorMessageRequest, current_user: CurrentUser, tutor_service: TutorServiceDep
) -> TutorReplyResponse:
    """Send a message to the question-scoped AI tutor; returns a grounded
    reply restricted to the question/answer data and retrieved syllabus
    context (§3), plus the citations (retrieved syllabus chunks) that
    grounded it. `selected_answer` is optional — pass it (typically only on
    the opening turn right after a wrong attempt) so the tutor addresses the
    student's actual wrong choice instead of only the correct answer in the
    abstract. Requires auth. `404` if the question doesn't exist. 20 req/min
    per user — each call is a paid LLM request, same budget as the generic
    chat's POST /messages (§8)."""
    result = await tutor_service.send_message(current_user.id, question_id, body.content, body.selected_answer)
    return TutorReplyResponse(
        user_message=TutorMessageOut.model_validate(result.user_message),
        assistant_message=TutorMessageOut.model_validate(result.assistant_message),
    )


@router.get("/history", response_model=list[TutorMessageOut])
async def get_tutor_history(
    question_id: UUID, current_user: CurrentUser, tutor_service: TutorServiceDep
) -> list[TutorMessageOut]:
    """This caller's prior tutor chat turns for this question, oldest ->
    newest. Requires auth. `404` if the question doesn't exist."""
    history = await tutor_service.get_history(current_user.id, question_id)
    return [TutorMessageOut.model_validate(m) for m in history]
