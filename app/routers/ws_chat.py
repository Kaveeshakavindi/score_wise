from __future__ import annotations

import asyncio
import json
from uuid import UUID

import jwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.config import get_settings
from app.core.exceptions import RateLimitedError
from app.core.logging import logger, set_session_id, set_user_id
from app.core.security import decode_access_token
from app.db.base import get_session_factory
from app.db.models import User
from app.repositories.llm_usage_repository import LlmUsageRepository
from app.repositories.message_repository import MessageRepository
from app.repositories.rag_chunk_repository import RagChunkRepository
from app.repositories.session_repository import SessionRepository
from app.repositories.tool_invocation_repository import ToolInvocationRepository
from app.repositories.user_repository import UserRepository
from app.services.chat_service import ChatService
from app.services.rag_service import RagService
from app.services.title_service import TitleService
from app.services.tool_service import ToolService

router = APIRouter()

_RATE_LIMIT_PER_MIN = 20
_RATE_WINDOW_S = 60


def _extract_token(websocket: WebSocket) -> str | None:
    # Preferred: Sec-WebSocket-Protocol: bearer.<access_token> — doesn't leak
    # into server access logs/proxies the way query strings do (§5).
    proto_header = websocket.headers.get("sec-websocket-protocol", "")
    for candidate in proto_header.split(","):
        candidate = candidate.strip()
        if candidate.startswith("bearer."):
            return candidate[len("bearer.") :]
    # Fallback: ?token=... query parameter.
    return websocket.query_params.get("token")


def _format_user_context(user: User) -> str:
    return f"Name: {user.name}; Nickname: {user.nickname}; Age: {user.age}"


async def _safe_send(websocket: WebSocket, payload: dict) -> None:
    try:
        await websocket.send_text(json.dumps(payload))
    except Exception:
        # Client disconnected mid-turn — the turn still completes server-side
        # and is persisted; a reconnecting client fetches it via
        # GET /messages (§7 reliability note).
        pass


@router.websocket("/api/v1/sessions/{session_id}/stream")
async def stream_chat(websocket: WebSocket, session_id: UUID) -> None:
    settings = get_settings()
    token = _extract_token(websocket)
    if not token:
        await websocket.close(code=4401)
        return

    try:
        payload = decode_access_token(token, settings)
        user_id = UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        await websocket.close(code=4401)
        return

    session_factory = get_session_factory()
    async with session_factory() as auth_db:
        user = await UserRepository(auth_db).get_by_id(user_id)
        if user is None:
            await websocket.close(code=4401)
            return

        chat_session = await SessionRepository(auth_db).get_by_id(session_id)
        if chat_session is None:
            await websocket.close(code=4404)
            return
        if chat_session.user_id != user.id:
            await websocket.close(code=4403)
            return

    await websocket.accept(subprotocol="bearer")
    set_user_id(str(user.id))
    set_session_id(str(session_id))
    logger.info("ws_connected", user_id=str(user.id), session_id=str(session_id))

    turn_in_flight = False
    user_context = _format_user_context(user)

    async def run_turn(content: str) -> None:
        nonlocal turn_in_flight
        try:
            async with session_factory() as db:
                chat_service = ChatService(
                    MessageRepository(db),
                    SessionRepository(db),
                    RagService(RagChunkRepository(db), settings),
                    ToolService(
                        RagService(RagChunkRepository(db), settings),
                        ToolInvocationRepository(db),
                        settings,
                    ),
                    TitleService(settings, LlmUsageRepository(db)),
                    LlmUsageRepository(db),
                    settings,
                )
                try:
                    async for event in chat_service.stream_turn(session_id, user_context, content):
                        await _safe_send(websocket, event)
                    await db.commit()
                except Exception as exc:
                    await db.rollback()
                    logger.exception("ws_turn_failed", error=str(exc))
                    await _safe_send(
                        websocket, {"type": "error", "code": "llm_upstream_error", "message": str(exc)}
                    )
        finally:
            turn_in_flight = False

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                frame = json.loads(raw)
            except json.JSONDecodeError:
                await _safe_send(websocket, {"type": "error", "code": "invalid_frame", "message": "Malformed JSON."})
                continue

            if frame.get("type") != "message" or not isinstance(frame.get("content"), str) or not frame["content"].strip():
                await _safe_send(
                    websocket,
                    {"type": "error", "code": "invalid_frame", "message": "Expected {'type':'message','content':str}."},
                )
                continue

            if turn_in_flight:
                # Server serializes turns per connection — no client-side race
                # between two concurrent sends (§7).
                await websocket.close(code=4409)
                return

            try:
                await _enforce_rate_limit(user.id)
            except RateLimitedError as exc:
                await _safe_send(websocket, {"type": "error", "code": "rate_limited", "message": exc.message})
                continue

            turn_in_flight = True
            asyncio.create_task(run_turn(frame["content"]))
    except WebSocketDisconnect:
        logger.info("ws_disconnected", user_id=str(user.id), session_id=str(session_id))


async def _enforce_rate_limit(user_id: UUID) -> None:
    from app.core.deps import _check_rate_limit, get_redis  # local import avoids a routing-time cycle

    settings = get_settings()
    redis_client = get_redis(settings)
    key = f"ratelimit:ws_messages:user:{user_id}"
    await _check_rate_limit(redis_client, key, _RATE_LIMIT_PER_MIN, _RATE_WINDOW_S)
