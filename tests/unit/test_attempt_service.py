from __future__ import annotations

import uuid

import pytest

from app.core.exceptions import NotFoundError, ValidationError
from app.services.attempt_service import AttemptAnswerInput, AttemptService
from tests.fakes import FakeAttemptRepository, FakePaperRepository, FakeQuestionRepository


@pytest.fixture
def attempt_service() -> tuple[AttemptService, FakePaperRepository, FakeQuestionRepository, FakeAttemptRepository]:
    paper_repo = FakePaperRepository()
    question_repo = FakeQuestionRepository()
    attempt_repo = FakeAttemptRepository()
    return AttemptService(attempt_repo, paper_repo, question_repo), paper_repo, question_repo, attempt_repo


async def test_submit_scores_correct_and_incorrect_answers(attempt_service) -> None:
    service, paper_repo, question_repo, attempt_repo = attempt_service
    paper = await paper_repo.create("Physics", 2022)
    q1 = await question_repo.create(
        paper.id, subject="Physics", year=2022, question_number=1, question_text="Q1",
        options={"A": "a", "B": "b"}, correct_answer=0,
    )
    q2 = await question_repo.create(
        paper.id, subject="Physics", year=2022, question_number=2, question_text="Q2",
        options={"A": "a", "B": "b"}, correct_answer=1,
    )

    result = await service.submit(
        uuid.uuid4(),
        paper.id,
        [
            AttemptAnswerInput(question_id=q1.id, selected_answer=0),  # correct
            AttemptAnswerInput(question_id=q2.id, selected_answer=0),  # incorrect
        ],
    )

    assert result.score == 1
    assert result.total == 2
    outcomes = {o.question_id: o for o in result.results}
    assert outcomes[q1.id].is_correct is True
    assert outcomes[q2.id].is_correct is False
    assert len(attempt_repo.answers) == 2


async def test_submit_unanswered_question_counts_as_incorrect_not_an_error(attempt_service) -> None:
    service, paper_repo, question_repo, _ = attempt_service
    paper = await paper_repo.create("Physics", 2022)
    q1 = await question_repo.create(
        paper.id, subject="Physics", year=2022, question_number=1, question_text="Q1",
        options={"A": "a"}, correct_answer=0,
    )

    result = await service.submit(uuid.uuid4(), paper.id, [AttemptAnswerInput(question_id=q1.id, selected_answer=None)])

    assert result.score == 0
    assert result.results[0].is_correct is False
    assert result.results[0].selected_answer is None


async def test_submit_missing_paper_raises_not_found(attempt_service) -> None:
    service, _, _, _ = attempt_service
    with pytest.raises(NotFoundError):
        await service.submit(uuid.uuid4(), uuid.uuid4(), [])


async def test_submit_question_not_belonging_to_paper_raises_validation_error(attempt_service) -> None:
    service, paper_repo, question_repo, _ = attempt_service
    paper_a = await paper_repo.create("Physics", 2022)
    paper_b = await paper_repo.create("Chemistry", 2022)
    q_from_b = await question_repo.create(
        paper_b.id, subject="Chemistry", year=2022, question_number=1, question_text="Q1",
        options={"A": "a"}, correct_answer=0,
    )

    with pytest.raises(ValidationError):
        await service.submit(uuid.uuid4(), paper_a.id, [AttemptAnswerInput(question_id=q_from_b.id, selected_answer=0)])


async def test_submit_unknown_question_id_raises_validation_error(attempt_service) -> None:
    service, paper_repo, _, _ = attempt_service
    paper = await paper_repo.create("Physics", 2022)

    with pytest.raises(ValidationError):
        await service.submit(uuid.uuid4(), paper.id, [AttemptAnswerInput(question_id=uuid.uuid4(), selected_answer=0)])
