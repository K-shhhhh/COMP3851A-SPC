"""Unit tests for personal-chat application use cases."""

import pytest

from app.domains.chats.application.services import ChatService
from app.domains.chats.domain.answering import (
    ChatAnswerGenerator,
    GeneratedAnswer,
)
from app.domains.chats.domain.exceptions import (
    AnswerGenerationError,
    ChatNotFoundError,
    NoProcessedNotesError,
)
from app.domains.chats.domain.models import ChatSource
from app.domains.chats.domain.retrieval import GroundingChunk
from app.domains.chats.infrastructure.memory_answering import (
    LocalGroundedAnswerGenerator,
)
from app.domains.chats.infrastructure.memory_repository import (
    InMemoryChatRepository,
)
from app.domains.chats.infrastructure.memory_retrieval import (
    InMemoryReadyNoteChunkRepository,
)


pytestmark = pytest.mark.asyncio


def make_service(answer_generator=None):
    """Build isolated Chat use cases and return seedable dependencies."""

    repository = InMemoryChatRepository()
    chunks = InMemoryReadyNoteChunkRepository()
    service = ChatService(
        repository=repository,
        chunk_repository=chunks,
        answer_generator=(
            answer_generator or LocalGroundedAnswerGenerator()
        ),
        maximum_question_length=4000,
    )
    return service, repository, chunks


def sample_chunk() -> GroundingChunk:
    """Create one ready, already-authorized note chunk."""

    return GroundingChunk(
        content="A database index speeds up selected data retrieval.",
        source=ChatSource(
            note_id=1,
            note_title="Database Indexing",
            chunk_id=7,
            page=4,
        ),
    )


async def test_question_requires_ready_note_chunks() -> None:
    """Reject answering when the student has no processed notes."""

    service, _, _ = make_service()
    chat = await service.create_chat(user_id="user-1", title=None)

    with pytest.raises(NoProcessedNotesError):
        await service.ask_question(
            chat_id=chat.chat_id,
            user_id="user-1",
            question="What is indexing?",
        )


async def test_question_persists_grounded_exchange() -> None:
    """Persist the user question and completed cited answer."""

    service, _, chunks = make_service()
    chat = await service.create_chat(user_id="user-1", title=None)
    await chunks.replace_user_chunks(
        user_id="user-1",
        chunks=(sample_chunk(),),
    )

    exchange = await service.ask_question(
        chat_id=chat.chat_id,
        user_id="user-1",
        question="  What is indexing?  ",
    )
    history, total = await service.list_messages(
        chat_id=chat.chat_id,
        user_id="user-1",
        page=1,
        page_size=50,
    )

    assert exchange.user_message.content == "What is indexing?"
    assert exchange.assistant_message.sources[0].chunk_id == 7
    assert total == 2
    assert history == [exchange.user_message, exchange.assistant_message]


async def test_cross_user_chat_access_is_hidden() -> None:
    """Return the same not-found result for missing and unauthorized chats."""

    service, _, _ = make_service()
    chat = await service.create_chat(user_id="user-1", title=None)

    with pytest.raises(ChatNotFoundError):
        await service.get_chat(chat_id=chat.chat_id, user_id="user-2")


class UnauthorizedSourceAnswerGenerator(ChatAnswerGenerator):
    """Test adapter that attempts to cite a chunk outside the allowed set."""

    async def answer_question(self, *, question, chunks) -> GeneratedAnswer:
        """Return a deliberately unauthorized citation."""

        del question, chunks
        return GeneratedAnswer(
            content="Unsafe answer",
            sources=(
                ChatSource(
                    note_id=999,
                    note_title="Another student's note",
                    chunk_id=999,
                ),
            ),
        )


async def test_answer_cannot_cite_an_unauthorized_chunk() -> None:
    """Reject a provider response that escapes retrieval authorization."""

    service, _, chunks = make_service(UnauthorizedSourceAnswerGenerator())
    chat = await service.create_chat(user_id="user-1", title=None)
    await chunks.replace_user_chunks(
        user_id="user-1",
        chunks=(sample_chunk(),),
    )

    with pytest.raises(AnswerGenerationError):
        await service.ask_question(
            chat_id=chat.chat_id,
            user_id="user-1",
            question="What is indexing?",
        )

