from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from app.core.config import Settings
from app.core.exceptions import NotFoundError
from app.db.models import Question, TutorMessage
from app.llm.anthropic_client import get_llm, get_text_content
from app.llm.embedder import embed_query, get_embedder
from app.repositories.question_repository import QuestionRepository
from app.repositories.syllabus_document_repository import SyllabusDocumentRepository
from app.repositories.tutor_message_repository import TutorMessageRepository
from app.vectorstore import chroma_client

_RETRIEVAL_K = 4
_CITATION_SNIPPET_MAX_CHARS = 400

# (a) states the question/options/correct answer explicitly, (a2) states what
# the student themselves picked, (b) includes retrieved syllabus context
# (numbered so the model can point back at [n]), (c) restricts the model to
# that data only, and (d) redirects off-topic questions back to this one (§3
# step 3 (a)-(d), and the proposal's "AI tutor misuse" risk mitigation). No
# tool-calling loop and no generic file/URL tools are wired in here — out of
# scope for ScoreWise (§5).
_SYSTEM_PROMPT_TEMPLATE = """You are ScoreWise's AI tutor. You are helping a GCE A/L student understand ONE specific past-paper multiple-choice question — nothing else.

Question ({subject}, {year}, Q{question_number}):
{question_text}

Options:
{options_block}

Correct answer: {correct_answer_label}
{student_answer_line}
Relevant syllabus context (retrieved for this question, numbered for citation):
{context_block}

Rules you must follow:
1. Answer using ONLY the question/options/correct-answer data above and the retrieved syllabus context above. Do not use any outside knowledge, even if you are confident about it.
2. If the syllabus context above does not cover something the student asks, say plainly that the provided syllabus material does not cover it — do not fill the gap yourself.
3. Never contradict the stated correct answer.
4. If the student answered incorrectly, address their specific wrong choice — explain why it's wrong, not just why the correct answer is right.
5. If the student asks about anything unrelated to this specific question (a different subject, a different question, general chit-chat, or anything off-topic), politely decline and redirect them back to this question. Do not answer the unrelated request.
6. Be concise and pedagogical — explain *why* the correct answer is correct, and where useful, why the other options are wrong, grounded in the context above. Reference context items as [1], [2], etc. where it helps show your explanation is grounded.
"""


@dataclass(frozen=True)
class Citation:
    """One retrieved syllabus chunk that grounded an assistant reply."""

    document_id: uuid.UUID
    filename: str
    topic: str | None
    snippet: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "document_id": str(self.document_id),
            "filename": self.filename,
            "topic": self.topic,
            "snippet": self.snippet,
        }


@dataclass(frozen=True)
class TutorTurnResult:
    user_message: TutorMessage
    assistant_message: TutorMessage


