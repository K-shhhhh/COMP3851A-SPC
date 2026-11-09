"""Integration point for Krish's synchronous ``ask_question`` pipeline.

Krish implements ``ChatAnswerGenerator`` here after exposing the tested RAG
function as importable Python code. The adapter receives only chunks that the
retrieval repository has already scoped to the authenticated student.

When PostgreSQL semantic search is disabled, this adapter preserves the local
Python ranking fallback. When it is enabled, the repository has already
returned authorized chunks in cosine-similarity order and this adapter uses
them directly without re-embedding stored chunks.
"""

from app.domains.chats.domain.answering import (
    ChatAnswerGenerator,
    ConversationTurn,
    GeneratedAnswer,
)
from app.domains.chats.domain.followups import build_retrieval_query
from app.domains.chats.domain.retrieval import GroundingChunk

import asyncio
import re

from app.ai.rag.embedding import embed_text
from app.ai.rag.vector_store import cosine_similarity
from app.ai.providers.llama_provider import generate_answer
from app.ai.rag.small_talk import answer_small_talk


_REFUSAL_MARKER = "not available in the supplied study material"

# The model does not always use the exact marker. A short reply that opens by
# saying the notes do not mention the topic is also a refusal. Longer replies
# or phrases late in the text are left alone, so a partial answer that ends
# with "the notes do not mention X" keeps its sources.
_SOFT_REFUSAL_PHRASES = (
    "does not mention",
    "do not mention",
    "doesn't mention",
    "is not mentioned",
    "are not mentioned",
    "not mentioned in",
    "not covered in",
    "no mention of",
    "does not cover",
    "do not cover",
    "does not discuss",
    "not in your notes",
)
_SOFT_REFUSAL_OPENING_CHARS = 150
_SOFT_REFUSAL_MAX_CHARS = 600

# The model selects the retrieved passages that actually support its answer.
# This marker is removed before the reply is persisted or returned to the UI.
# If a provider omits it, we conservatively cite only the highest-ranked
# passage instead of presenting every retrieved chunk as if it were used.
# The marker is matched anywhere in the reply, because the model sometimes
# places it before a closing full stop instead of at the very end.
_SOURCE_IDS_MARKER = re.compile(
    r"\s*\[\[\s*SOURCE_IDS\s*:\s*([0-9,\s]*)\]\]",
    re.IGNORECASE,
)


def _is_refusal(answer_text: str) -> bool:
    """Return whether the reply says the notes do not cover the question."""

    text = answer_text.lower()
    if _REFUSAL_MARKER in text:
        return True
    if len(text) > _SOFT_REFUSAL_MAX_CHARS:
        return False
    opening = text[:_SOFT_REFUSAL_OPENING_CHARS]
    for phrase in _SOFT_REFUSAL_PHRASES:
        if phrase in opening:
            return True
    return False


_FACILITATOR_FALLBACK_QUESTION = (
    "What do you already know about this, and which part of your notes "
    "could help you work it out?"
)


def _facilitator_question(answer_text: str) -> str:
    """Reduce a facilitator reply to its final guiding question.

    The model sometimes states findings before asking. Only the last question
    is kept, so no fact from the notes reaches the student. A reply with no
    question gets a neutral guiding question instead.
    """

    text = answer_text.strip()
    last_mark = text.rfind("?")
    if last_mark == -1:
        return _FACILITATOR_FALLBACK_QUESTION

    # Start of the final sentence: just after the last sentence break before it.
    head = text[:last_mark]
    start = 0
    for separator in (". ", "! ", "? ", "\n"):
        position = head.rfind(separator)
        if position != -1:
            candidate = position + len(separator)
            if candidate > start:
                start = candidate

    question = text[start:last_mark + 1].strip()
    if len(question) < 10:
        return _FACILITATOR_FALLBACK_QUESTION
    return question


