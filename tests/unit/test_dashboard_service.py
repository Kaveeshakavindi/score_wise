from __future__ import annotations

import uuid

import pytest

from app.services.dashboard_service import DashboardService
from tests.fakes import FakeAttemptRepository, FakePaperRepository, FakeQuestionRepository, FakeTutorMessageRepository


@pytest.fixture
def dashboard():
    paper_repo = FakePaperRepository()
    question_repo = FakeQuestionRepository()
    attempt_repo = FakeAttemptRepository(paper_repo=paper_repo, question_repo=question_repo)
    tutor_repo = FakeTutorMessageRepository()
    service = DashboardService(attempt_repo, tutor_repo, question_repo)
    return service, paper_repo, question_repo, attempt_repo, tutor_repo


async def _submit(attempt_repo, *, user_id, paper_id, answers: list[tuple[uuid.UUID, bool]]):
    """answers: list of (question_id, is_correct). Mirrors what
    AttemptService.submit does to attempt_repo, without pulling in the whole
    service — this test suite is only exercising DashboardService's reads."""
    attempt = await attempt_repo.create(user_id=user_id, paper_id=paper_id, score=0, total=len(answers))
    for question_id, is_correct in answers:
        await attempt_repo.add_answer(
            attempt_id=attempt.id, question_id=question_id, selected_answer=0, is_correct=is_correct
        )
    return attempt


async def test_get_summary_empty_for_new_user(dashboard) -> None:
    service, *_ = dashboard
    summary = await service.get_summary(uuid.uuid4())

    assert summary.attempts_count == 0
    assert summary.trend == []
    assert summary.subjects == []
    assert summary.mistakes_total == 0
    assert summary.mistakes_unreviewed == 0
    assert summary.follow_through_rate == 0.0
    assert summary.tutor_helped_count == 0
    assert summary.top_topics == []


async def test_get_summary_aggregates_across_subjects_and_orders_trend_oldest_first(dashboard) -> None:
    service, paper_repo, question_repo, attempt_repo, _ = dashboard
    user_id = uuid.uuid4()

    physics = await paper_repo.create("Physics", 2022)
    chemistry = await paper_repo.create("Chemistry", 2022)
    pq = await question_repo.create(
        physics.id, subject="Physics", year=2022, question_number=1, question_text="P1",
        options={"A": "a", "B": "b"}, correct_answer=0,
    )
    cq = await question_repo.create(
        chemistry.id, subject="Chemistry", year=2022, question_number=1, question_text="C1",
        options={"A": "a", "B": "b"}, correct_answer=0,
    )

    first = await _submit(attempt_repo, user_id=user_id, paper_id=physics.id, answers=[(pq.id, False)])
    second = await _submit(attempt_repo, user_id=user_id, paper_id=chemistry.id, answers=[(cq.id, True)])

    summary = await service.get_summary(user_id)

    assert summary.attempts_count == 2
    subjects = {s.subject: (s.correct, s.total) for s in summary.subjects}
    assert subjects == {"Physics": (0, 1), "Chemistry": (1, 1)}
    assert summary.overall_correct == 1
    assert summary.overall_total == 2
    # Attempts are created in dict-insertion order here, so this also proves
    # list_recent_with_paper's desc-then-reverse round-trips back to
    # chronological order rather than staying reversed.
    assert [t.attempt_id for t in summary.trend] == [first.id, second.id]


async def test_get_summary_follow_through_rate_counts_reviewed_vs_unreviewed(dashboard) -> None:
    service, paper_repo, question_repo, attempt_repo, tutor_repo = dashboard
    user_id = uuid.uuid4()
    paper = await paper_repo.create("Physics", 2022)
    q1 = await question_repo.create(
        paper.id, subject="Physics", year=2022, question_number=1, question_text="Q1",
        options={"A": "a"}, correct_answer=0,
    )
    q2 = await question_repo.create(
        paper.id, subject="Physics", year=2022, question_number=2, question_text="Q2",
        options={"A": "a"}, correct_answer=0,
    )
    await _submit(attempt_repo, user_id=user_id, paper_id=paper.id, answers=[(q1.id, False), (q2.id, False)])

    # Only q1's feedback has been viewed.
    await tutor_repo.create(question_id=q1.id, user_id=user_id, role="assistant", content="help", is_correct=False)

    summary = await service.get_summary(user_id)

    assert summary.mistakes_total == 2
    assert summary.mistakes_unreviewed == 1
    assert summary.follow_through_rate == pytest.approx(0.5)
    assert summary.tutor_helped_count == 1


