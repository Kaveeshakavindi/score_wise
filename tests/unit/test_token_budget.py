from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.core.deps import token_budget_check
from app.core.exceptions import RateLimitedError
from app.llm.anthropic_client import Usage
from tests.fakes import FakeLlmUsageRepository


async def _seed(repo: FakeLlmUsageRepository, user_id, total_tokens: int, *, when: datetime | None = None) -> None:
    event = await repo.record(
        user_id=user_id,
        feature="tutor_feedback",
        model="test-model",
        usage=Usage(input_tokens=total_tokens, output_tokens=0, total_tokens=total_tokens),
        request_id=None,
    )
    if when is not None:
        event.created_at = when


async def test_token_budget_check_is_a_noop_when_unset(test_user, settings) -> None:
    dependency = token_budget_check("tutor_feedback")
    unset_settings = settings.model_copy(update={"daily_token_budget": None})
    llm_usage_repo = FakeLlmUsageRepository()

    # No exception even with usage far beyond any reasonable limit.
    await _seed(llm_usage_repo, test_user.id, 10_000_000)
    await dependency(current_user=test_user, settings=unset_settings, llm_usage_repo=llm_usage_repo)


async def test_token_budget_check_passes_when_under_budget(test_user, settings) -> None:
    dependency = token_budget_check("tutor_feedback")
    budgeted_settings = settings.model_copy(update={"daily_token_budget": 1000})
    llm_usage_repo = FakeLlmUsageRepository()
    await _seed(llm_usage_repo, test_user.id, 500)

    await dependency(current_user=test_user, settings=budgeted_settings, llm_usage_repo=llm_usage_repo)


async def test_token_budget_check_raises_at_or_over_budget(test_user, settings) -> None:
    dependency = token_budget_check("tutor_feedback")
    budgeted_settings = settings.model_copy(update={"daily_token_budget": 1000})
    llm_usage_repo = FakeLlmUsageRepository()
    await _seed(llm_usage_repo, test_user.id, 1000)

    with pytest.raises(RateLimitedError):
        await dependency(current_user=test_user, settings=budgeted_settings, llm_usage_repo=llm_usage_repo)


async def test_token_budget_check_ignores_usage_from_a_prior_day(test_user, settings) -> None:
    dependency = token_budget_check("tutor_feedback")
    budgeted_settings = settings.model_copy(update={"daily_token_budget": 1000})
    llm_usage_repo = FakeLlmUsageRepository()
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    await _seed(llm_usage_repo, test_user.id, 5000, when=yesterday)

    # Yesterday's usage doesn't count against today's budget.
    await dependency(current_user=test_user, settings=budgeted_settings, llm_usage_repo=llm_usage_repo)
