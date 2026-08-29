from __future__ import annotations

import re

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from app.core.config import Settings
from app.core.logging import get_request_id, logger
from app.llm.anthropic_client import get_llm, get_text_content, get_usage
from app.repositories.llm_usage_repository import LlmUsageRepository

_SYSTEM_TEXT = (
    "Create a short 3-4 word session title in Title Case. "
    "Use only ASCII letters and spaces. No punctuation. Return only the title."
)


class TitleService:
    """Mirrors chatbot/chat/title.py's generate_session_title, async."""

    def __init__(self, settings: Settings, llm_usage_repo: LlmUsageRepository) -> None:
        self._settings = settings
        self._llm_usage = llm_usage_repo

    async def generate(self, user_input: str, assistant_output: str) -> str:
        human_text = f"User: {user_input}\nAssistant: {assistant_output}"

        candidate = ""
        try:
            llm = get_llm(self._settings)
            response = await llm.ainvoke([SystemMessage(content=_SYSTEM_TEXT), HumanMessage(content=human_text)])
            candidate = _sanitize_title(get_text_content(response))
        except Exception:
            candidate = ""
        else:
            # Own try/except so a usage-logging failure can never wipe out a
            # candidate title that was already generated successfully above.
            await self._record_usage(response)

        if not candidate:
            candidate = _fallback_title(f"{user_input} {assistant_output}")

        words = candidate.split()
        if len(words) < 3:
            words = _fallback_title(user_input).split()

        if len(words) < 3:
            return "New Chat Session"

        return " ".join(words[:4]).title()

    async def _record_usage(self, response: BaseMessage) -> None:
        # No user_id here: title generation runs inside ChatService.send_message
        # keyed by session_id, with no user-ownership model resolved at this
        # layer (see app/db/models.py — there's no Session model this app's
        # auth ties to). Recorded with user_id=None so it still counts toward
        # total app-wide token spend; per-user attribution for this feature
        # is a follow-up, not something worth threading through here now.
        usage = get_usage(response)
        if usage is None:
            return
        try:
            await self._llm_usage.record(
                user_id=None,
                feature="chat_title",
                model=self._settings.anthropic_model,
                usage=usage,
                request_id=get_request_id(),
            )
        except Exception as exc:
            logger.warning("llm_usage_record_failed", feature="chat_title", error=str(exc))


def _sanitize_title(text: str) -> str:
    cleaned = text.strip().strip('"').strip("'")
    cleaned = cleaned.encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^A-Za-z0-9\s]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _fallback_title(text: str) -> str:
    cleaned = _sanitize_title(text)
    if not cleaned:
        return ""
    words = cleaned.split()
    return " ".join(words[:4])
