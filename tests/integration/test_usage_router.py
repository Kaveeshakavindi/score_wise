from __future__ import annotations

import httpx
import pytest

from app.core.deps import get_current_user, get_llm_usage_repository
from app.llm.anthropic_client import Usage
from app.main import app
from tests.fakes import FakeLlmUsageRepository

_HEADERS = {"Authorization": "Bearer test-token"}


@pytest.fixture
async def client(test_user):
    llm_usage_repo = FakeLlmUsageRepository()

    app.dependency_overrides[get_current_user] = lambda: test_user
    app.dependency_overrides[get_llm_usage_repository] = lambda: llm_usage_repo

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac, llm_usage_repo, test_user

    app.dependency_overrides.clear()


async def test_get_my_usage_unbudgeted_by_default(client) -> None:
    ac, llm_usage_repo, user = client
    await llm_usage_repo.record(
        user_id=user.id, feature="tutor_feedback", model="test-model",
        usage=Usage(input_tokens=100, output_tokens=20, total_tokens=120), request_id=None,
    )

    response = await ac.get("/api/v1/usage/me", headers=_HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert body["tokens_used_today"] == 120
    # DAILY_TOKEN_BUDGET isn't set in the test environment (see conftest.py) --
    # unlimited, not zero remaining.
    assert body["daily_budget"] is None
    assert body["tokens_remaining"] is None


async def test_get_my_usage_requires_auth() -> None:
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/api/v1/usage/me")
    assert response.status_code == 401
