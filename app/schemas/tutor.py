from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class TutorMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
    # 0-based index into the question's options, matching AttemptSubmitRequest's
    # convention. Optional and typically only sent on the opening turn right
    # after a wrong attempt, so the tutor can address what the student picked
    # instead of only explaining the correct answer in the abstract.
    selected_answer: int | None = None


class CitationOut(BaseModel):
    """One syllabus chunk that grounded an assistant reply — lets the UI show
    an expandable "citation" proving the answer traces back to real syllabus
    content rather than the model's own claims."""

    document_id: UUID
    filename: str
    topic: str | None
    snippet: str

    model_config = {"from_attributes": True}


class TutorMessageOut(BaseModel):
    id: UUID
    role: Literal["user", "assistant"]
    content: str
    citations: list[CitationOut] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class TutorReplyResponse(BaseModel):
    user_message: TutorMessageOut
    assistant_message: TutorMessageOut
