from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import app.core.deps as deps_module
import app.routers.ws_chat as ws_chat_module
from app.core.security import create_access_token
from app.db.models import ChatSession, User
from app.main import app
from tests.fakes import FakeRedis

# --- fakes wiring the WS handler's directly-instantiated collaborators (it
# bypasses app.core.deps entirely — see routers/ws_chat.py) without a real
# Postgres connection ---


class _FakeDb:
    async def commit(self) -> None:
        pass

    async def rollback(self) -> None:
        pass


class _FakeSessionCtx:
    def __init__(self, value: _FakeDb) -> None:
        self._value = value

    async def __aenter__(self) -> _FakeDb:
        return self._value

    async def __aexit__(self, *exc: object) -> bool:
        return False


def _fake_session_factory():
    # Mirrors app.db.base.get_session_factory()'s real shape: it returns a
    # callable ("the factory") which is itself called per `async with` block
    # to produce a fresh session context (router does `factory()` then
    # `async with factory() as db:`).
    return lambda: _FakeSessionCtx(_FakeDb())


class _FakeUserRepo:
    def __init__(self, users: list[User]) -> None:
        self._by_id = {u.id: u for u in users}

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return self._by_id.get(user_id)


class _FakeSessionRepo:
    def __init__(self, session: ChatSession) -> None:
        self._session = session

    async def get_by_id(self, session_id: uuid.UUID) -> ChatSession | None:
        return self._session if session_id == self._session.id else None


class _ScriptedChatService:
    """Replaces the real ChatService entirely so the WS test asserts on the
    exact frame sequence from api.md §7 without touching the LLM or DB."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    async def stream_turn(self, session_id: uuid.UUID, user_context: str, content: str):
        yield {"type": "ack", "user_message_id": "m1"}
        yield {"type": "tool_call", "name": "get_current_time", "args": {}, "call_id": "c1"}
        yield {"type": "tool_result", "call_id": "c1", "status": "ok", "summary": "It is now."}
        yield {"type": "token", "content": "Hi"}
        yield {"type": "token", "content": " there"}
        yield {"type": "done", "assistant_message_id": "m2", "generated_title": None}


def _make_user(nickname: str) -> User:
    user = User(id=uuid.uuid4(), name=nickname.title(), nickname=nickname, password_hash="x", age=30)
    user.created_at = datetime.now(timezone.utc)
    return user


@pytest.fixture
def ws_user() -> User:
    return _make_user("wsuser")


@pytest.fixture
def other_user() -> User:
    return _make_user("otheruser")


@pytest.fixture
def ws_chat_session(ws_user: User) -> ChatSession:
    now = datetime.now(timezone.utc)
    return ChatSession(id=uuid.uuid4(), user_id=ws_user.id, title=None, created_at=now, last_active=now)


@pytest.fixture
def ws_client(monkeypatch, ws_user: User, other_user: User, ws_chat_session: ChatSession):
    monkeypatch.setattr(ws_chat_module, "get_session_factory", _fake_session_factory)
    monkeypatch.setattr(ws_chat_module, "UserRepository", lambda db: _FakeUserRepo([ws_user, other_user]))
    monkeypatch.setattr(ws_chat_module, "SessionRepository", lambda db: _FakeSessionRepo(ws_chat_session))
    monkeypatch.setattr(ws_chat_module, "ChatService", _ScriptedChatService)
    # _enforce_rate_limit does a function-local `from app.core.deps import get_redis`,
    # so the patch target is deps_module.get_redis itself, not ws_chat_module's.
    monkeypatch.setattr(deps_module, "get_redis", lambda settings: FakeRedis())

    with TestClient(app) as test_client:
        yield test_client


def _token_for(settings, user: User) -> str:
    token, _ = create_access_token(str(user.id), user.nickname, settings)
    return token


def test_ws_rejects_missing_token_with_4401(ws_client: TestClient, ws_chat_session: ChatSession) -> None:
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with ws_client.websocket_connect(f"/api/v1/sessions/{ws_chat_session.id}/stream"):
            pass
    assert exc_info.value.code == 4401


def test_ws_rejects_invalid_token_with_4401(ws_client: TestClient, ws_chat_session: ChatSession) -> None:
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with ws_client.websocket_connect(
            f"/api/v1/sessions/{ws_chat_session.id}/stream", subprotocols=["bearer.not-a-real-token"]
        ):
            pass
    assert exc_info.value.code == 4401


def test_ws_rejects_missing_session_with_4404(ws_client: TestClient, settings, ws_user: User) -> None:
    token = _token_for(settings, ws_user)
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with ws_client.websocket_connect(
            f"/api/v1/sessions/{uuid.uuid4()}/stream", subprotocols=[f"bearer.{token}"]
        ):
            pass
    assert exc_info.value.code == 4404


def test_ws_rejects_non_owner_with_4403(
    ws_client: TestClient, settings, other_user: User, ws_chat_session: ChatSession
) -> None:
    token = _token_for(settings, other_user)
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with ws_client.websocket_connect(
            f"/api/v1/sessions/{ws_chat_session.id}/stream", subprotocols=[f"bearer.{token}"]
        ):
            pass
    assert exc_info.value.code == 4403


def test_ws_streams_ack_tool_events_tokens_then_done(
    ws_client: TestClient, settings, ws_user: User, ws_chat_session: ChatSession
) -> None:
    token = _token_for(settings, ws_user)
    with ws_client.websocket_connect(
        f"/api/v1/sessions/{ws_chat_session.id}/stream", subprotocols=[f"bearer.{token}"]
    ) as ws:
        ws.send_text(json.dumps({"type": "message", "content": "What time is it?"}))
        frames = [json.loads(ws.receive_text()) for _ in range(6)]

    # §7 ordering: ack -> tool_call* -> tool_result* -> token* -> done
    assert [f["type"] for f in frames] == ["ack", "tool_call", "tool_result", "token", "token", "done"]
    assert frames[0]["user_message_id"] == "m1"
    assert "".join(f["content"] for f in frames if f["type"] == "token") == "Hi there"
    assert frames[-1]["assistant_message_id"] == "m2"


def test_ws_invalid_frame_returns_error_event_without_closing(
    ws_client: TestClient, settings, ws_user: User, ws_chat_session: ChatSession
) -> None:
    token = _token_for(settings, ws_user)
    with ws_client.websocket_connect(
        f"/api/v1/sessions/{ws_chat_session.id}/stream", subprotocols=[f"bearer.{token}"]
    ) as ws:
        ws.send_text(json.dumps({"type": "not_a_message"}))
        frame = json.loads(ws.receive_text())

        assert frame == {
            "type": "error",
            "code": "invalid_frame",
            "message": "Expected {'type':'message','content':str}.",
        }

        # connection survives an invalid frame — a valid one still works after it
        ws.send_text(json.dumps({"type": "message", "content": "hi"}))
        next_frame = json.loads(ws.receive_text())
        assert next_frame["type"] == "ack"
