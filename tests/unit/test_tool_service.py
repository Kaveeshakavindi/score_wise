from __future__ import annotations

import uuid

import pytest

from app.services.tool_service import ToolService
from tests.fakes import FakeRagService, FakeToolInvocationRepository


@pytest.fixture
def tool_service(settings) -> ToolService:
    return ToolService(FakeRagService(), FakeToolInvocationRepository(), settings)


async def test_get_current_time_returns_ok(tool_service: ToolService) -> None:
    result = await tool_service.execute(uuid.uuid4(), "get_current_time", {})
    assert result.status == "ok"
    assert result.output


async def test_read_file_blocks_path_traversal(tool_service: ToolService) -> None:
    result = await tool_service.execute(uuid.uuid4(), "read_file", {"path": "../../../etc/passwd"})
    assert result.status == "ok"  # tool itself didn't error; it returned a safe message
    assert "outside the project workspace" in result.output


async def test_read_file_missing_file_reports_not_found(tool_service: ToolService) -> None:
    result = await tool_service.execute(uuid.uuid4(), "read_file", {"path": "definitely-does-not-exist.txt"})
    assert "not found" in result.output


async def test_unknown_tool_is_recorded_as_error(tool_service: ToolService) -> None:
    result = await tool_service.execute(uuid.uuid4(), "not_a_real_tool", {})
    assert result.status == "error"


async def test_read_file_indexes_into_rag(tool_service: ToolService) -> None:
    session_id = uuid.uuid4()
    # pyproject.toml is a real, small, readable file inside the workspace.
    result = await tool_service.execute(session_id, "read_file", {"path": "pyproject.toml"})
    assert result.status == "ok"
    assert "Indexed" in result.output
    assert tool_service._rag_service.indexed  # noqa: SLF001 - inspecting the fake's recorded calls
