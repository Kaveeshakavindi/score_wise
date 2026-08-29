from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from app.core.deps import (
    CurrentUser,
    SettingsDep,
    get_llm_usage_repository,
    get_tutor_rag_service,
    rate_limit_per_user,
    token_budget_check,
)
from app.llm.pricing import estimate_cost_usd
from app.repositories.llm_usage_repository import LlmUsageRepository
from app.schemas.tutor import TutorFeedbackRequest, TutorFeedbackResponse, TutorMessageOut
from app.services.tutor_rag_service import TutorRagService

router = APIRouter(prefix="/api/v1/questions/{question_id}/tutor", tags=["tutor"])

TutorServiceDep = Annotated[TutorRagService, Depends(get_tutor_rag_service)]
LlmUsageRepoDep = Annotated[LlmUsageRepository, Depends(get_llm_usage_repository)]


@router.post(
    "",
    response_model=TutorFeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(rate_limit_per_user("tutor_feedback", limit=20, window_s=60)),
        Depends(token_budget_check("tutor_feedback")),
    ],
)
async def get_tutor_feedback(
    question_id: UUID,
    body: TutorFeedbackRequest,
    current_user: CurrentUser,
    tutor_service: TutorServiceDep,
    settings: SettingsDep,
    llm_usage_repo: LlmUsageRepoDep,
    response: Response,
) -> TutorFeedbackResponse:
    """Structured, grounded feedback on this student's answer to this
    question — not a chat: pass whatever `selected_answer` they submitted
    (or omit it if they left the question blank) and get back a fixed-shape
    explanation of why it was correct, wrong, or what the right answer was,
    plus the citations (retrieved syllabus chunks) that grounded it.
    Idempotent per (question, student, selected_answer) — asking again about
    the exact same answer returns the same cached result without another LLM
    call; a different answer always generates fresh feedback. Requires auth.
    `404` if the question doesn't exist. 20 req/min per user, plus an opt-in
    daily token budget (DAILY_TOKEN_BUDGET) — each *first* call for a given
    answer is a paid LLM request."""
    feedback = await tutor_service.generate_feedback(current_user.id, question_id, body.selected_answer)
    feedback_out = TutorMessageOut.model_validate(feedback)

    if feedback_out.input_tokens is not None and feedback_out.output_tokens is not None:
        cost = estimate_cost_usd(settings.anthropic_model, feedback_out.input_tokens, feedback_out.output_tokens)
        feedback_out = feedback_out.model_copy(update={"estimated_cost_usd": cost})
        response.headers["X-Tokens-Used-Request"] = str(feedback_out.input_tokens + feedback_out.output_tokens)

    if settings.daily_token_budget is not None:
        now = datetime.now(timezone.utc)
        since = now.replace(hour=0, minute=0, second=0, microsecond=0)
        used_today = await llm_usage_repo.sum_tokens_since(current_user.id, since)
        response.headers["X-Tokens-Remaining-Today"] = str(max(settings.daily_token_budget - used_today, 0))

    return TutorFeedbackResponse(feedback=feedback_out)
