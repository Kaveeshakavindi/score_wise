from __future__ import annotations

import uuid

import pytest
from langchain_core.messages import AIMessage

import app.services.chat_service as chat_service_module
from app.services.chat_service import ChatService
from tests.fakes import (
    FakeLlmUsageRepository,
    FakeMessageRepository,
    FakeRagService,
    FakeSessionRepository,
    FakeTitleService,
    FakeToolService,
)


class FakeLLM:
    """Canned AIMessage sequence, including a tool-call scenario, to test the
    tool loop in isolation from the real Anthropic API (§13)."""

    def __init__(self, responses: list[AIMessage]) -> None:
        self._responses = list(responses)

    async def ainvoke(self, messages):
        return self._responses.pop(0)


@pytest.fixture
def chat_service(
    settings, monkeypatch
) -> tuple[ChatService, FakeMessageRepository, FakeSessionRepository, FakeToolService, FakeLlmUsageRepository]:
    message_repo = FakeMessageRepository()
    session_repo = FakeSessionRepository()
    rag_service = FakeRagService()
    tool_service = FakeToolService()
    title_service = FakeTitleService()
    llm_usage_repo = FakeLlmUsageRepository()

    service = ChatService(
        message_repo, session_repo, rag_service, tool_service, title_service, llm_usage_repo, settings
    )
    return service, message_repo, session_repo, tool_service, llm_usage_repo


def _patch_llm(monkeypatch, responses: list[AIMessage]) -> None:
    fake = FakeLLM(responses)
    monkeypatch.setattr(chat_service_module, "get_llm_with_tools", lambda *a, **k: fake)


async def test_send_message_simple_turn_persists_both_messages_and_sets_title(chat_service, monkeypatch) -> None:
    service, message_repo, session_repo, tool_service, llm_usage_repo = chat_service
    session = await session_repo.create(uuid.uuid4())
    _patch_llm(monkeypatch, [AIMessage(content="Hello there!")])

    result = await service.send_message(session.id, "Name: Ada; Nickname: ada; Age: 30", "Hi")

    assert result.user_message.content == "Hi"
    assert result.assistant_message.content == "Hello there!"
    assert result.generated_title == "Fake Generated Title"
    assert session.title == "Fake Generated Title"  # first-turn title only fills when NULL
    assert tool_service.calls == []


async def test_send_message_runs_tool_loop_before_final_answer(chat_service, monkeypatch) -> None:
    service, message_repo, session_repo, tool_service, llm_usage_repo = chat_service
    session = await session_repo.create(uuid.uuid4())

    tool_call_response = AIMessage(
        content="",
        tool_calls=[{"name": "get_current_time", "args": {}, "id": "call_1"}],
    )
    final_response = AIMessage(content="It is currently that time.")
    _patch_llm(monkeypatch, [tool_call_response, final_response])

    result = await service.send_message(session.id, "Name: Ada; Nickname: ada; Age: 30", "What time is it?")

    assert tool_service.calls == [("get_current_time", {})]
    assert result.assistant_message.content == "It is currently that time."
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].status == "ok"


async def test_send_message_second_turn_does_not_overwrite_title(chat_service, monkeypatch) -> None:
    service, message_repo, session_repo, tool_service, llm_usage_repo = chat_service
    session = await session_repo.create(uuid.uuid4())
    session.title = "Existing Title"

    _patch_llm(monkeypatch, [AIMessage(content="First reply")])
    await service.send_message(session.id, "ctx", "First message")

    _patch_llm(monkeypatch, [AIMessage(content="Second reply")])
    result = await service.send_message(session.id, "ctx", "Second message")

    assert result.generated_title is None
    assert session.title == "Existing Title"


async def test_send_message_records_usage_for_each_llm_call_in_the_turn(chat_service, monkeypatch) -> None:
    service, message_repo, session_repo, tool_service, llm_usage_repo = chat_service
    session = await session_repo.create(uuid.uuid4())

    tool_call_response = AIMessage(
        content="",
        tool_calls=[{"name": "get_current_time", "args": {}, "id": "call_1"}],
        usage_metadata={"input_tokens": 100, "output_tokens": 10, "total_tokens": 110},
    )
    final_response = AIMessage(
        content="It is currently that time.",
        usage_metadata={"input_tokens": 120, "output_tokens": 8, "total_tokens": 128},
    )
    _patch_llm(monkeypatch, [tool_call_response, final_response])

    await service.send_message(session.id, "ctx", "What time is it?")

    # One event per ainvoke call in the tool loop -- not just the final answer.
    assert [e.total_tokens for e in llm_usage_repo.events] == [110, 128]
    assert all(e.feature == "chat" and e.user_id is None for e in llm_usage_repo.events)
