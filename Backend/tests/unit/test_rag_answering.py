"""Tests for ranked-chunk handoff to the RAG answering adapter."""

import pytest

from app.domains.chats.domain.models import ChatSource
from app.domains.chats.domain.retrieval import GroundingChunk
from app.domains.chats.infrastructure import rag_answering


@pytest.mark.asyncio
async def test_ranked_chunks_are_not_embedded_again(monkeypatch) -> None:
    """Trust PostgreSQL order when database semantic search is enabled."""

    def fail_if_embedded(text: str):
        raise AssertionError(f"unexpected embedding call for {text}")

    def fake_generate(question, context, *, response_format=None, mode=None):
        assert question == "What is indexing?"
        assert context == "Ranked database context"
        return "A database index speeds up selected retrieval."

    monkeypatch.setattr(rag_answering, "embed_text", fail_if_embedded)
    monkeypatch.setattr(rag_answering, "generate_answer", fake_generate)
    source = ChatSource(
        note_id=1,
        note_title="Database Indexing",
        chunk_id=7,
        page=4,
    )
    generator = rag_answering.KrishRagAnswerGenerator(
        top_k=5,
        rank_chunks=False,
    )

    answer = await generator.answer_question(
        question="What is indexing?",
        chunks=(
            GroundingChunk(
                content="Ranked database context",
                source=source,
            ),
        ),
    )

    assert answer.sources == (source,)
