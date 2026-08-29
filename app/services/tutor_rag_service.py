from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.core.config import Settings
from app.core.exceptions import NotFoundError
from app.core.logging import get_request_id, logger
from app.db.models import Question, TutorMessage
from app.llm.anthropic_client import get_llm, get_text_content, get_usage
from app.llm.embedder import embed_query, get_embedder
from app.repositories.llm_usage_repository import LlmUsageRepository
from app.repositories.question_repository import QuestionRepository
from app.repositories.syllabus_document_repository import SyllabusDocumentRepository
from app.repositories.tutor_message_repository import TutorMessageRepository
from app.vectorstore import chroma_client

_RETRIEVAL_K = 4
_CITATION_SNIPPET_MAX_CHARS = 400

# One fixed, structured feedback message per (question, user) — not a
# conversation (§3 redesign: the free-text "AI tutor chat" let students ask
# anything, including off-topic questions unrelated to why their answer was
# right/wrong, which was both a misuse surface and a weak learning design —
# structured, always-shown feedback teaches better than an open-ended
# invitation to ask). The branch instruction (correct/wrong/missed/voided)
# is selected in Python, not left to the model, so every student gets the
# same scaffold instead of whatever shape the model felt like writing.
_SYSTEM_PROMPT_TEMPLATE = """You are ScoreWise's AI tutor. You generate ONE piece of feedback for a GCE A/L student about their answer to ONE specific past-paper multiple-choice question. This is not a conversation: do not invite follow-up questions, do not address the student as if they can reply.

Question ({subject}, {year}, Q{question_number}):
{question_text}

Options:
{options_block}

Correct answer: {correct_answer_label}
{student_answer_line}
Relevant syllabus context (retrieved for this question, numbered for citation):
{context_block}

Rules you must follow:
1. Use ONLY the question/options/correct-answer data above and the retrieved syllabus context above. Do not use any outside knowledge, even if you are confident about it.
2. If the syllabus context above does not cover something needed to explain the answer, say plainly that the provided syllabus material does not cover it — do not fill the gap yourself.
3. Never contradict the stated correct answer.
4. Be concise. Reference context items as [1], [2], etc. where it helps show your explanation is grounded.
5. {outcome_instructions}
"""

_CORRECT_INSTRUCTIONS = (
    "The student answered correctly. Confirm this in one short sentence, then give a brief (2-4 sentence) "
    "explanation of why that answer is right, grounded in the syllabus context above."
)

_WRONG_INSTRUCTIONS = (
    "The student answered incorrectly. Respond in exactly this structure, using these three headings verbatim "
    "(markdown bold, one blank line between sections):\n\n"
    "**Why {student_label} is wrong**\n<1-3 sentences>\n\n"
    "**Why {correct_label} is right**\n<1-3 sentences>\n\n"
    "**Concept being tested**\n<1-2 sentences naming the underlying syllabus concept>"
)

_MISSED_INSTRUCTIONS = (
    "The student left this question blank. Respond in exactly this structure, using these two headings verbatim "
    "(markdown bold, one blank line between sections):\n\n"
    "**Why {correct_label} is right**\n<1-3 sentences>\n\n"
    "**Concept being tested**\n<1-2 sentences naming the underlying syllabus concept>"
)

_VOIDED_INSTRUCTIONS = (
    "This question was voided on the official marking scheme — every response, including a blank one, was "
    "accepted as correct. In 2-3 sentences grounded in the syllabus context above, explain what the question was "
    "testing; if the context doesn't explain why it was voided, just say there's no single correct option here."
)

# The system prompt carries the entire task; this is just enough of a human
# turn to satisfy the API's requirement of at least one non-system message.
_GENERATE_TURN = HumanMessage(content="Generate the feedback now, following the rules exactly.")


@dataclass(frozen=True)
class Citation:
    """One retrieved syllabus chunk that grounded the feedback."""

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


