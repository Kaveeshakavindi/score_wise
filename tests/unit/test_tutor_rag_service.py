from __future__ import annotations

import uuid

import pytest
from langchain_core.messages import AIMessage

import app.services.tutor_rag_service as tutor_rag_service_module
from app.core.exceptions import NotFoundError
from app.services.tutor_rag_service import TutorRagService
from app.vectorstore import chroma_client as chroma_client_module
from tests.fakes import FakeQuestionRepository, FakeSyllabusDocumentRepository, FakeTutorMessageRepository


class _FakeLLM:
    """Canned AIMessage response, same technique as ChatService's unit tests
    (§13) — no real Anthropic call happens here."""

    def __init__(self, response: AIMessage) -> None:
        self._response = response
        self.received_messages: list | None = None

    async def ainvoke(self, messages):
        self.received_messages = messages
        return self._response


def _async_return(value):
    async def _fn(*args, **kwargs):
        return value

    return _fn


async def _fake_get_embedder(model_name: str):
    return object()


async def _fake_embed_query(embedder, text: str) -> list[float]:
    return [0.1, 0.2]


@pytest.fixture
def tutor(settings, monkeypatch):
    question_repo = FakeQuestionRepository()
    message_repo = FakeTutorMessageRepository()
    syllabus_document_repo = FakeSyllabusDocumentRepository()
    service = TutorRagService(question_repo, message_repo, syllabus_document_repo, settings)

    monkeypatch.setattr(tutor_rag_service_module, "get_embedder", _fake_get_embedder)
    monkeypatch.setattr(tutor_rag_service_module, "embed_query", _fake_embed_query)

    return service, question_repo, message_repo, syllabus_document_repo


def _patch_llm(monkeypatch, response_text: str) -> _FakeLLM:
    fake = _FakeLLM(AIMessage(content=response_text))
    monkeypatch.setattr(tutor_rag_service_module, "get_llm", lambda *a, **k: fake)
    return fake


def _chunk(*, text: str, source_document_id: uuid.UUID, chunk_index: int = 0) -> dict:
    return {
        "text": text,
        "subject": "Physics",
        "topic": "Mechanics",
        "source_document_id": str(source_document_id),
        "chunk_index": chunk_index,
    }


async def test_send_message_grounds_the_prompt_in_the_question_and_retrieved_context(tutor, monkeypatch) -> None:
    service, question_repo, _, syllabus_document_repo = tutor
    question = await question_repo.create(
        uuid.uuid4(),
        subject="Physics",
        year=2022,
        question_number=1,
        question_text="What is the SI unit of force?",
        options={"A": "Newton", "B": "Joule", "C": "Watt", "D": "Pascal"},
        correct_answer=0,
    )
    document = await syllabus_document_repo.create(
        document_id=None, filename="physics_syllabus.pdf", subject="Physics", topic="Mechanics", chunk_count=1
    )
    monkeypatch.setattr(
        chroma_client_module,
        "query_chunks",
        _async_return([_chunk(text="Force is measured in Newtons per the syllabus.", source_document_id=document.id)]),
    )
    fake_llm = _patch_llm(monkeypatch, "The correct answer is A, Newton, because force = mass x acceleration.")

    result = await service.send_message(uuid.uuid4(), question.id, "Why is it A?")

    assert result.user_message.content == "Why is it A?"
    assert result.assistant_message.content == "The correct answer is A, Newton, because force = mass x acceleration."

    system_prompt = fake_llm.received_messages[0].content
    assert "What is the SI unit of force?" in system_prompt
    assert "A. Newton" in system_prompt
    assert "Correct answer: A" in system_prompt
    assert "Force is measured in Newtons per the syllabus." in system_prompt


async def test_send_message_attaches_resolved_citations_to_the_assistant_message(tutor, monkeypatch) -> None:
    service, question_repo, _, syllabus_document_repo = tutor
    question = await question_repo.create(
        uuid.uuid4(), subject="Physics", year=2022, question_number=1, question_text="Q?",
        options={"A": "a", "B": "b"}, correct_answer=0,
    )
    document = await syllabus_document_repo.create(
        document_id=None, filename="physics_syllabus.pdf", subject="Physics", topic="Mechanics", chunk_count=1
    )
    monkeypatch.setattr(
        chroma_client_module,
        "query_chunks",
        _async_return([_chunk(text="Grounding text.", source_document_id=document.id)]),
    )
    _patch_llm(monkeypatch, "reply")

    result = await service.send_message(uuid.uuid4(), question.id, "help")

    assert result.assistant_message.citations == [
        {
            "document_id": str(document.id),
            "filename": "physics_syllabus.pdf",
            "topic": "Mechanics",
            "snippet": "Grounding text.",
        }
    ]
    # The user's own turn never carries citations — only the grounded reply does.
    assert result.user_message.citations is None


async def test_send_message_skips_citations_for_chunks_with_an_unresolvable_source_document(tutor, monkeypatch) -> None:
    service, question_repo, _, _ = tutor
    question = await question_repo.create(
        uuid.uuid4(), subject="Physics", year=2022, question_number=1, question_text="Q?",
        options={"A": "a"}, correct_answer=0,
    )
    monkeypatch.setattr(
        chroma_client_module,
        "query_chunks",
        _async_return([_chunk(text="Orphaned chunk.", source_document_id=uuid.uuid4())]),
    )
    _patch_llm(monkeypatch, "reply")

    result = await service.send_message(uuid.uuid4(), question.id, "help")

    assert result.assistant_message.citations is None


