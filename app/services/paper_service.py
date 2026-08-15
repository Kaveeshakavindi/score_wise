from __future__ import annotations

import uuid

from app.core.exceptions import NotFoundError
from app.db.models import Paper, Question
from app.repositories.paper_repository import PaperRepository
from app.repositories.question_repository import QuestionRepository


class PaperService:
    def __init__(self, paper_repo: PaperRepository, question_repo: QuestionRepository) -> None:
        self._papers = paper_repo
        self._questions = question_repo

    async def list_papers(self, subject: str | None, *, limit: int, offset: int) -> tuple[list[Paper], int]:
        items = await self._papers.list_by_subject(subject, limit=limit, offset=offset)
        total = await self._papers.count_by_subject(subject)
        return items, total

    async def list_questions(self, paper_id: uuid.UUID, *, limit: int, offset: int) -> tuple[list[Question], int]:
        paper = await self._papers.get_by_id(paper_id)
        if paper is None:
            raise NotFoundError(f"Paper {paper_id} was not found.")
        items = await self._questions.list_by_paper(paper_id, limit=limit, offset=offset)
        total = await self._questions.count_by_paper(paper_id)
        return items, total