# Added under every full refusal so the student knows how to get an answer.
# SPC only answers from uploaded material, so the next step is to add a source.
_UPLOAD_TIP = (
    "Tip: upload a PDF that covers this topic, or select a note that does, "
    "and ask again."
)


def _with_upload_tip(answer_text: str) -> str:
    """Add the upload tip to a refusal once."""

    if _UPLOAD_TIP.lower() in answer_text.lower():
        return answer_text
    return f"{answer_text.rstrip()}\n\n{_UPLOAD_TIP}"


_NUMBERED_QUESTION_LINE = re.compile(r"^\s*\d+[.)]\s")
_ANSWER_OPTION_LINE = re.compile(r"^\s*[A-Da-d][.)]\s")


def _asks_for_answers(question: str) -> bool:
    """Return whether the student explicitly asked for the quiz answers."""

    return "answer" in question.lower()


def _hide_quiz_answers(answer_text: str) -> str:
    """Keep only the numbered questions of a quiz reply.

    The model sometimes prints the answer on the lines under each question.
    Text before the first question and lettered options are kept, and every
    other line under a numbered question is dropped.
    """

    kept_lines = []
    inside_questions = False
    for line in answer_text.split("\n"):
        if _NUMBERED_QUESTION_LINE.match(line):
            inside_questions = True
            kept_lines.append(line)
            continue
        if not inside_questions:
            kept_lines.append(line)
            continue
        if line.strip() == "":
            kept_lines.append("")
            continue
        if _ANSWER_OPTION_LINE.match(line):
            kept_lines.append(line)

    cleaned = "\n".join(kept_lines).strip()
    return re.sub(r"\n{3,}", "\n\n", cleaned)


def _distinct_sources(chunks):
    """One source per page of each note, in ranked order.

    The best passages often come from the same page, which used to list the
    same document several times under one answer.
    """

    seen = set()
    sources = []
    for chunk in chunks:
        source = chunk.source
        key = (source.note_id, source.page)
        if key in seen:
            continue
        seen.add(key)
        sources.append(source)
    return tuple(sources)


def _labelled_context(chunks: list[GroundingChunk]) -> str:
    """Give each retrieved passage a stable ID for citation selection."""

    return "\n\n".join(
        f"[SOURCE {index}]\n{chunk.content}"
        for index, chunk in enumerate(chunks, start=1)
    )


def _selected_source_chunks(
    answer_text: str,
    chunks: list[GroundingChunk],
) -> tuple[str, list[GroundingChunk]]:
    """Strip the private marker and return only passages the model used.

    A missing marker can happen during a provider/model transition. The safe
    fallback is the first semantic-search result, not all top-k candidates.
    Invalid IDs are ignored rather than becoming fabricated citations.
    """

    matches = list(_SOURCE_IDS_MARKER.finditer(answer_text))
    if not matches:
        return answer_text.strip(), chunks[:1]

    # The last marker decides the citations and every marker is removed.
    match = matches[-1]
    cleaned_answer = _SOURCE_IDS_MARKER.sub("", answer_text).strip()
    selected: list[GroundingChunk] = []
    seen_indexes: set[int] = set()
    for raw_id in match.group(1).split(","):
        raw_id = raw_id.strip()
        if not raw_id.isdigit():
            continue
        index = int(raw_id)
        if index in seen_indexes or index < 1 or index > len(chunks):
            continue
        seen_indexes.add(index)
        selected.append(chunks[index - 1])
    return cleaned_answer, selected


