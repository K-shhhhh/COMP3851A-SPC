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
        assert context == "[SOURCE 1]\nRanked database context"
        return "A database index speeds up selected retrieval. [[SOURCE_IDS:1]]"

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
    assert answer.content == "A database index speeds up selected retrieval."


@pytest.mark.asyncio
async def test_only_sources_used_by_the_answer_are_returned(monkeypatch) -> None:
    """Do not expose every top-k retrieval candidate as a citation."""

    chunks = tuple(
        GroundingChunk(
            content=f"Passage {index}",
            source=ChatSource(
                note_id=1,
                note_title="Database Systems",
                chunk_id=index,
                page=index,
            ),
        )
        for index in range(1, 4)
    )
    monkeypatch.setattr(
        rag_answering,
        "generate_answer",
        lambda *args, **kwargs: "Supported by two passages. [[SOURCE_IDS:2,3]]",
    )
    generator = rag_answering.KrishRagAnswerGenerator(
        top_k=3,
        rank_chunks=False,
    )

    answer = await generator.answer_question(question="Explain it", chunks=chunks)

    assert answer.content == "Supported by two passages."
    assert [source.page for source in answer.sources] == [2, 3]


@pytest.mark.asyncio
async def test_missing_source_marker_falls_back_to_best_ranked_chunk(
    monkeypatch,
) -> None:
    """A provider-format failure must not turn all top-k hits into sources."""

    chunks = tuple(
        GroundingChunk(
            content=f"Passage {index}",
            source=ChatSource(
                note_id=1,
                note_title="Database Systems",
                chunk_id=index,
                page=index,
            ),
        )
        for index in range(1, 4)
    )
    monkeypatch.setattr(
        rag_answering,
        "generate_answer",
        lambda *args, **kwargs: "An answer without the private marker.",
    )
    generator = rag_answering.KrishRagAnswerGenerator(
        top_k=3,
        rank_chunks=False,
    )

    answer = await generator.answer_question(question="Explain it", chunks=chunks)

    assert [source.page for source in answer.sources] == [1]
