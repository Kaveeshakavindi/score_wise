from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class PaperOut(BaseModel):
    id: UUID
    subject: str
    year: int
    question_count: int
    created_at: datetime

    model_config = {"from_attributes": True}
