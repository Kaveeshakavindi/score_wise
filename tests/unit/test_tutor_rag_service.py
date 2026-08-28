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
        self.call_count = 0

    async def ainvoke(self, messages):
        self.call_count += 1
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
    monkeypatch.setattr(chroma_client_module, "query_chunks", _async_return([]))

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


async def test_generate_feedback_grounds_the_prompt_in_the_question_and_retrieved_context(tutor, monkeypatch) -> None:
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

    message = await service.generate_feedback(uuid.uuid4(), question.id, selected_answer=1)

    assert message.content == "The correct answer is A, Newton, because force = mass x acceleration."

    system_prompt = fake_llm.received_messages[0].content
    assert "What is the SI unit of force?" in system_prompt
    assert "A. Newton" in system_prompt
    assert "Correct answer: A" in system_prompt
    assert "Force is measured in Newtons per the syllabus." in system_prompt


async def test_generate_feedback_attaches_resolved_citations(tutor, monkeypatch) -> None:
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

    message = await service.generate_feedback(uuid.uuid4(), question.id, selected_answer=1)

    assert message.citations == [
        {
            "document_id": str(document.id),
            "filename": "physics_syllabus.pdf",
            "topic": "Mechanics",
            "snippet": "Grounding text.",
        }
    ]


async def test_generate_feedback_skips_citations_for_chunks_with_an_unresolvable_source_document(
    tutor, monkeypatch
) -> None:
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

    message = await service.generate_feedback(uuid.uuid4(), question.id)

    assert message.citations is None


async def test_generate_feedback_for_a_correct_answer_uses_the_correct_branch(tutor, monkeypatch) -> None:
    service, question_repo, _, _ = tutor
    question = await question_repo.create(
        uuid.uuid4(), subject="Physics", year=2022, question_number=1, question_text="Q?",
        options={"A": "Newton", "B": "Joule"}, correct_answer=0,
    )
    fake_llm = _patch_llm(monkeypatch, "reply")

    message = await service.generate_feedback(uuid.uuid4(), question.id, selected_answer=0)

    assert message.is_correct is True
    system_prompt = fake_llm.received_messages[0].content
    assert "The student answered correctly" in system_prompt
    assert "Student's submitted answer: A (correct)" in system_prompt


async def test_generate_feedback_for_a_wrong_answer_requests_the_structured_wrong_branch(tutor, monkeypatch) -> None:
    service, question_repo, _, _ = tutor
    question = await question_repo.create(
        uuid.uuid4(), subject="Physics", year=2022, question_number=1, question_text="Q?",
        options={"A": "Newton", "B": "Joule"}, correct_answer=0,
    )
    fake_llm = _patch_llm(monkeypatch, "reply")

    message = await service.generate_feedback(uuid.uuid4(), question.id, selected_answer=1)

    assert message.is_correct is False
    system_prompt = fake_llm.received_messages[0].content
    assert "The student answered incorrectly" in system_prompt
    assert "**Why B is wrong**" in system_prompt
    assert "**Why A is right**" in system_prompt
    assert "Student's submitted answer: B (incorrect)" in system_prompt


async def test_generate_feedback_for_a_missed_question_requests_the_structured_missed_branch(
    tutor, monkeypatch
) -> None:
    service, question_repo, _, _ = tutor
    question = await question_repo.create(
        uuid.uuid4(), subject="Physics", year=2022, question_number=1, question_text="Q?",
        options={"A": "Newton", "B": "Joule"}, correct_answer=0,
    )
    fake_llm = _patch_llm(monkeypatch, "reply")

    message = await service.generate_feedback(uuid.uuid4(), question.id, selected_answer=None)

    assert message.is_correct is False
    assert message.selected_answer is None
    system_prompt = fake_llm.received_messages[0].content
    assert "The student left this question blank" in system_prompt
    assert "**Why A is right**" in system_prompt
    assert "is wrong**" not in system_prompt  # no "why your answer is wrong" section — there was no answer
    assert "Student's submitted answer: (left blank)" in system_prompt


