from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import BaseMessage
from langchain_core.tools import BaseTool

from app.core.config import Settings

# Anthropic SDK's built-in retry (exponential backoff on 429/5xx) — no custom
# retry loop needed (§11).
DEFAULT_MAX_RETRIES = 2


def get_llm(settings: Settings, *, streaming: bool = False) -> ChatAnthropic:
    """Thin wrapper factory around ChatAnthropic (async-capable via
    ainvoke/astream_events — langchain_anthropic's async methods are backed by
    the Anthropic SDK's own async HTTP transport)."""
    return ChatAnthropic(
        model=settings.anthropic_model,
        api_key=settings.anthropic_api_key,
        max_tokens=8192,
        streaming=streaming,
        max_retries=DEFAULT_MAX_RETRIES,
    )


def get_llm_with_tools(settings: Settings, tools: list[BaseTool], *, streaming: bool = False) -> ChatAnthropic:
    return get_llm(settings, streaming=streaming).bind_tools(tools)


def get_text_content(message: BaseMessage) -> str:
    """Extract plain text from a message's content. Anthropic responses
    represent content as a list of content blocks rather than a plain string."""
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "".join(parts)
    return str(content) if content else ""


@dataclass(frozen=True)
class Usage:
    """Token usage for one LLM call, in the provider-agnostic shape the rest
    of the app deals with (app/llm/pricing.py, LlmUsageEvent)."""

    input_tokens: int
    output_tokens: int
    total_tokens: int


def get_usage(message: BaseMessage) -> Usage | None:
    """Extracts real token usage from a response message's usage_metadata --
    Anthropic's Messages API reports exact counts, so nothing here estimates
    with a tokenizer. None if the message carries no usage_metadata (e.g. a
    non-AIMessage, or a provider/version that doesn't populate it) — callers
    must treat that as "unknown", not zero."""
    usage = getattr(message, "usage_metadata", None)
    if not usage:
        return None
    return Usage(
        input_tokens=usage.get("input_tokens", 0),
        output_tokens=usage.get("output_tokens", 0),
        total_tokens=usage.get("total_tokens", 0),
    )


async def astream_text_events(llm: ChatAnthropic, messages: list[BaseMessage]) -> AsyncIterator[dict[str, Any]]:
    """Yields real incremental generation events from astream_events — genuine
    token-by-token streaming, unlike the CLI's post-hoc chunk-slicing (§7, §16)."""
    async for event in llm.astream_events(messages, version="v2"):
        yield event