class TutorRagService:
    """Question-scoped, grounded AI tutor (§3): SQL lookup for the exact
    question/answer, ChromaDB retrieval for syllabus context, then a single
    non-streaming, non-tool-calling LLM turn. Deliberately not built on
    ChatService's tool-calling loop (§5 explicit non-goal)."""

    def __init__(
        self,
        question_repo: QuestionRepository,
        tutor_message_repo: TutorMessageRepository,
        syllabus_document_repo: SyllabusDocumentRepository,
        settings: Settings,
    ) -> None:
        self._questions = question_repo
        self._messages = tutor_message_repo
        self._syllabus_documents = syllabus_document_repo
        self._settings = settings

    async def send_message(
        self, user_id: uuid.UUID, question_id: uuid.UUID, content: str, selected_answer: int | None = None
    ) -> TutorTurnResult:
        # Step 1: deterministic SQL lookup for the question/options/answer —
        # never a vector search for this part (§3 step 1).
        question = await self._questions.get_by_id(question_id)
        if question is None:
            raise NotFoundError(f"Question {question_id} was not found.")

        history = await self._messages.history(question_id=question_id, user_id=user_id)
        user_message = await self._messages.create(
            question_id=question_id, user_id=user_id, role="user", content=content
        )

        # Step 2: top-k syllabus chunks, filtered by subject, ranked by
        # similarity to question text + the student's message (§3 step 2).
        chunks = await self._retrieve_context(question, content)
        citations = await self._to_citations(chunks)

        # Step 3: structured, grounded system prompt — including what the
        # student themselves answered, when known.
        messages: list[BaseMessage] = [
            SystemMessage(content=_build_system_prompt(question, citations, selected_answer))
        ]
        messages.extend(_to_lc_messages(history))
        messages.append(HumanMessage(content=content))

        # Step 4: a single grounded LLM turn — no streaming, no tool loop.
        llm = get_llm(self._settings)
        response: AIMessage = await llm.ainvoke(messages)
        response_text = get_text_content(response).strip()

        assistant_message = await self._messages.create(
            question_id=question_id,
            user_id=user_id,
            role="assistant",
            content=response_text,
            citations=[c.as_dict() for c in citations] or None,
        )

        return TutorTurnResult(user_message=user_message, assistant_message=assistant_message)

    async def get_history(self, user_id: uuid.UUID, question_id: uuid.UUID) -> list[TutorMessage]:
        question = await self._questions.get_by_id(question_id)
        if question is None:
            raise NotFoundError(f"Question {question_id} was not found.")
        return await self._messages.history(question_id=question_id, user_id=user_id)

    async def _retrieve_context(self, question: Question, student_message: str) -> list[dict[str, Any]]:
        try:
            embedder = await get_embedder(self._settings.embedding_model)
            query_vector = await embed_query(embedder, f"{question.question_text}\n{student_message}")
            return await chroma_client.query_chunks(
                self._settings, query_embedding=query_vector, subject=question.subject, k=_RETRIEVAL_K
            )
        except Exception:
            # A syllabus-retrieval hiccup (e.g. ChromaDB briefly unreachable)
            # shouldn't take the tutor turn down with it — it degrades to
            # question/answer-only grounding instead (mirrors ChatService's
            # _safe_retrieve for the generic RAG store).
            return []

    async def _to_citations(self, chunks: list[dict[str, Any]]) -> list[Citation]:
        """Resolves each retrieved chunk's source_document_id to its
        filename/topic in one batched lookup, so the tutor can show real
        citations instead of opaque chunk text."""
        document_ids: list[uuid.UUID] = []
        for chunk in chunks:
            raw_id = chunk.get("source_document_id")
            if raw_id:
                try:
                    document_ids.append(uuid.UUID(str(raw_id)))
                except ValueError:
                    continue

        documents_by_id = await self._syllabus_documents.get_many_by_ids(document_ids)

        citations: list[Citation] = []
        for chunk in chunks:
            raw_id = chunk.get("source_document_id")
            text = chunk.get("text") or ""
            snippet = text if len(text) <= _CITATION_SNIPPET_MAX_CHARS else text[:_CITATION_SNIPPET_MAX_CHARS] + "…"
            try:
                document_id = uuid.UUID(str(raw_id)) if raw_id else None
            except ValueError:
                document_id = None
            document = documents_by_id.get(document_id) if document_id else None
            if document_id is None or document is None:
                continue  # chunk's source document was deleted/unresolvable — skip rather than cite a ghost
            citations.append(
                Citation(
                    document_id=document_id,
                    filename=document.filename,
                    topic=document.topic,
                    snippet=snippet,
                )
            )
        return citations


def _build_system_prompt(question: Question, citations: list[Citation], selected_answer: int | None) -> str:
    keys = _ordered_option_keys(question.options)
    options_block = "\n".join(f"{key}. {question.options[key]}" for key in keys)
    context_block = (
        "\n\n".join(f"[{i}] ({c.filename}) {c.snippet}" for i, c in enumerate(citations, start=1))
        if citations
        else "(No matching syllabus content was found.)"
    )
    return _SYSTEM_PROMPT_TEMPLATE.format(
        subject=question.subject,
        year=question.year,
        question_number=question.question_number,
        question_text=question.question_text,
        options_block=options_block,
        correct_answer_label=(
            "This question was voided on the official marking scheme — every answer, including leaving it "
            "blank, was accepted as correct. There is no single right option to explain."
            if question.accept_all
            else keys[question.correct_answer]
        ),
        student_answer_line=_student_answer_line(question, keys, selected_answer),
        context_block=context_block,
    )


def _student_answer_line(question: Question, keys: list[str], selected_answer: int | None) -> str:
    if selected_answer is None or not (0 <= selected_answer < len(keys)):
        return ""
    if question.accept_all:
        return f"Student's submitted answer: {keys[selected_answer]} (this question was voided, so it was accepted).\n"
    is_correct = selected_answer == question.correct_answer
    verdict = "correct" if is_correct else "incorrect"
    return f"Student's submitted answer: {keys[selected_answer]} ({verdict}).\n"


def _ordered_option_keys(options: dict[str, str]) -> list[str]:
    # Options are keyed however the source paper labels them (e.g. "1"-"5" or
    # "A"-"D"); correct_answer is a 0-based index into this ordering. Sorted
    # numerically when keys are digits so "2" < "10" (falls back to plain
    # lexicographic sort for lettered keys).
    return sorted(options.keys(), key=lambda k: int(k) if k.isdigit() else k)


def _to_lc_messages(history: list[TutorMessage]) -> list[BaseMessage]:
    result: list[BaseMessage] = []
    for message in history:
        if message.role == "user":
            result.append(HumanMessage(content=message.content))
        else:
            result.append(AIMessage(content=message.content))
    return result
