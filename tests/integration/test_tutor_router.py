from __future__ import annotations

import uuid

import httpx
import pytest
from langchain_core.messages import AIMessage

import app.services.tutor_rag_service as tutor_rag_service_module
from app.core.deps import (
    get_current_user,
    get_llm_usage_repository,
    get_question_repository,
    get_redis,
    get_syllabus_document_repository,
    get_tutor_message_repository,
)
from app.llm.pricing import estimate_cost_usd
from app.main import app
from app.vectorstore import chroma_client as chroma_client_module
from tests.fakes import (
    FakeLlmUsageRepository,
    FakeQuestionRepository,
    FakeRedis,
    FakeSyllabusDocumentRepository,
    FakeTutorMessageRepository,
)

_HEADERS = {"Authorization": "Bearer test-token"}


class _FakeLLM:
    def __init__(self, text: str, usage_metadata: dict | None = None) -> None:
        self._text = text
        self._usage_metadata = usage_metadata
        self.call_count = 0

    async def ainvoke(self, messages):
        self.call_count += 1
        return AIMessage(content=self._text, usage_metadata=self._usage_metadata)


async def _fake_get_embedder(model_name: str):
    return object()


async def _fake_embed_query(embedder, text: str) -> list[float]:
    return [0.1, 0.2]


@pytest.fixture
async def client(test_user, monkeypatch):
    question_repo = FakeQuestionRepository()
    tutor_message_repo = FakeTutorMessageRepository()
    syllabus_document_repo = FakeSyllabusDocumentRepository()
    llm_usage_repo = FakeLlmUsageRepository()

    app.dependency_overrides[get_current_user] = lambda: test_user
    app.dependency_overrides[get_question_repository] = lambda: question_repo
    app.dependency_overrides[get_tutor_message_repository] = lambda: tutor_message_repo
    app.dependency_overrides[get_syllabus_document_repository] = lambda: syllabus_document_repo
    app.dependency_overrides[get_llm_usage_repository] = lambda: llm_usage_repo
    app.dependency_overrides[get_redis] = lambda: FakeRedis()

    monkeypatch.setattr(tutor_rag_service_module, "get_embedder", _fake_get_embedder)
    monkeypatch.setattr(tutor_rag_service_module, "embed_query", _fake_embed_query)
    monkeypatch.setattr(tutor_rag_service_module, "get_llm", lambda *a, **k: _FakeLLM("Grounded feedback."))

    async def _fake_query_chunks(settings, *, query_embedding, subject, k):
        return [
            {
                "text": "Relevant syllabus excerpt.",
                "subject": subject,
                "topic": "Mechanics",
                "source_document_id": str(_SYLLABUS_DOC_ID),
                "chunk_index": 0,
            }
        ]

    monkeypatch.setattr(chroma_client_module, "query_chunks", _fake_query_chunks)

    await syllabus_document_repo.create(
        document_id=_SYLLABUS_DOC_ID,
        filename="physics_syllabus.pdf",
        subject="Physics",
        topic="Mechanics",
        chunk_count=1,
    )

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac, question_repo, tutor_message_repo, llm_usage_repo

    app.dependency_overrides.clear()


_SYLLABUS_DOC_ID = uuid.uuid4()


async def test_get_tutor_feedback_returns_grounded_feedback_with_citations(client) -> None:
    ac, question_repo, _, _ = client
    question = await question_repo.create(
        uuid.uuid4(), subject="Physics", year=2022, question_number=1, question_text="What is the SI unit of force?",
        options={"A": "Newton", "B": "Joule"}, correct_answer=0,
    )

    response = await ac.post(
        f"/api/v1/questions/{question.id}/tutor", json={"selected_answer": 1}, headers=_HEADERS
    )

    assert response.status_code == 201
    body = response.json()
    assert body["feedback"]["content"] == "Grounded feedback."
    assert body["feedback"]["is_correct"] is False
    assert body["feedback"]["citations"] == [
        {
            "document_id": str(_SYLLABUS_DOC_ID),
            "filename": "physics_syllabus.pdf",
            "topic": "Mechanics",
            "snippet": "Relevant syllabus excerpt.",
        }
    ]


