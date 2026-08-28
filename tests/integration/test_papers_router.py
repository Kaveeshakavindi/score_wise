from __future__ import annotations

import uuid

import httpx
import pytest

from app.core.deps import get_current_user, get_paper_repository, get_question_repository, get_redis
from app.main import app
from tests.fakes import FakePaperRepository, FakeQuestionRepository, FakeRedis

_HEADERS = {"Authorization": "Bearer test-token"}


@pytest.fixture
async def client(test_user):
    question_repo = FakeQuestionRepository()
    paper_repo = FakePaperRepository(question_repo=question_repo)

    app.dependency_overrides[get_current_user] = lambda: test_user
    app.dependency_overrides[get_paper_repository] = lambda: paper_repo
    app.dependency_overrides[get_question_repository] = lambda: question_repo
    app.dependency_overrides[get_redis] = lambda: FakeRedis()

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac, paper_repo, question_repo

    app.dependency_overrides.clear()


async def test_list_papers_filters_by_subject_query_param(client) -> None:
    ac, paper_repo, _ = client
    await paper_repo.create("Physics", 2022)
    await paper_repo.create("Chemistry", 2022)

    response = await ac.get("/api/v1/papers", params={"subject": "Physics"}, headers=_HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["subject"] == "Physics"


async def test_list_papers_includes_question_count(client) -> None:
    ac, paper_repo, question_repo = client
    paper = await paper_repo.create("Physics", 2022)
    for i in range(1, 4):
        await question_repo.create(
            paper.id, subject="Physics", year=2022, question_number=i, question_text=f"Q{i}",
            options={"A": "x"}, correct_answer=0,
        )

    response = await ac.get("/api/v1/papers", headers=_HEADERS)

    assert response.status_code == 200
    assert response.json()["items"][0]["question_count"] == 3


async def test_list_papers_requires_auth() -> None:
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/api/v1/papers")
    assert response.status_code == 401


async def test_list_paper_questions_omits_correct_answer_from_response(client) -> None:
    ac, paper_repo, question_repo = client
    paper = await paper_repo.create("Physics", 2022)
    await question_repo.create(
        paper.id, subject="Physics", year=2022, question_number=1, question_text="What is force?",
        options={"A": "mass", "B": "mass x acceleration"}, correct_answer=1,
    )

    response = await ac.get(f"/api/v1/papers/{paper.id}/questions", headers=_HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    question = body["items"][0]
    assert question["question_text"] == "What is force?"
    assert "correct_answer" not in question


async def test_list_paper_questions_missing_paper_returns_404(client) -> None:
    ac, _, _ = client
    response = await ac.get(f"/api/v1/papers/{uuid.uuid4()}/questions", headers=_HEADERS)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
