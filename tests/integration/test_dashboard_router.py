from __future__ import annotations

import httpx
import pytest

from app.core.deps import (
    get_attempt_repository,
    get_current_user,
    get_question_repository,
    get_redis,
    get_tutor_message_repository,
)
from app.main import app
from tests.fakes import (
    FakeAttemptRepository,
    FakePaperRepository,
    FakeQuestionRepository,
    FakeRedis,
    FakeTutorMessageRepository,
)

_HEADERS = {"Authorization": "Bearer test-token"}


@pytest.fixture
async def client(test_user):
    paper_repo = FakePaperRepository()
    question_repo = FakeQuestionRepository()
    attempt_repo = FakeAttemptRepository(paper_repo=paper_repo, question_repo=question_repo)
    tutor_repo = FakeTutorMessageRepository()

    app.dependency_overrides[get_current_user] = lambda: test_user
    app.dependency_overrides[get_attempt_repository] = lambda: attempt_repo
    app.dependency_overrides[get_tutor_message_repository] = lambda: tutor_repo
    app.dependency_overrides[get_question_repository] = lambda: question_repo
    app.dependency_overrides[get_redis] = lambda: FakeRedis()

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac, test_user, paper_repo, question_repo, attempt_repo, tutor_repo

    app.dependency_overrides.clear()


async def test_summary_reflects_submitted_attempts(client) -> None:
    ac, user, paper_repo, question_repo, attempt_repo, _ = client
    paper = await paper_repo.create("Physics", 2022)
    q1 = await question_repo.create(
        paper.id, subject="Physics", year=2022, question_number=1, question_text="Q1",
        options={"A": "a"}, correct_answer=0,
    )
    q2 = await question_repo.create(
        paper.id, subject="Physics", year=2022, question_number=2, question_text="Q2",
        options={"A": "a"}, correct_answer=0,
    )
    attempt = await attempt_repo.create(user_id=user.id, paper_id=paper.id, score=1, total=2)
    await attempt_repo.add_answer(attempt_id=attempt.id, question_id=q1.id, selected_answer=0, is_correct=True)
    await attempt_repo.add_answer(attempt_id=attempt.id, question_id=q2.id, selected_answer=1, is_correct=False)

    response = await ac.get("/api/v1/dashboard/summary", headers=_HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert body["attempts_count"] == 1
    assert body["overall_correct"] == 1
    assert body["overall_total"] == 2
    assert body["subjects"] == [{"subject": "Physics", "correct": 1, "total": 2}]
    assert len(body["trend"]) == 1
    assert body["trend"][0]["attempt_id"] == str(attempt.id)
    assert body["mistakes_total"] == 1
    assert body["mistakes_unreviewed"] == 1
    assert body["tutor_helped_count"] == 0
    # Zero-filled fixed 14-day window, no tutor activity recorded above.
    assert len(body["tutor_activity"]) == 14
    assert all(a["count"] == 0 for a in body["tutor_activity"])


async def test_tutor_history_includes_question_details_and_messages(client) -> None:
    ac, user, paper_repo, question_repo, attempt_repo, tutor_repo = client
    paper = await paper_repo.create("Chemistry", 2021)
    q = await question_repo.create(
        paper.id, subject="Chemistry", year=2021, question_number=1, question_text="What is X?",
        options={"A": "a", "B": "b"}, correct_answer=1,
    )
    attempt = await attempt_repo.create(user_id=user.id, paper_id=paper.id, score=0, total=1)
    await attempt_repo.add_answer(attempt_id=attempt.id, question_id=q.id, selected_answer=0, is_correct=False)
    await tutor_repo.create(question_id=q.id, user_id=user.id, role="assistant", content="Because...", is_correct=False)

    response = await ac.get("/api/v1/dashboard/tutor-history", headers=_HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["question_id"] == str(q.id)
    assert item["subject"] == "Chemistry"
    assert item["question_text"] == "What is X?"
    assert [m["content"] for m in item["messages"]] == ["Because..."]


async def test_tutor_history_excludes_undiscussed_wrong_answers(client) -> None:
    ac, user, paper_repo, question_repo, attempt_repo, tutor_repo = client
    paper = await paper_repo.create("Physics", 2022)
    discussed = await question_repo.create(
        paper.id, subject="Physics", year=2022, question_number=1, question_text="P1",
        options={"A": "a"}, correct_answer=0,
    )
    undiscussed = await question_repo.create(
        paper.id, subject="Physics", year=2022, question_number=2, question_text="P2",
        options={"A": "a"}, correct_answer=0,
    )
    attempt = await attempt_repo.create(user_id=user.id, paper_id=paper.id, score=0, total=2)
    await attempt_repo.add_answer(attempt_id=attempt.id, question_id=discussed.id, selected_answer=1, is_correct=False)
    await attempt_repo.add_answer(attempt_id=attempt.id, question_id=undiscussed.id, selected_answer=1, is_correct=False)
    await tutor_repo.create(question_id=discussed.id, user_id=user.id, role="assistant", content="help", is_correct=False)

    response = await ac.get("/api/v1/dashboard/tutor-history", headers=_HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["question_id"] == str(discussed.id)


async def test_dashboard_endpoints_require_auth() -> None:
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/api/v1/dashboard/summary")
            response2 = await ac.get("/api/v1/dashboard/tutor-history")
    assert response.status_code == 401
    assert response2.status_code == 401
