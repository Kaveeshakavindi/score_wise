from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ToolInvocation


class ToolInvocationRepository:
    """Audit trail for every tool the model invokes (§9, §12)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        session_id: uuid.UUID,
        tool_name: str,
        args: dict[str, Any],
        status: str,
        duration_ms: int,
        error_message: str | None = None,
    ) -> ToolInvocation:
        invocation = ToolInvocation(
            session_id=session_id,
            tool_name=tool_name,
            args=args,
            status=status,
            duration_ms=duration_ms,
            error_message=error_message,
        )
        self._session.add(invocation)
        await self._session.flush()
        return invocation
