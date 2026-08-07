from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from app.core.deps import CurrentUser, get_session_service, rate_limit_per_user
from app.schemas.common import Page
from app.schemas.session import SessionListItem, SessionOut, SessionRenameRequest
from app.services.session_service import SessionService

router = APIRouter(
    prefix="/api/v1/sessions",
    tags=["sessions"],
    dependencies=[Depends(rate_limit_per_user("sessions_generic", limit=120, window_s=60))],
)

SessionServiceDep = Annotated[SessionService, Depends(get_session_service)]


@router.post("", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
async def create_session(current_user: CurrentUser, session_service: SessionServiceDep) -> SessionOut:
    """Create a new chat session. Requires auth."""
    session = await session_service.create(current_user.id)
    return SessionOut.model_validate(session)


@router.get("", response_model=Page[SessionListItem])
async def list_sessions(
    current_user: CurrentUser,
    session_service: SessionServiceDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[SessionListItem]:
    """List caller's sessions, newest-active first. Requires auth."""
    items, total = await session_service.list_for_user(current_user.id, limit=limit, offset=offset)
    return Page(items=[SessionListItem.model_validate(s) for s in items], total=total, limit=limit, offset=offset)


@router.get("/{session_id}", response_model=SessionOut)
async def get_session(session_id: UUID, current_user: CurrentUser, session_service: SessionServiceDep) -> SessionOut:
    """Get one session. Requires auth + ownership (404 if not owner or missing)."""
    session = await session_service.get_owned(current_user.id, session_id)
    return SessionOut.model_validate(session)


@router.patch("/{session_id}", response_model=SessionOut)
async def rename_session(
    session_id: UUID, body: SessionRenameRequest, current_user: CurrentUser, session_service: SessionServiceDep
) -> SessionOut:
    """Rename session title. Requires auth + ownership."""
    session = await session_service.rename(current_user.id, session_id, body.title)
    return SessionOut.model_validate(session)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(session_id: UUID, current_user: CurrentUser, session_service: SessionServiceDep) -> Response:
    """Delete one session (cascades messages + RAG chunks). Requires auth + ownership."""
    await session_service.delete(current_user.id, session_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_all_sessions(current_user: CurrentUser, session_service: SessionServiceDep) -> Response:
    """Delete ALL of caller's sessions. Requires auth."""
    await session_service.delete_all(current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
