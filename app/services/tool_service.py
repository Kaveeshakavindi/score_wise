from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable

from app.core.config import Settings
from app.repositories.tool_invocation_repository import ToolInvocationRepository
from app.services.rag_service import RagService
from app.services.url_fetch import fetch_url_safely, strip_html

# Confines read_file to the project workspace, mirroring chatbot/chat/tools.py's
# path-traversal guard (Path(__file__).resolve().parents[2] from that file).
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    parameters: dict[str, Any]


@dataclass
class ToolCallResult:
    name: str
    args: dict[str, Any]
    status: str  # "ok" | "error"
    output: str
    duration_ms: int
    error_message: str | None = None


TOOL_DEFINITIONS: list[ToolDefinition] = [
    ToolDefinition(
        name="get_current_time",
        description="Return the current local time.",
        parameters={"type": "object", "properties": {}, "required": []},
    ),
    ToolDefinition(
        name="read_file",
        description="Read a local text file by path (workspace only).",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path relative to the project workspace."},
                "max_chars": {"type": "integer", "default": 8000},
            },
            "required": ["path"],
        },
    ),
    ToolDefinition(
        name="fetch_url",
        description="Fetch raw text content from a URL via HTTP GET (not indexed).",
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "http(s) URL to fetch."},
                "max_chars": {"type": "integer", "default": 2000},
                "timeout_s": {"type": "integer", "default": 8},
            },
            "required": ["url"],
        },
    ),
    ToolDefinition(
        name="read_url",
        description="Read a website URL, strip HTML, and index the cleaned text into this session's RAG store.",
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "http(s) URL to read."},
                "max_chars": {"type": "integer", "default": 8000},
                "timeout_s": {"type": "integer", "default": 8},
            },
            "required": ["url"],
        },
    ),
]

_TOOL_NAMES = {definition.name for definition in TOOL_DEFINITIONS}
INDEXING_TOOLS = {"read_file", "read_url"}


class ToolService:
    """Tool registry + sandboxed execution + audit logging (§9, §12). Tools are
    only ever invoked by the model inside ChatService's loop — never directly
    by a client (§6.6, explicit non-goal)."""

    def __init__(self, rag_service: RagService, invocation_repo: ToolInvocationRepository, settings: Settings) -> None:
        self._rag_service = rag_service
        self._invocation_repo = invocation_repo
        self._settings = settings

    def list_definitions(self) -> list[ToolDefinition]:
        return TOOL_DEFINITIONS

    async def execute(self, session_id: uuid.UUID, name: str, args: dict[str, Any]) -> ToolCallResult:
        start = time.perf_counter()
        try:
            if name not in _TOOL_NAMES:
                raise ValueError(f"Unknown tool '{name}'")
            handler = self._handlers()[name]
            output = await handler(session_id, args)
            duration_ms = int((time.perf_counter() - start) * 1000)
            await self._invocation_repo.create(session_id, name, args, "ok", duration_ms)
            return ToolCallResult(name=name, args=args, status="ok", output=output, duration_ms=duration_ms)
        except Exception as exc:  # noqa: BLE001 - tool failures are reported to the model, not raised
            duration_ms = int((time.perf_counter() - start) * 1000)
            error_message = str(exc)
            await self._invocation_repo.create(session_id, name, args, "error", duration_ms, error_message)
            return ToolCallResult(
                name=name,
                args=args,
                status="error",
                output=f"Error: tool execution failed: {error_message}",
                duration_ms=duration_ms,
                error_message=error_message,
            )

    def _handlers(self) -> dict[str, Callable[[uuid.UUID, dict[str, Any]], Awaitable[str]]]:
        return {
            "get_current_time": self._get_current_time,
            "read_file": self._read_file,
            "fetch_url": self._fetch_url,
            "read_url": self._read_url,
        }

    async def _get_current_time(self, session_id: uuid.UUID, args: dict[str, Any]) -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    async def _read_file(self, session_id: uuid.UUID, args: dict[str, Any]) -> str:
        path = args["path"]
        max_chars = int(args.get("max_chars", 8000))

        requested = Path(path)
        if not requested.is_absolute():
            requested = _PROJECT_ROOT / requested
        try:
            requested = requested.resolve()
            requested.relative_to(_PROJECT_ROOT)
        except Exception:
            return "Error: path is outside the project workspace."

        if not requested.exists():
            return "Error: file not found."
        if not requested.is_file():
            return "Error: path is not a file."

        text = await asyncio.to_thread(requested.read_text, "utf-8", "replace")
        if max_chars > 0:
            text = text[:max_chars]

        document = await self._rag_service.index_text(session_id, str(requested), text)
        chunk_count = await self._rag_service.chunk_count(document.id)
        return f"{text}\n\n[Indexed {chunk_count} chunks from {requested}]"

    async def _fetch_url(self, session_id: uuid.UUID, args: dict[str, Any]) -> str:
        url = args["url"]
        max_chars = int(args.get("max_chars", 2000))
        timeout_s = float(args.get("timeout_s", 8))

        result = await fetch_url_safely(url, max_bytes=self._settings.max_ingest_bytes, timeout_s=timeout_s)
        text = result.text[:max_chars] if max_chars > 0 else result.text
        if result.content_type:
            return f"Content-Type: {result.content_type}\n{text}"
        return text

    async def _read_url(self, session_id: uuid.UUID, args: dict[str, Any]) -> str:
        url = args["url"]
        max_chars = int(args.get("max_chars", 8000))
        timeout_s = float(args.get("timeout_s", 8))

        result = await fetch_url_safely(url, max_bytes=self._settings.max_ingest_bytes, timeout_s=timeout_s)
        text = strip_html(result.text)
        if max_chars > 0:
            text = text[:max_chars]

        document = await self._rag_service.index_text(session_id, url, text)
        chunk_count = await self._rag_service.chunk_count(document.id)
        return f"{text}\n\n[Indexed {chunk_count} chunks from {url}]"
