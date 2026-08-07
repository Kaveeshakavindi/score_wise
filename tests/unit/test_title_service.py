from __future__ import annotations

from langchain_core.messages import AIMessage

import app.services.title_service as title_service_module
from app.services.title_service import TitleService


class _FakeLLM:
    def __init__(self, text: str) -> None:
        self._text = text

    async def ainvoke(self, messages) -> AIMessage:
        return AIMessage(content=self._text)


async def test_generate_sanitizes_and_title_cases_model_output(settings, monkeypatch) -> None:
    monkeypatch.setattr(
        title_service_module, "get_llm", lambda *a, **k: _FakeLLM('"draft a statement of purpose!!"')
    )
    service = TitleService(settings)

    title = await service.generate("How do I draft an SOP?", "Here's how...")

    assert title == "Draft A Statement Of"
    assert all(c.isalnum() or c.isspace() for c in title)  # ASCII letters/spaces only, no punctuation


async def test_generate_falls_back_to_input_when_llm_call_fails(settings, monkeypatch) -> None:
    def _boom(*a, **k):
        raise RuntimeError("upstream down")

    monkeypatch.setattr(title_service_module, "get_llm", _boom)
    service = TitleService(settings)

    title = await service.generate("What is the capital of France", "Paris is the capital")

    assert title == "What Is The Capital"


async def test_generate_returns_default_when_everything_is_too_short(settings, monkeypatch) -> None:
    monkeypatch.setattr(title_service_module, "get_llm", lambda *a, **k: _FakeLLM(""))
    service = TitleService(settings)

    title = await service.generate("hi", "hello")

    assert title == "New Chat Session"
