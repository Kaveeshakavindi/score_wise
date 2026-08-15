from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.core.deps import CurrentUser, get_paper_service, rate_limit_per_user
from app.schemas.common import Page
from app.schemas.paper import PaperOut
from app.schemas.question import QuestionOut
from app.services.paper_service import PaperService

router = APIRouter(
    prefix="/api/v1/papers",
    tags=["papers"],
    dependencies=[Depends(rate_limit_per_user("papers_generic", limit=120, window_s=60))],
)

PaperServiceDep = Annotated[PaperService, Depends(get_paper_service)]


@router.get("", response_model=Page[PaperOut])
async def list_papers(
    current_user: CurrentUser,
    paper_service: PaperServiceDep,
    subject: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[PaperOut]:
    """List available past papers, optionally filtered by subject, newest
    year first. Requires auth."""
    items, total = await paper_service.list_papers(subject, limit=limit, offset=offset)
    return Page(items=[PaperOut.model_validate(p) for p in items], total=total, limit=limit, offset=offset)


@router.get("/{paper_id}/questions", response_model=Page[QuestionOut])
async def list_paper_questions(
    paper_id: UUID,
    current_user: CurrentUser,
    paper_service: PaperServiceDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[QuestionOut]:
    """List a paper's questions in question-number order. Requires auth.
    `correct_answer` is deliberately omitted from the response — see
    QuestionOut's docstring."""
    items, total = await paper_service.list_questions(paper_id, limit=limit, offset=offset)
    return Page(items=[QuestionOut.model_validate(q) for q in items], total=total, limit=limit, offset=offset)
