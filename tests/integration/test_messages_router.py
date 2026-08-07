from __future__ import annotations

import uuid

import httpx
import pytest
from langchain_core.messages import AIMessage

import app.services.chat_service as chat_service_module
from app.core.deps import (
    get_current_user,
    get_message_repository,
    get_rag_service,
    get_redis,
    get_session_repository,
    get_title_service,
    get_tool_service,
)
from app.main import app
from tests.fakes import (
    FakeMessageRepository,
    FakeRagService,
    FakeRedis,
    FakeSessionRepository,
    FakeTitleService,
    FakeToolService,
)

_HEADERS = {"Authorization": "Bearer test-token"}


class _FakeLLM:
    """Canned AIMessage sequence, same technique as the ChatService unit tests
    (§13) — no real Anthropic call happens in this router test either."""

    def __init__(self, responses: list[AIMessage]) -> None:
        self._responses = list(responses)

    async def ainvoke(self, messages):
        return self._responses.pop(0)


@pytest.fixture
async def client(test_user, monkeypatch):
    fake_session_repo = FakeSessionRepository()
    fake_message_repo = FakeMessageRepository()

    app.dependency_overrides[get_current_user] = lambda: test_user
    app.dependency_overrides[get_session_repository] = lambda: fake_session_repo
    app.dependency_overrides[get_message_repository] = lambda: fake_message_repo
    app.dependency_overrides[get_rag_service] = lambda: FakeRagService()
    app.dependency_overrides[get_tool_service] = lambda: FakeToolService()
    app.dependency_overrides[get_title_service] = lambda: FakeTitleService()
    app.dependency_overrides[get_redis] = lambda: FakeRedis()

    monkeypatch.setattr(
        chat_service_module,
        "get_llm_with_tools",
        lambda *a, **k: _FakeLLM([AIMessage(content="Hi there!")]),
    )

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac, fake_session_repo, fake_message_repo

    app.dependency_overrides.clear()


async def test_send_message_persists_turn_and_returns_reply(client, test_user) -> None:
    ac, session_repo, _ = client
    session = await session_repo.create(test_user.id)

    response = await ac.post(f"/api/v1/sessions/{session.id}/messages", json={"content": "Hello"}, headers=_HEADERS)
    assert response.status_code == 201
    body = response.json()
    assert body["user_message"]["content"] == "Hello"
    assert body["user_message"]["role"] == "user"
    assert body["assistant_message"]["content"] == "Hi there!"
    assert body["assistant_message"]["role"] == "assistant"
    assert body["generated_title"] == "Fake Generated Title"  # first turn generates+persists a title


async def test_send_message_not_owner_returns_404(client) -> None:
    ac, session_repo, _ = client
    other_session = await session_repo.create(uuid.uuid4())

    response = await ac.post(
        f"/api/v1/sessions/{other_session.id}/messages", json={"content": "Hi"}, headers=_HEADERS
    )
    assert response.status_code == 404


async def test_send_message_empty_content_returns_422(client, test_user) -> None:
    ac, session_repo, _ = client
    session = await session_repo.create(test_user.id)

    response = await ac.post(f"/api/v1/sessions/{session.id}/messages", json={"content": ""}, headers=_HEADERS)
    assert response.status_code == 422


async def test_list_messages_returns_full_history_oldest_first(client, test_user) -> None:
    ac, session_repo, message_repo = client
    session = await session_repo.create(test_user.id)
    await message_repo.create(session.id, "user", "First")
    await message_repo.create(session.id, "assistant", "Second")

    response = await ac.get(f"/api/v1/sessions/{session.id}/messages", headers=_HEADERS)
    assert response.status_code == 200
    body = response.json()
    assert [m["content"] for m in body["items"]] == ["First", "Second"]
    assert body["total"] == 2


async def test_list_messages_not_owner_returns_404(client) -> None:
    ac, session_repo, _ = client
    other_session = await session_repo.create(uuid.uuid4())

    response = await ac.get(f"/api/v1/sessions/{other_session.id}/messages", headers=_HEADERS)
    assert response.status_code == 404