async def test_generate_feedback_for_a_voided_question_uses_the_voided_branch(tutor, monkeypatch) -> None:
    service, question_repo, _, _ = tutor
    question = await question_repo.create(
        uuid.uuid4(), subject="Physics", year=2022, question_number=1, question_text="Q?",
        options={"A": "a", "B": "b"}, correct_answer=0,
    )
    question.accept_all = True
    fake_llm = _patch_llm(monkeypatch, "reply")

    message = await service.generate_feedback(uuid.uuid4(), question.id, selected_answer=1)

    assert message.is_correct is True
    assert "voided on the official marking scheme" in fake_llm.received_messages[0].content


async def test_generate_feedback_unknown_question_raises_not_found(tutor) -> None:
    service, _, _, _ = tutor
    with pytest.raises(NotFoundError):
        await service.generate_feedback(uuid.uuid4(), uuid.uuid4())


async def test_generate_feedback_is_idempotent_and_does_not_call_the_llm_again(tutor, monkeypatch) -> None:
    service, question_repo, _, _ = tutor
    question = await question_repo.create(
        uuid.uuid4(), subject="Physics", year=2022, question_number=1, question_text="Q?",
        options={"A": "a", "B": "b"}, correct_answer=0,
    )
    user_id = uuid.uuid4()
    fake_llm = _patch_llm(monkeypatch, "First reply")

    first = await service.generate_feedback(user_id, question.id, selected_answer=1)
    second = await service.generate_feedback(user_id, question.id, selected_answer=1)

    assert first.id == second.id
    assert second.content == "First reply"
    assert fake_llm.call_count == 1


async def test_generate_feedback_regenerates_when_the_selected_answer_changes(tutor, monkeypatch) -> None:
    service, question_repo, _, _ = tutor
    question = await question_repo.create(
        uuid.uuid4(), subject="Physics", year=2022, question_number=1, question_text="Q?",
        options={"A": "a", "B": "b", "C": "c"}, correct_answer=0,
    )
    user_id = uuid.uuid4()
    _patch_llm(monkeypatch, "First reply, about B")

    first = await service.generate_feedback(user_id, question.id, selected_answer=1)

    fake_llm_second = _patch_llm(monkeypatch, "Second reply, about C")
    second = await service.generate_feedback(user_id, question.id, selected_answer=2)

    assert second.id != first.id
    assert second.content == "Second reply, about C"
    assert second.selected_answer == 2
    assert fake_llm_second.call_count == 1

    # Asking again about the first answer still returns that first cached
    # row rather than re-generating or returning the second one.
    third = await service.generate_feedback(user_id, question.id, selected_answer=1)
    assert third.id == first.id
    assert third.content == "First reply, about B"


async def test_generate_feedback_scopes_caching_per_user_not_globally(tutor, monkeypatch) -> None:
    service, question_repo, _, _ = tutor
    question = await question_repo.create(
        uuid.uuid4(), subject="Physics", year=2022, question_number=1, question_text="Q?",
        options={"A": "a"}, correct_answer=0,
    )
    _patch_llm(monkeypatch, "Reply to user A")
    await service.generate_feedback(uuid.uuid4(), question.id, selected_answer=0)

    fake_llm_b = _patch_llm(monkeypatch, "Reply to user B")
    message_b = await service.generate_feedback(uuid.uuid4(), question.id, selected_answer=0)

    assert message_b.content == "Reply to user B"
    assert fake_llm_b.call_count == 1


async def test_generate_feedback_retrieval_failure_degrades_to_question_only_grounding(tutor, monkeypatch) -> None:
    service, question_repo, _, _ = tutor
    question = await question_repo.create(
        uuid.uuid4(), subject="Physics", year=2022, question_number=1, question_text="Q?",
        options={"A": "a"}, correct_answer=0,
    )

    async def _boom(*args, **kwargs):
        raise RuntimeError("chroma unreachable")

    monkeypatch.setattr(chroma_client_module, "query_chunks", _boom)
    fake_llm = _patch_llm(monkeypatch, "Answer anyway")

    message = await service.generate_feedback(uuid.uuid4(), question.id)

    assert message.content == "Answer anyway"
    assert message.citations is None
    assert "No matching syllabus content was found" in fake_llm.received_messages[0].content
