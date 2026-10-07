"""Integration point for Krish's synchronous ``ask_question`` pipeline.

Krish implements ``ChatAnswerGenerator`` here after exposing the tested RAG
function as importable Python code. The adapter receives only chunks that the
retrieval repository has already scoped to the authenticated student.

When PostgreSQL semantic search is disabled, this adapter preserves the local
Python ranking fallback. When it is enabled, the repository has already
returned authorized chunks in cosine-similarity order and this adapter uses
them directly without re-embedding stored chunks.
"""

from app.domains.chats.domain.answering import ChatAnswerGenerator, GeneratedAnswer
from app.domains.chats.domain.retrieval import GroundingChunk

import asyncio

from app.ai.rag.embedding import embed_text
from app.ai.rag.vector_store import cosine_similarity
from app.ai.providers.llama_provider import generate_answer
from app.ai.rag.small_talk import answer_small_talk


_REFUSAL_MARKER = "not available in the supplied study material"


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
    ) -> GeneratedAnswer:
        """Return an answer grounded only in the supplied authorized chunks.

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
            question_embedding = await asyncio.to_thread(embed_text, question)
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

        # Build the context block directly from .content.
        context = "\n\n".join(chunk.content for chunk in top_chunks)

        # Generate the grounded answer off the event loop.
        answer_text = await asyncio.to_thread(
            generate_answer, question, context, response_format=response_format, mode=mode
        )

        # Carry over each used chunk's citation information.
        sources = _distinct_sources(top_chunks)
        # An answer that says the material does not cover the question did not
        # use the passages, so citing them would be misleading.
        if _REFUSAL_MARKER in answer_text.lower():
            sources = ()

        return GeneratedAnswer(content=answer_text, sources=sources)
