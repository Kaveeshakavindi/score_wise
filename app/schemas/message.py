from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class SendMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=8000)


class MessageOut(BaseModel):
    id: UUID
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ToolCallSummary(BaseModel):
    name: str
    args: dict[str, Any]
    status: Literal["ok", "error"]
    duration_ms: int


class SendMessageResponse(BaseModel):
    user_message: MessageOut
    assistant_message: MessageOut
    tool_calls: list[ToolCallSummary] = []
    generated_title: str | None = None
