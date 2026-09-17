"""Integration point for Krish's synchronous ``ask_question`` pipeline.

Krish implements ``ChatAnswerGenerator`` here after exposing the tested RAG
function as importable Python code. The adapter receives only chunks that the
retrieval repository has already scoped to the authenticated student.

Note on embeddings: GroundingChunk carries only .content and .source, no
precomputed vector. Repository-side filtering only handles ownership/status
(not semantic relevance) -- this adapter is responsible for embedding the
question, embedding each supplied chunk, and ranking them by similarity
itself. This keeps the repository simple (access control only) and keeps
all RAG/semantic logic in one place, owned here.
"""

from app.domains.chats.domain.answering import ChatAnswerGenerator, GeneratedAnswer
from app.domains.chats.domain.retrieval import GroundingChunk

import asyncio

from app.ai.rag.embedding import embed_text
from app.ai.rag.vector_store import cosine_similarity
from app.ai.providers.llama_provider import generate_answer


class KrishRagAnswerGenerator(ChatAnswerGenerator):
    """Ranks already-authorized chunks by relevance, then generates an answer."""

    def __init__(self, top_k: int = 5) -> None:
        self.top_k = top_k

    async def answer_question(
        self,
        *,
        question: str,
        chunks: tuple[GroundingChunk, ...],
    ) -> GeneratedAnswer:
        """Return an answer grounded only in the supplied authorized chunks.

        embed_text() and generate_answer() are blocking calls under the hood
        (real network I/O to Ollama/OpenRouter). Each is wrapped in
        asyncio.to_thread() so it runs on a background thread instead of
        blocking the event loop -- lets FastAPI keep handling other requests
        while this one is waiting on a model response.
        """
        if not chunks:
            raise ValueError("answer_question called with no chunks -- caller should check for this before invoking the adapter")

        # 1. Embed the question once (off the event loop)
        question_embedding = await asyncio.to_thread(embed_text, question)

        # 2. Embed every supplied chunk and score it against the question.
        #    No embeddings arrive pre-attached, so this happens fresh each call.
        scored_chunks = []
        for chunk in chunks:
            chunk_embedding = await asyncio.to_thread(embed_text, chunk.content)
            score = cosine_similarity(question_embedding, chunk_embedding)
            scored_chunks.append((score, chunk))

        # 3. Keep only the top_k most relevant
        scored_chunks.sort(key=lambda pair: pair[0], reverse=True)
        top_chunks = [chunk for _, chunk in scored_chunks[: self.top_k]]

        # 4. Build the context block directly from .content (no dict wrapping needed)
        context = "\n\n".join(chunk.content for chunk in top_chunks)

        # 5. Generate the grounded answer (off the event loop)
        answer_text = await asyncio.to_thread(generate_answer, question, context)

        # 6. Carry over each used chunk's citation info (.source is already a ChatSource)
        sources = tuple(chunk.source for chunk in top_chunks)

        return GeneratedAnswer(content=answer_text, sources=sources)