class TutorRagService:
    """Question-scoped, grounded AI feedback (§3 redesign): SQL lookup for
    the exact question/answer, ChromaDB retrieval for syllabus context, then
    a single non-streaming, non-tool-calling LLM call whose output structure
    is fixed by which of correct/wrong/missed/voided applies — not an open
    chat. Idempotent per (question, user, selected_answer): the first call
    for a given answer generates and caches the feedback, and every later
    call for that exact same answer returns the cached row without another
    LLM call — but a call with a *different* selected_answer (e.g. a retake
    where the student picked something else) always generates fresh feedback
    rather than reusing a cached row that was about a different answer."""

    def __init__(
        self,
        question_repo: QuestionRepository,
        tutor_message_repo: TutorMessageRepository,
        syllabus_document_repo: SyllabusDocumentRepository,
        llm_usage_repo: LlmUsageRepository,
        settings: Settings,
    ) -> None:
        self._questions = question_repo
        self._messages = tutor_message_repo
        self._syllabus_documents = syllabus_document_repo
        self._llm_usage = llm_usage_repo
        self._settings = settings

    async def generate_feedback(
        self, user_id: uuid.UUID, question_id: uuid.UUID, selected_answer: int | None = None
    ) -> TutorMessage:
        question = await self._questions.get_by_id(question_id)
        if question is None:
            raise NotFoundError(f"Question {question_id} was not found.")

        cached = await self._messages.get_one(
            question_id=question_id, user_id=user_id, selected_answer=selected_answer
        )
        if cached is not None:
            return cached

        is_correct = question.accept_all or (
            selected_answer is not None and selected_answer == question.correct_answer
        )

        chunks = await self._retrieve_context(question)
        citations = await self._to_citations(chunks)

        llm = get_llm(self._settings)
        response: AIMessage = await llm.ainvoke(
            [SystemMessage(content=_build_system_prompt(question, citations, selected_answer, is_correct)), _GENERATE_TURN]
        )
        response_text = get_text_content(response).strip()
        usage = get_usage(response)

        message = await self._messages.create(
            question_id=question_id,
            user_id=user_id,
            role="assistant",
            content=response_text,
            citations=[c.as_dict() for c in citations] or None,
            selected_answer=selected_answer,
            is_correct=is_correct,
            input_tokens=usage.input_tokens if usage else None,
            output_tokens=usage.output_tokens if usage else None,
        )

        if usage is not None:
            # Best-effort: a logging failure here must never lose the
            # explanation that was already generated and stored above.
            try:
                await self._llm_usage.record(
                    user_id=user_id,
                    feature="tutor_feedback",
                    model=self._settings.anthropic_model,
                    usage=usage,
                    request_id=get_request_id(),
                )
            except Exception as exc:
                logger.warning("llm_usage_record_failed", feature="tutor_feedback", error=str(exc))

        return message

    async def _retrieve_context(self, question: Question) -> list[dict[str, Any]]:
        try:
            embedder = await get_embedder(self._settings.embedding_model)
            query_vector = await embed_query(embedder, question.question_text)
            return await chroma_client.query_chunks(
                self._settings, query_embedding=query_vector, subject=question.subject, k=_RETRIEVAL_K
            )
        except Exception:
            # A syllabus-retrieval hiccup (e.g. ChromaDB briefly unreachable)
            # shouldn't block feedback generation — it degrades to
            # question/answer-only grounding instead (mirrors ChatService's
            # _safe_retrieve for the generic RAG store).
            return []

    async def _to_citations(self, chunks: list[dict[str, Any]]) -> list[Citation]:
        """Resolves each retrieved chunk's source_document_id to its
        filename/topic in one batched lookup, so the feedback can show real
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


def _build_system_prompt(
    question: Question, citations: list[Citation], selected_answer: int | None, is_correct: bool
) -> str:
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
        outcome_instructions=_outcome_instructions(question, keys, selected_answer, is_correct),
    )


def _outcome_instructions(question: Question, keys: list[str], selected_answer: int | None, is_correct: bool) -> str:
    if question.accept_all:
        return _VOIDED_INSTRUCTIONS
    if is_correct:
        return _CORRECT_INSTRUCTIONS
    if selected_answer is None or not (0 <= selected_answer < len(keys)):
        return _MISSED_INSTRUCTIONS.format(correct_label=keys[question.correct_answer])
    return _WRONG_INSTRUCTIONS.format(student_label=keys[selected_answer], correct_label=keys[question.correct_answer])


def _student_answer_line(question: Question, keys: list[str], selected_answer: int | None) -> str:
    if selected_answer is None or not (0 <= selected_answer < len(keys)):
        return "Student's submitted answer: (left blank)\n"
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