class KrishRagAnswerGenerator(ChatAnswerGenerator):
    """Ranks already-authorized chunks by relevance, then generates an answer."""

    def __init__(self, top_k: int = 5, *, rank_chunks: bool = True) -> None:
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        self.top_k = top_k
        self.rank_chunks = rank_chunks

    async def answer_question(
        self,
        *,
        question: str,
        chunks: tuple[GroundingChunk, ...],
        response_format: str | None = None,
        mode: str | None = None,
        history: tuple[ConversationTurn, ...] = (),
    ) -> GeneratedAnswer:
        """Return an answer grounded only in the supplied authorized chunks.

        history is the last few turns of the same chat. It is used twice: a
        short follow up is ranked together with the previous question so the
        right chunks are found, and the turns go to the model so it knows
        what "that" or "it" refers to.

        embed_text() and generate_answer() are blocking calls under the hood
        (real network I/O to Ollama/OpenRouter). Each is wrapped in
        asyncio.to_thread() so it runs on a background thread instead of
        blocking the event loop -- lets FastAPI keep handling other requests
        while this one is waiting on a model response.

        response_format and mode are accepted here to match the updated
        ChatAnswerGenerator interface, and passed straight through to
        generate_answer -- this adapter doesn't interpret either itself.
        mode defaults to "default" (Companion) behaviour when not supplied,
        which is the only value personal chat ever needs -- group chat's
        @-mention modes are the intended caller for the other three.
        """
        # A message that is only social chat ("okay thanks", "hi") gets a short
        # friendly reply. It needs no search, no model call and no sources.
        small_talk_reply = answer_small_talk(question)
        if small_talk_reply is not None:
            return GeneratedAnswer(content=small_talk_reply, sources=())

        if not chunks:
            raise ValueError("answer_question called with no chunks -- caller should check for this before invoking the adapter")

        if self.rank_chunks:
            # Local fallback: rank authorized chunks in Python.
            previous_questions = []
            for turn in history:
                if turn.role == "user":
                    previous_questions.append(turn.content)
            search_text = build_retrieval_query(question, previous_questions)
            question_embedding = await asyncio.to_thread(embed_text, search_text)
            scored_chunks = []
            for chunk in chunks:
                chunk_embedding = await asyncio.to_thread(
                    embed_text,
                    chunk.content,
                )
                score = cosine_similarity(question_embedding, chunk_embedding)
                scored_chunks.append((score, chunk))
            scored_chunks.sort(key=lambda pair: pair[0], reverse=True)
            top_chunks = [chunk for _, chunk in scored_chunks[: self.top_k]]
        else:
            # PostgreSQL has already applied HNSW cosine ranking and LIMIT.
            top_chunks = list(chunks[: self.top_k])

        # Label passages so the model can tell us which retrieved chunks
        # actually support the answer. Retrieval candidates are not citations
        # until the answer uses them.
        context = _labelled_context(top_chunks)

        # Generate the grounded answer off the event loop.
        generation_options = {"response_format": response_format, "mode": mode}
        if history:
            # Only sent when there is something to send, so a first question
            # behaves exactly as before.
            history_payload = []
            for turn in history:
                history_payload.append({"role": turn.role, "content": turn.content})
            generation_options["history"] = history_payload
        answer_text = await asyncio.to_thread(
            generate_answer, question, context, **generation_options
        )

        # Keep only the passages selected by the grounded answer. The private
        # selection marker never reaches chat history or the frontend.
        answer_text, source_chunks = _selected_source_chunks(
            answer_text,
            top_chunks,
        )
        sources = _distinct_sources(source_chunks)
        # Quiz questions must not come with their answers printed underneath.
        if mode == "quiz" and not _asks_for_answers(question):
            answer_text = _hide_quiz_answers(answer_text)
        # An answer that says the material does not cover the question did not
        # use the passages, so citing them would be misleading.
        if _is_refusal(answer_text):
            sources = ()
            answer_text = _with_upload_tip(answer_text)
        # A facilitator reply is a guiding question, not a fact from the
        # notes, so there is nothing to cite and listing pages would hand the
        # student the answer's location.
        if mode == "facilitator":
            sources = ()
            # Keep only the guiding question so no finding is revealed.
            if not _is_refusal(answer_text):
                answer_text = _facilitator_question(answer_text)

        return GeneratedAnswer(content=answer_text, sources=sources)