async def test_get_summary_ranks_top_cited_topics(dashboard) -> None:
    service, paper_repo, question_repo, attempt_repo, tutor_repo = dashboard
    user_id = uuid.uuid4()
    paper = await paper_repo.create("Physics", 2022)
    q = await question_repo.create(
        paper.id, subject="Physics", year=2022, question_number=1, question_text="Q1",
        options={"A": "a"}, correct_answer=0,
    )

    async def cite(topic: str) -> None:
        await tutor_repo.create(
            question_id=q.id, user_id=user_id, role="assistant", content="explanation", is_correct=False,
            citations=[{"document_id": str(uuid.uuid4()), "filename": "f.pdf", "topic": topic, "snippet": "s"}],
        )

    await cite("Projectile motion")
    await cite("Projectile motion")
    await cite("Equilibrium")

    summary = await service.get_summary(user_id)

    assert [(t.topic, t.count) for t in summary.top_topics] == [("Projectile motion", 2), ("Equilibrium", 1)]


async def test_list_tutor_history_includes_only_discussed_questions(dashboard) -> None:
    service, paper_repo, question_repo, attempt_repo, tutor_repo = dashboard
    user_id = uuid.uuid4()
    paper = await paper_repo.create("Physics", 2022)
    discussed = await question_repo.create(
        paper.id, subject="Physics", year=2022, question_number=1, question_text="Discussed",
        options={"A": "a"}, correct_answer=0,
    )
    undiscussed = await question_repo.create(
        paper.id, subject="Physics", year=2022, question_number=2, question_text="Undiscussed",
        options={"A": "a"}, correct_answer=0,
    )
    await _submit(
        attempt_repo, user_id=user_id, paper_id=paper.id,
        answers=[(discussed.id, False), (undiscussed.id, False)],
    )
    await tutor_repo.create(question_id=discussed.id, user_id=user_id, role="assistant", content="sure", is_correct=False)

    items, total = await service.list_tutor_history(user_id, limit=20, offset=0)

    assert total == 1
    assert [h.question_id for h in items] == [discussed.id]
    assert [m.content for m in items[0].messages] == ["sure"]
    assert items[0].question_text == "Discussed"


async def test_list_tutor_history_orders_most_recently_discussed_first(dashboard) -> None:
    service, paper_repo, question_repo, attempt_repo, tutor_repo = dashboard
    user_id = uuid.uuid4()
    paper = await paper_repo.create("Physics", 2022)
    q1 = await question_repo.create(
        paper.id, subject="Physics", year=2022, question_number=1, question_text="Q1",
        options={"A": "a"}, correct_answer=0,
    )
    q2 = await question_repo.create(
        paper.id, subject="Physics", year=2022, question_number=2, question_text="Q2",
        options={"A": "a"}, correct_answer=0,
    )
    await tutor_repo.create(question_id=q1.id, user_id=user_id, role="assistant", content="first", is_correct=False)
    await tutor_repo.create(question_id=q2.id, user_id=user_id, role="assistant", content="second", is_correct=False)

    items, total = await service.list_tutor_history(user_id, limit=20, offset=0)

    assert total == 2
    assert [h.question_id for h in items] == [q2.id, q1.id]


async def test_list_tutor_history_paginates(dashboard) -> None:
    service, paper_repo, question_repo, attempt_repo, tutor_repo = dashboard
    user_id = uuid.uuid4()
    paper = await paper_repo.create("Physics", 2022)
    for i in range(1, 4):
        q = await question_repo.create(
            paper.id, subject="Physics", year=2022, question_number=i, question_text=f"Q{i}",
            options={"A": "a"}, correct_answer=0,
        )
        await tutor_repo.create(question_id=q.id, user_id=user_id, role="assistant", content="help", is_correct=False)

    page, total = await service.list_tutor_history(user_id, limit=2, offset=0)
    assert total == 3
    assert len(page) == 2

    next_page, _ = await service.list_tutor_history(user_id, limit=2, offset=2)
    assert len(next_page) == 1


async def test_list_tutor_history_empty_for_new_user(dashboard) -> None:
    service, *_ = dashboard
    items, total = await service.list_tutor_history(uuid.uuid4(), limit=20, offset=0)
    assert items == []
    assert total == 0
