from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.core.deps import CurrentUser, get_chat_service, get_message_repository, get_session_service, rate_limit_per_user
from app.db.models import User
from app.repositories.message_repository import MessageRepository
from app.schemas.common import Page
from app.schemas.message import MessageOut, SendMessageRequest, SendMessageResponse, ToolCallSummary
from app.services.chat_service import ChatService
from app.services.session_service import SessionService

router = APIRouter(prefix="/api/v1/sessions/{session_id}/messages", tags=["messages"])

SessionServiceDep = Annotated[SessionService, Depends(get_session_service)]
MessageRepoDep = Annotated[MessageRepository, Depends(get_message_repository)]
ChatServiceDep = Annotated[ChatService, Depends(get_chat_service)]


def _format_user_context(user: User) -> str:
    # Mirrors chatbot/main.py's _format_user_context, injected into the system prompt.
    return f"Name: {user.name}; Nickname: {user.nickname}; Age: {user.age}"


@router.get("", response_model=Page[MessageOut])
async def list_messages(
    session_id: UUID,
    current_user: CurrentUser,
    session_service: SessionServiceDep,
    message_repo: MessageRepoDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[MessageOut]:
    """Full history, oldest -> newest. Requires auth + session ownership."""
    await session_service.get_owned(current_user.id, session_id)
    items = await message_repo.list_by_session(session_id, limit=limit, offset=offset)
    total = await message_repo.count_by_session(session_id)
    return Page(items=[MessageOut.model_validate(m) for m in items], total=total, limit=limit, offset=offset)


@router.post(
    "",
    response_model=SendMessageResponse,
    status_code=201,
    dependencies=[Depends(rate_limit_per_user("messages_send", limit=20, window_s=60))],
)
async def send_message(
    session_id: UUID,
    body: SendMessageRequest,
    current_user: CurrentUser,
    session_service: SessionServiceDep,
    chat_service: ChatServiceDep,
) -> SendMessageResponse:
    """Send a message; the server runs the full LLM+tool+RAG turn synchronously
    and returns the assistant reply. Requires auth + session ownership.
    20 req/min per user (§8 — each call is a paid LLM request)."""
    await session_service.get_owned(current_user.id, session_id)
    result = await chat_service.send_message(session_id, _format_user_context(current_user), body.content)
    return SendMessageResponse(
        user_message=MessageOut.model_validate(result.user_message),
        assistant_message=MessageOut.model_validate(result.assistant_message),
        tool_calls=[
            ToolCallSummary(name=c.name, args=c.args, status=c.status, duration_ms=c.duration_ms)
            for c in result.tool_calls
        ],
        generated_title=result.generated_title,
    )
