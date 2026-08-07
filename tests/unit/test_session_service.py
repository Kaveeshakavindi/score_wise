from __future__ import annotations

import uuid

import pytest

from app.core.exceptions import NotFoundError
from app.services.session_service import SessionService
from tests.fakes import FakeSessionRepository


@pytest.fixture
def session_service() -> SessionService:
    return SessionService(FakeSessionRepository())


async def test_create_and_get_owned(session_service: SessionService) -> None:
    user_id = uuid.uuid4()
    session = await session_service.create(user_id)
    fetched = await session_service.get_owned(user_id, session.id)
    assert fetched.id == session.id


async def test_get_owned_by_non_owner_raises_not_found(session_service: SessionService) -> None:
    owner_id = uuid.uuid4()
    other_user_id = uuid.uuid4()
    session = await session_service.create(owner_id)

    # 404, not 403, so as not to confirm resource existence to non-owners (§5).
    with pytest.raises(NotFoundError):
        await session_service.get_owned(other_user_id, session.id)


async def test_get_owned_missing_session_raises_not_found(session_service: SessionService) -> None:
    with pytest.raises(NotFoundError):
        await session_service.get_owned(uuid.uuid4(), uuid.uuid4())


async def test_rename_updates_title(session_service: SessionService) -> None:
    user_id = uuid.uuid4()
    session = await session_service.create(user_id)
    renamed = await session_service.rename(user_id, session.id, "New Title")
    assert renamed.title == "New Title"


async def test_list_for_user_only_returns_owned_sessions(session_service: SessionService) -> None:
    user_a = uuid.uuid4()
    user_b = uuid.uuid4()
    await session_service.create(user_a)
    await session_service.create(user_a)
    await session_service.create(user_b)

    items, total = await session_service.list_for_user(user_a, limit=20, offset=0)
    assert total == 2
    assert all(s.user_id == user_a for s in items)


async def test_delete_all_only_removes_owned_sessions(session_service: SessionService) -> None:
    user_a = uuid.uuid4()
    user_b = uuid.uuid4()
    await session_service.create(user_a)
    session_b = await session_service.create(user_b)

    await session_service.delete_all(user_a)

    items, total = await session_service.list_for_user(user_a, limit=20, offset=0)
    assert total == 0
    fetched_b = await session_service.get_owned(user_b, session_b.id)
    assert fetched_b.id == session_b.id
