from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class QuestionOut(BaseModel):
    """Public question shape. Deliberately omits `correct_answer` — exposing
    the answer key while a student is still browsing/attempting a paper would
    defeat the practice tool's purpose. The correct answer is only ever used
    server-side (AttemptService scoring) or stated explicitly inside the
    tutor's system prompt (never returned verbatim by a listing endpoint)."""

    id: UUID
    paper_id: UUID
    subject: str
    year: int
    question_number: int
    question_text: str
    options: dict[str, str]

    model_config = {"from_attributes": True}