async def test_send_message_includes_the_students_wrong_answer_in_the_prompt(tutor, monkeypatch) -> None:
    service, question_repo, _, _ = tutor
    question = await question_repo.create(
        uuid.uuid4(), subject="Physics", year=2022, question_number=1, question_text="Q?",
        options={"A": "Newton", "B": "Joule"}, correct_answer=0,
    )
    monkeypatch.setattr(chroma_client_module, "query_chunks", _async_return([]))
    fake_llm = _patch_llm(monkeypatch, "reply")

    await service.send_message(uuid.uuid4(), question.id, "Why is it wrong?", selected_answer=1)

    system_prompt = fake_llm.received_messages[0].content
    assert "Student's submitted answer: B (incorrect)" in system_prompt


async def test_send_message_without_a_selected_answer_omits_the_student_answer_line(tutor, monkeypatch) -> None:
    service, question_repo, _, _ = tutor
    question = await question_repo.create(
        uuid.uuid4(), subject="Physics", year=2022, question_number=1, question_text="Q?",
        options={"A": "Newton", "B": "Joule"}, correct_answer=0,
    )
    monkeypatch.setattr(chroma_client_module, "query_chunks", _async_return([]))
    fake_llm = _patch_llm(monkeypatch, "reply")

    await service.send_message(uuid.uuid4(), question.id, "help")

    assert "Student's submitted answer" not in fake_llm.received_messages[0].content


async def test_send_message_unknown_question_raises_not_found(tutor) -> None:
    service, _, _, _ = tutor
    with pytest.raises(NotFoundError):
        await service.send_message(uuid.uuid4(), uuid.uuid4(), "hi")


async def test_send_message_second_turn_includes_prior_turn_as_history(tutor, monkeypatch) -> None:
    service, question_repo, _, _ = tutor
    question = await question_repo.create(
        uuid.uuid4(), subject="Physics", year=2022, question_number=1, question_text="Q?",
        options={"A": "a", "B": "b"}, correct_answer=1,
    )
    monkeypatch.setattr(chroma_client_module, "query_chunks", _async_return([]))
    user_id = uuid.uuid4()

    _patch_llm(monkeypatch, "First reply")
    await service.send_message(user_id, question.id, "First message")

    fake_llm_2 = _patch_llm(monkeypatch, "Second reply")
    await service.send_message(user_id, question.id, "Second message")

    contents = [m.content for m in fake_llm_2.received_messages]
    assert "First message" in contents
    assert "First reply" in contents
    assert "Second message" in contents


async def test_send_message_scopes_history_per_user_not_globally(tutor, monkeypatch) -> None:
    service, question_repo, _, _ = tutor
    question = await question_repo.create(
        uuid.uuid4(), subject="Physics", year=2022, question_number=1, question_text="Q?",
        options={"A": "a"}, correct_answer=0,
    )
    monkeypatch.setattr(chroma_client_module, "query_chunks", _async_return([]))

    _patch_llm(monkeypatch, "Reply to user A")
    await service.send_message(uuid.uuid4(), question.id, "Message from user A")

    fake_llm_b = _patch_llm(monkeypatch, "Reply to user B")
    await service.send_message(uuid.uuid4(), question.id, "Message from user B")

    # user B's turn must not see user A's conversation
    contents = [m.content for m in fake_llm_b.received_messages]
    assert "Message from user A" not in contents
    assert "Reply to user A" not in contents


async def test_send_message_retrieval_failure_degrades_to_question_only_grounding(tutor, monkeypatch) -> None:
    service, question_repo, _, _ = tutor
    question = await question_repo.create(
        uuid.uuid4(), subject="Physics", year=2022, question_number=1, question_text="Q?",
        options={"A": "a"}, correct_answer=0,
    )

    async def _boom(*args, **kwargs):
        raise RuntimeError("chroma unreachable")

    monkeypatch.setattr(chroma_client_module, "query_chunks", _boom)
    fake_llm = _patch_llm(monkeypatch, "Answer anyway")

    result = await service.send_message(uuid.uuid4(), question.id, "help")

    assert result.assistant_message.content == "Answer anyway"
    assert result.assistant_message.citations is None
    assert "No matching syllabus content was found" in fake_llm.received_messages[0].content


async def test_get_history_returns_this_users_prior_turns_oldest_first(tutor, monkeypatch) -> None:
    service, question_repo, _, _ = tutor
    question = await question_repo.create(
        uuid.uuid4(), subject="Physics", year=2022, question_number=1, question_text="Q?",
        options={"A": "a"}, correct_answer=0,
    )
    monkeypatch.setattr(chroma_client_module, "query_chunks", _async_return([]))
    user_id = uuid.uuid4()
    _patch_llm(monkeypatch, "reply")
    await service.send_message(user_id, question.id, "hello")

    history = await service.get_history(user_id, question.id)

    assert [m.role for m in history] == ["user", "assistant"]
    assert history[0].content == "hello"
    assert history[1].content == "reply"


async def test_get_history_unknown_question_raises_not_found(tutor) -> None:
    service, _, _, _ = tutor
    with pytest.raises(NotFoundError):
        await service.get_history(uuid.uuid4(), uuid.uuid4())
