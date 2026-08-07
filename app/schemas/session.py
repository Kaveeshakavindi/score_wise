from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SessionOut(BaseModel):
    id: UUID
    title: str | None
    created_at: datetime
    last_active: datetime

    model_config = {"from_attributes": True}


class SessionListItem(BaseModel):
    id: UUID
    title: str | None
    last_active: datetime

    model_config = {"from_attributes": True}


class SessionRenameRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
