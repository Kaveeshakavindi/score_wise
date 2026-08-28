from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class TutorFeedbackRequest(BaseModel):
    # 0-based index into the question's options, matching AttemptSubmitRequest's
    # convention; null means the student left the question blank. Always sent
    # (never omitted) — it's the only thing that determines which of the
    # three feedback branches (correct/wrong/missed) gets generated.
    selected_answer: int | None = Field(None, ge=0)


class CitationOut(BaseModel):
    """One syllabus chunk that grounded the feedback — lets the UI show an
    expandable "citation" proving the explanation traces back to real
    syllabus content rather than the model's own claims."""

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
    # Which option was selected (see TutorMessage.selected_answer) — lets the
    # UI show the same badge the result screen already shows.
    selected_answer: int | None = None
    # Whether that selected_answer was correct. Null only for legacy rows
    # created before this column existed.
    is_correct: bool | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class TutorFeedbackResponse(BaseModel):
    feedback: TutorMessageOut
