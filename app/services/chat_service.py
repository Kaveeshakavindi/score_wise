from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, AsyncIterator

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import StructuredTool

from app.core.config import Settings
from app.core.logging import get_request_id, logger
from app.db.models import Message
from app.llm.anthropic_client import astream_text_events, get_llm_with_tools, get_text_content, get_usage
from app.repositories.llm_usage_repository import LlmUsageRepository
from app.repositories.message_repository import MessageRepository
from app.repositories.session_repository import SessionRepository
from app.services.rag_service import RagService
from app.services.title_service import TitleService
from app.services.tool_service import INDEXING_TOOLS, TOOL_DEFINITIONS, ToolCallResult, ToolService

_SYSTEM_INSTRUCTIONS = (
    "You are a helpful assistant. User info: {user_context}. Use tools when helpful. "
    "If a file path is provided, use read_file to load it. If a URL is provided, use read_url to load it. "
    "Answer based on the retrieved content."
)


@dataclass(frozen=True)
class ChatTurnResult:
    user_message: Message
    assistant_message: Message
    tool_calls: list[ToolCallResult]
    generated_title: str | None


class ChatService:
    """Orchestration: prompt build -> LLM -> tool loop -> RAG -> persist.
    Async equivalent of chatbot/chat/loop.py's run_chat, split into a
    synchronous full-turn path (HTTP) and a token-streaming path (WebSocket)."""

    def __init__(
        self,
        message_repo: MessageRepository,
        session_repo: SessionRepository,
        rag_service: RagService,
        tool_service: ToolService,
        title_service: TitleService,
        llm_usage_repo: LlmUsageRepository,
        settings: Settings,
    ) -> None:
        self._messages = message_repo
        self._sessions = session_repo
        self._rag = rag_service
        self._tools = tool_service
        self._titles = title_service
        self._llm_usage = llm_usage_repo
        self._settings = settings

    async def _record_usage(self, response: BaseMessage) -> None:
        # user_id=None: same reasoning as TitleService._record_usage — this
        # chat feature has no user-ownership model resolved at this layer to
        # attribute the call to. Still counted toward total app-wide spend.
        usage = get_usage(response)
        if usage is None:
            return
        try:
            await self._llm_usage.record(
                user_id=None, feature="chat", model=self._settings.anthropic_model, usage=usage,
                request_id=get_request_id(),
            )
        except Exception as exc:
            logger.warning("llm_usage_record_failed", feature="chat", error=str(exc))

    # --- HTTP: POST /sessions/{id}/messages — full turn, synchronous ---

    async def send_message(self, session_id: uuid.UUID, user_context: str, content: str) -> ChatTurnResult:
        prior_history = await self._messages.history(session_id)
        is_first_turn = len(prior_history) == 0

        user_message = await self._messages.create(session_id, "user", content)

        context_text = await self._safe_retrieve(session_id, content)
        messages = self._build_messages(user_context, prior_history, content, context_text)

        llm = get_llm_with_tools(self._settings, self._langchain_tools(), streaming=False)
        tool_call_results: list[ToolCallResult] = []

        response: AIMessage = await llm.ainvoke(messages)
        await self._record_usage(response)
        while getattr(response, "tool_calls", None):
            messages.append(response)
            used_indexing = False
            for call in response.tool_calls:
                result = await self._tools.execute(session_id, call["name"], call.get("args", {}))
                tool_call_results.append(result)
                if call["name"] in INDEXING_TOOLS and result.status == "ok":
                    used_indexing = True
                messages.append(ToolMessage(content=result.output, tool_call_id=call.get("id")))
            if used_indexing:
                refreshed = await self._safe_retrieve(session_id, content)
                if refreshed:
                    messages.append(_context_reminder(refreshed))
            response = await llm.ainvoke(messages)
            await self._record_usage(response)

        response_text = get_text_content(response).strip()
        assistant_message = await self._messages.create(session_id, "assistant", response_text)

        generated_title = None
        if is_first_turn:
            generated_title = await self._titles.generate(content, response_text)
            await self._sessions.set_title_if_null(session_id, generated_title)
        await self._sessions.touch(session_id)

        return ChatTurnResult(
            user_message=user_message,
            assistant_message=assistant_message,
            tool_calls=tool_call_results,
            generated_title=generated_title,
        )

    # --- WebSocket: token-by-token streaming (§7) ---

    async def stream_turn(self, session_id: uuid.UUID, user_context: str, content: str) -> AsyncIterator[dict[str, Any]]:
        prior_history = await self._messages.history(session_id)
        is_first_turn = len(prior_history) == 0

        user_message = await self._messages.create(session_id, "user", content)
        yield {"type": "ack", "user_message_id": str(user_message.id)}

        context_text = await self._safe_retrieve(session_id, content)
        messages = self._build_messages(user_context, prior_history, content, context_text)

        llm = get_llm_with_tools(self._settings, self._langchain_tools(), streaming=True)
        response_text_parts: list[str] = []

        while True:
            final_message: BaseMessage | None = None
            async for event in astream_text_events(llm, messages):
                kind = event.get("event")
                if kind == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    delta = get_text_content(chunk)
                    if delta:
                        yield {"type": "token", "content": delta}
                elif kind == "on_chat_model_end":
                    final_message = event["data"]["output"]

            if final_message is None:
                yield {"type": "error", "code": "llm_upstream_error", "message": "No response from model."}
                return

            if not getattr(final_message, "tool_calls", None):
                response_text_parts.append(get_text_content(final_message))
                break

            messages.append(final_message)
            used_indexing = False
            for call in final_message.tool_calls:
                call_id = call.get("id") or str(uuid.uuid4())
                yield {"type": "tool_call", "name": call["name"], "args": call.get("args", {}), "call_id": call_id}
                result = await self._tools.execute(session_id, call["name"], call.get("args", {}))
                if call["name"] in INDEXING_TOOLS and result.status == "ok":
                    used_indexing = True
                yield {
                    "type": "tool_result",
                    "call_id": call_id,
                    "status": result.status,
                    "summary": _summarize(result),
                }
                messages.append(ToolMessage(content=result.output, tool_call_id=call_id))
            if used_indexing:
                refreshed = await self._safe_retrieve(session_id, content)
                if refreshed:
                    messages.append(_context_reminder(refreshed))

        response_text = "".join(response_text_parts).strip()
        assistant_message = await self._messages.create(session_id, "assistant", response_text)

        generated_title = None
        if is_first_turn:
            generated_title = await self._titles.generate(content, response_text)
            await self._sessions.set_title_if_null(session_id, generated_title)
        await self._sessions.touch(session_id)

        yield {
            "type": "done",
            "assistant_message_id": str(assistant_message.id),
            "generated_title": generated_title,
        }

    # --- shared helpers ---

    def _build_messages(
        self, user_context: str, history: list[Message], content: str, context_text: str
    ) -> list[BaseMessage]:
        messages: list[BaseMessage] = [
            SystemMessage(content=_SYSTEM_INSTRUCTIONS.format(user_context=user_context)),
            SystemMessage(content=f"Relevant context (if any):\n{context_text}"),
        ]
        messages.extend(_to_lc_messages(history))
        messages.append(HumanMessage(content=content))
        return messages

    async def _safe_retrieve(self, session_id: uuid.UUID, query: str) -> str:
        try:
            chunks = await self._rag.retrieve(session_id, query, k=4)
        except Exception:
            return ""
        return "\n\n".join(chunks)

    def _langchain_tools(self) -> list[StructuredTool]:
        # Schemas are declarative (TOOL_DEFINITIONS); execution is dispatched
        # through ToolService.execute, so these stub coroutines are never
        # actually invoked by langchain — the loop above intercepts tool_calls
        # before .invoke() would run them.
        tools = []
        for definition in TOOL_DEFINITIONS:
            tools.append(
                StructuredTool.from_function(
                    func=lambda **_: "",
                    name=definition.name,
                    description=definition.description,
                    args_schema=_schema_to_pydantic(definition.name, definition.parameters),
                )
            )
        return tools


