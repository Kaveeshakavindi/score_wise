from __future__ import annotations

import re

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.config import Settings
from app.llm.anthropic_client import get_llm, get_text_content

_SYSTEM_TEXT = (
    "Create a short 3-4 word session title in Title Case. "
    "Use only ASCII letters and spaces. No punctuation. Return only the title."
)


class TitleService:
    """Mirrors chatbot/chat/title.py's generate_session_title, async."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def generate(self, user_input: str, assistant_output: str) -> str:
        human_text = f"User: {user_input}\nAssistant: {assistant_output}"

        candidate = ""
        try:
            llm = get_llm(self._settings)
            response = await llm.ainvoke([SystemMessage(content=_SYSTEM_TEXT), HumanMessage(content=human_text)])
            candidate = _sanitize_title(get_text_content(response))
        except Exception:
            candidate = ""

        if not candidate:
            candidate = _fallback_title(f"{user_input} {assistant_output}")

        words = candidate.split()
        if len(words) < 3:
            words = _fallback_title(user_input).split()

        if len(words) < 3:
            return "New Chat Session"

        return " ".join(words[:4]).title()


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
