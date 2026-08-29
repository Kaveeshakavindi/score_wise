from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.deps import CurrentUser, SettingsDep, get_llm_usage_repository
from app.repositories.llm_usage_repository import LlmUsageRepository
from app.schemas.usage import UsageSummaryOut

router = APIRouter(prefix="/api/v1/usage", tags=["usage"])

LlmUsageRepoDep = Annotated[LlmUsageRepository, Depends(get_llm_usage_repository)]


@router.get("/me", response_model=UsageSummaryOut)
async def get_my_usage(
    current_user: CurrentUser, settings: SettingsDep, llm_usage_repo: LlmUsageRepoDep
) -> UsageSummaryOut:
    """This user's token usage for the current UTC day, across every LLM
    feature (tutor feedback, chat, title generation). `daily_budget` and
    `tokens_remaining` are null when no budget is configured — see
    DAILY_TOKEN_BUDGET / app.core.deps.token_budget_check."""
    now = datetime.now(timezone.utc)
    since = now.replace(hour=0, minute=0, second=0, microsecond=0)
    resets_at = since + timedelta(days=1)

    used = await llm_usage_repo.sum_tokens_since(current_user.id, since)
    budget = settings.daily_token_budget

    return UsageSummaryOut(
        tokens_used_today=used,
        daily_budget=budget,
        tokens_remaining=max(budget - used, 0) if budget is not None else None,
        resets_at=resets_at,
    )