def _to_lc_messages(history: list[Message]) -> list[BaseMessage]:
    result: list[BaseMessage] = []
    for message in history:
        if message.role == "user":
            result.append(HumanMessage(content=message.content))
        elif message.role == "assistant":
            result.append(AIMessage(content=message.content))
    return result


def _context_reminder(context_text: str) -> HumanMessage:
    # Anthropic only allows system messages at the very start of a conversation,
    # so mid-loop context is injected as a labeled human-turn block instead
    # (mirrors chatbot/chat/loop.py).
    return HumanMessage(content=f"<system-reminder>Relevant context (if any):\n{context_text}</system-reminder>")


def _summarize(result: ToolCallResult) -> str:
    if result.status == "error":
        return result.error_message or "Tool execution failed."
    return result.output[:200]


def _schema_to_pydantic(name: str, json_schema: dict[str, Any]):
    from pydantic import create_model

    fields: dict[str, Any] = {}
    required = set(json_schema.get("required", []))
    for field_name, field_schema in json_schema.get("properties", {}).items():
        py_type = {"string": str, "integer": int, "number": float, "boolean": bool}.get(
            field_schema.get("type"), str
        )
        default = ... if field_name in required else field_schema.get("default", None)
        fields[field_name] = (py_type, default)
    return create_model(f"{name}_Args", **fields)
