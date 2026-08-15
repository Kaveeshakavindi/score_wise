from __future__ import annotations

import uuid

import httpx
import pytest

from app.core.deps import (
    get_attempt_repository,
    get_current_user,
    get_paper_repository,
    get_question_repository,
    get_redis,
)
from app.main import app
from tests.fakes import FakeAttemptRepository, FakePaperRepository, FakeQuestionRepository, FakeRedis

_HEADERS = {"Authorization": "Bearer test-token"}


@pytest.fixture
async def client(test_user):
    paper_repo = FakePaperRepository()
    question_repo = FakeQuestionRepository()
    attempt_repo = FakeAttemptRepository()

    app.dependency_overrides[get_current_user] = lambda: test_user
    app.dependency_overrides[get_paper_repository] = lambda: paper_repo
    app.dependency_overrides[get_question_repository] = lambda: question_repo
    app.dependency_overrides[get_attempt_repository] = lambda: attempt_repo
    app.dependency_overrides[get_redis] = lambda: FakeRedis()

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac, paper_repo, question_repo

    app.dependency_overrides.clear()


async def test_submit_attempt_returns_score_and_per_question_results(client) -> None:
    ac, paper_repo, question_repo = client
    paper = await paper_repo.create("Physics", 2022)
    q1 = await question_repo.create(
        paper.id, subject="Physics", year=2022, question_number=1, question_text="Q1",
        options={"A": "a", "B": "b"}, correct_answer=0,
    )
    q2 = await question_repo.create(
        paper.id, subject="Physics", year=2022, question_number=2, question_text="Q2",
        options={"A": "a", "B": "b"}, correct_answer=1,
    )

    response = await ac.post(
        "/api/v1/attempts",
        json={
            "paper_id": str(paper.id),
            "answers": [
                {"question_id": str(q1.id), "selected_answer": 0},
                {"question_id": str(q2.id), "selected_answer": 0},
            ],
        },
        headers=_HEADERS,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["score"] == 1
    assert body["total"] == 2
    results_by_question = {r["question_id"]: r for r in body["results"]}
    assert results_by_question[str(q1.id)]["is_correct"] is True
    assert results_by_question[str(q2.id)]["is_correct"] is False
    assert results_by_question[str(q2.id)]["correct_answer"] == 1


async def test_submit_attempt_missing_paper_returns_404(client) -> None:
    ac, _, _ = client
    response = await ac.post(
        "/api/v1/attempts",
        json={"paper_id": str(uuid.uuid4()), "answers": [{"question_id": str(uuid.uuid4()), "selected_answer": 0}]},
        headers=_HEADERS,
    )
    assert response.status_code == 404


async def test_submit_attempt_empty_answers_returns_422(client) -> None:
    ac, paper_repo, _ = client
    paper = await paper_repo.create("Physics", 2022)

    response = await ac.post(
        "/api/v1/attempts", json={"paper_id": str(paper.id), "answers": []}, headers=_HEADERS
    )
    assert response.status_code == 422


async def test_submit_attempt_requires_auth() -> None:
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post("/api/v1/attempts", json={"paper_id": str(uuid.uuid4()), "answers": []})
    assert response.status_code == 401
