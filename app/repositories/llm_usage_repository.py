from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import LlmUsageEvent
from app.llm.anthropic_client import Usage


class LlmUsageRepository:
    """Append-only ledger of every LLM call — see LlmUsageEvent. Written by
    each service right after its own LLM call succeeds, read by the token
    budget check (app.core.deps.token_budget_check) and GET /api/v1/usage/me."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(
        self, *, user_id: uuid.UUID | None, feature: str, model: str, usage: Usage, request_id: str | None
    ) -> LlmUsageEvent:
        event = LlmUsageEvent(
            user_id=user_id,
            feature=feature,
            model=model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            total_tokens=usage.total_tokens,
            request_id=request_id,
        )
        self._session.add(event)
        await self._session.flush()
        return event

    async def sum_tokens_since(self, user_id: uuid.UUID, since: datetime) -> int:
        """Total tokens this user has used across every feature since
        `since` (typically the start of the current day, UTC) — the budget
        check's one query, batched rather than summing rows in Python."""
        result = await self._session.execute(
            select(func.coalesce(func.sum(LlmUsageEvent.total_tokens), 0)).where(
                LlmUsageEvent.user_id == user_id, LlmUsageEvent.created_at >= since
            )
        )
        return int(result.scalar_one())