async def test_get_tutor_feedback_with_selected_answer_grounds_the_prompt_in_it(client, monkeypatch) -> None:
    ac, question_repo, _, _ = client
    question = await question_repo.create(
        uuid.uuid4(), subject="Physics", year=2022, question_number=1, question_text="What is the SI unit of force?",
        options={"A": "Newton", "B": "Joule"}, correct_answer=0,
    )

    captured: dict = {}

    class _CapturingLLM:
        async def ainvoke(self, messages):
            captured["system_prompt"] = messages[0].content
            return AIMessage(content="Grounded feedback.")

    monkeypatch.setattr(tutor_rag_service_module, "get_llm", lambda *a, **k: _CapturingLLM())

    response = await ac.post(
        f"/api/v1/questions/{question.id}/tutor",
        json={"selected_answer": 1},
        headers=_HEADERS,
    )

    assert response.status_code == 201
    assert "Student's submitted answer: B (incorrect)" in captured["system_prompt"]


async def test_get_tutor_feedback_without_a_selected_answer_uses_the_missed_branch(client) -> None:
    ac, question_repo, _, _ = client
    question = await question_repo.create(
        uuid.uuid4(), subject="Physics", year=2022, question_number=1, question_text="Q?",
        options={"A": "a", "B": "b"}, correct_answer=0,
    )

    response = await ac.post(f"/api/v1/questions/{question.id}/tutor", json={}, headers=_HEADERS)

    assert response.status_code == 201
    body = response.json()
    assert body["feedback"]["selected_answer"] is None
    assert body["feedback"]["is_correct"] is False


async def test_get_tutor_feedback_unknown_question_returns_404(client) -> None:
    ac, _, _, _ = client
    response = await ac.post(
        f"/api/v1/questions/{uuid.uuid4()}/tutor", json={}, headers=_HEADERS
    )
    assert response.status_code == 404


async def test_get_tutor_feedback_is_idempotent_across_requests(client, monkeypatch) -> None:
    ac, question_repo, _, _ = client
    question = await question_repo.create(
        uuid.uuid4(), subject="Physics", year=2022, question_number=1, question_text="Q?",
        options={"A": "a", "B": "b"}, correct_answer=0,
    )
    fake_llm = _FakeLLM("Grounded feedback.")
    monkeypatch.setattr(tutor_rag_service_module, "get_llm", lambda *a, **k: fake_llm)

    first = await ac.post(f"/api/v1/questions/{question.id}/tutor", json={"selected_answer": 1}, headers=_HEADERS)
    second = await ac.post(f"/api/v1/questions/{question.id}/tutor", json={"selected_answer": 1}, headers=_HEADERS)

    assert first.json()["feedback"]["id"] == second.json()["feedback"]["id"]
    assert fake_llm.call_count == 1


async def test_get_tutor_feedback_reports_token_usage(client, monkeypatch, settings) -> None:
    ac, question_repo, _, llm_usage_repo = client
    question = await question_repo.create(
        uuid.uuid4(), subject="Physics", year=2022, question_number=1, question_text="Q?",
        options={"A": "a", "B": "b"}, correct_answer=0,
    )
    fake_llm = _FakeLLM("Grounded feedback.", usage_metadata={"input_tokens": 300, "output_tokens": 60, "total_tokens": 360})
    monkeypatch.setattr(tutor_rag_service_module, "get_llm", lambda *a, **k: fake_llm)

    response = await ac.post(f"/api/v1/questions/{question.id}/tutor", json={"selected_answer": 1}, headers=_HEADERS)

    assert response.status_code == 201
    body = response.json()["feedback"]
    assert body["input_tokens"] == 300
    assert body["output_tokens"] == 60
    # Computed from the real MODEL_PRICING entry for whatever ANTHROPIC_MODEL
    # the test settings resolve to -- not hardcoded, so this doesn't rot if
    # the configured rate changes. (See tests/unit/test_pricing.py for the
    # "model not in MODEL_PRICING -> None" case on its own.)
    expected_cost = estimate_cost_usd(settings.anthropic_model, input_tokens=300, output_tokens=60)
    assert expected_cost is not None
    assert body["estimated_cost_usd"] == pytest.approx(expected_cost)
    assert response.headers["X-Tokens-Used-Request"] == "360"
    assert len(llm_usage_repo.events) == 1
    assert llm_usage_repo.events[0].feature == "tutor_feedback"


async def test_tutor_routes_require_auth() -> None:
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(f"/api/v1/questions/{uuid.uuid4()}/tutor", json={})
    assert response.status_code == 401
