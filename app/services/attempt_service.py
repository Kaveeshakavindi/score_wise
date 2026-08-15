from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from app.core.exceptions import NotFoundError, ValidationError
from app.repositories.attempt_repository import AttemptRepository
from app.repositories.paper_repository import PaperRepository
from app.repositories.question_repository import QuestionRepository


@dataclass(frozen=True)
class AttemptAnswerInput:
    """Framework-agnostic input — routers map the AttemptAnswerIn schema to
    this before calling the service, so the service never imports app.schemas
    (§2 layering rule: services depend only on repos, not on request DTOs)."""

    question_id: uuid.UUID
    selected_answer: int | None


@dataclass(frozen=True)
class AttemptAnswerOutcome:
    question_id: uuid.UUID
    selected_answer: int | None
    correct_answer: int | None
    is_correct: bool


@dataclass(frozen=True)
class AttemptSubmitResult:
    id: uuid.UUID
    paper_id: uuid.UUID
    score: int
    total: int
    created_at: datetime
    results: list[AttemptAnswerOutcome]


class AttemptService:
    def __init__(
        self, attempt_repo: AttemptRepository, paper_repo: PaperRepository, question_repo: QuestionRepository
    ) -> None:
        self._attempts = attempt_repo
        self._papers = paper_repo
        self._questions = question_repo

    async def submit(
        self, user_id: uuid.UUID, paper_id: uuid.UUID, answers: list[AttemptAnswerInput]
    ) -> AttemptSubmitResult:
        paper = await self._papers.get_by_id(paper_id)
        if paper is None:
            raise NotFoundError(f"Paper {paper_id} was not found.")

        questions_by_id = await self._questions.get_many_by_ids([a.question_id for a in answers])

        outcomes: list[AttemptAnswerOutcome] = []
        score = 0
        for answer in answers:
            question = questions_by_id.get(answer.question_id)
            if question is None or question.paper_id != paper_id:
                raise ValidationError(f"Question {answer.question_id} is not part of paper {paper_id}.")

            # accept_all = examiner voided this question on the official marking
            # scheme (marked "All" instead of a specific option) — every
            # response, including a left-blank one, is scored as correct.
            is_correct = question.accept_all or (
                answer.selected_answer is not None and answer.selected_answer == question.correct_answer
            )
            if is_correct:
                score += 1
            outcomes.append(
                AttemptAnswerOutcome(
                    question_id=question.id,
                    selected_answer=answer.selected_answer,
                    correct_answer=question.correct_answer,
                    is_correct=is_correct,
                )
            )

        attempt = await self._attempts.create(user_id=user_id, paper_id=paper_id, score=score, total=len(outcomes))
        for outcome in outcomes:
            await self._attempts.add_answer(
                attempt_id=attempt.id,
                question_id=outcome.question_id,
                selected_answer=outcome.selected_answer,
                is_correct=outcome.is_correct,
            )

        return AttemptSubmitResult(
            id=attempt.id,
            paper_id=paper_id,
            score=score,
            total=len(outcomes),
            created_at=attempt.created_at,
            results=outcomes,
        )
