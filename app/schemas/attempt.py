from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AttemptAnswerIn(BaseModel):
    question_id: UUID
    selected_answer: int | None = Field(
        None,
        ge=0,
        description=(
            "0-based index into the question's options (0='A'); null if left unanswered. No upper bound here — "
            "option count varies per question (real data ranges up to 5), so an out-of-range index is left for "
            "AttemptService to simply score as incorrect rather than rejected as a schema error."
        ),
    )


class AttemptSubmitRequest(BaseModel):
    paper_id: UUID
    answers: list[AttemptAnswerIn] = Field(min_length=1)


class AttemptAnswerResult(BaseModel):
    question_id: UUID
    selected_answer: int | None
    # Null when the question was voided on the official marking scheme
    # (accept_all=True) — every response was scored correct, so there's no
    # single right answer to report.
    correct_answer: int | None
    is_correct: bool


class AttemptOut(BaseModel):
    id: UUID
    paper_id: UUID
    score: int
    total: int
    created_at: datetime
    results: list[AttemptAnswerResult]
