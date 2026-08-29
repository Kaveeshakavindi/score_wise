from __future__ import annotations

import uuid

import pytest

from app.core.exceptions import NotFoundError
from app.services.paper_service import PaperService
from tests.fakes import FakePaperRepository, FakeQuestionRepository


@pytest.fixture
def paper_service() -> tuple[PaperService, FakePaperRepository, FakeQuestionRepository]:
    question_repo = FakeQuestionRepository()
    paper_repo = FakePaperRepository(question_repo=question_repo)
    return PaperService(paper_repo, question_repo), paper_repo, question_repo


async def test_list_papers_filters_by_subject(paper_service) -> None:
    service, paper_repo, _ = paper_service
    await paper_repo.create("Physics", 2022)
    await paper_repo.create("Chemistry", 2022)

    items, total = await service.list_papers("Physics", limit=20, offset=0)

    assert total == 1
    assert items[0][0].subject == "Physics"


async def test_list_papers_no_filter_returns_all_newest_year_first(paper_service) -> None:
    service, paper_repo, _ = paper_service
    await paper_repo.create("Physics", 2020)
    await paper_repo.create("Physics", 2023)

    items, total = await service.list_papers(None, limit=20, offset=0)

    assert total == 2
    assert [p.year for p, _ in items] == [2023, 2020]


async def test_list_papers_includes_question_count(paper_service) -> None:
    service, paper_repo, question_repo = paper_service
    paper = await paper_repo.create("Physics", 2022)
    other_paper = await paper_repo.create("Chemistry", 2021)
    for i in range(1, 4):
        await question_repo.create(
            paper.id, subject="Physics", year=2022, question_number=i, question_text=f"Q{i}",
            options={"A": "x"}, correct_answer=0,
        )
    await question_repo.create(
        other_paper.id, subject="Chemistry", year=2021, question_number=1, question_text="Q1",
        options={"A": "x"}, correct_answer=0,
    )

    items, _ = await service.list_papers(None, limit=20, offset=0)

    counts = {p.id: count for p, count in items}
    assert counts[paper.id] == 3
    assert counts[other_paper.id] == 1


async def test_list_papers_question_count_zero_when_no_questions(paper_service) -> None:
    service, paper_repo, _ = paper_service
    paper = await paper_repo.create("Physics", 2022)

    items, _ = await service.list_papers(None, limit=20, offset=0)

    counts = {p.id: count for p, count in items}
    assert counts[paper.id] == 0


async def test_list_questions_returns_ordered_by_question_number(paper_service) -> None:
    service, paper_repo, question_repo = paper_service
    paper = await paper_repo.create("Physics", 2022)
    await question_repo.create(
        paper.id, subject="Physics", year=2022, question_number=2, question_text="Q2",
        options={"A": "x"}, correct_answer=0,
    )
    await question_repo.create(
        paper.id, subject="Physics", year=2022, question_number=1, question_text="Q1",
        options={"A": "x"}, correct_answer=0,
    )

    items, total = await service.list_questions(paper.id, limit=20, offset=0)

    assert total == 2
    assert [q.question_number for q in items] == [1, 2]


async def test_list_questions_missing_paper_raises_not_found(paper_service) -> None:
    service, _, _ = paper_service
    with pytest.raises(NotFoundError):
        await service.list_questions(uuid.uuid4(), limit=20, offset=0)
