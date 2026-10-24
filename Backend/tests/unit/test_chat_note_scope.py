"""Tests for asking the AI Assistant about one chosen note."""

import pytest
from pydantic import ValidationError

from app.api.error_handlers import ApiError
from app.domains.chats.application.services import ChatService
from app.domains.chats.domain.answering import (
    ChatAnswerGenerator,
    GeneratedAnswer,
)
from app.domains.chats.domain.embedding import QuestionEmbeddingProvider
from app.domains.chats.domain.exceptions import (
    NoProcessedNotesError,
    SelectedNoteUnavailableError,
)
from app.domains.chats.domain.models import ChatSource
from app.domains.chats.domain.retrieval import GroundingChunk
from app.domains.chats.infrastructure.memory_repository import (
    InMemoryChatRepository,
)
from app.domains.chats.infrastructure.memory_retrieval import (
    InMemoryReadyNoteChunkRepository,
)
from app.domains.chats.presentation.router import _raise_chat_api_error
from app.domains.chats.presentation.schemas import AskQuestionRequest


class CapturingGenerator(ChatAnswerGenerator):
    """Remember which notes the chunks it was given came from."""

    def __init__(self) -> None:
        self.note_ids_seen: list[list[int]] = []

    async def answer_question(
        self,
        *,
        question,
        chunks,
        response_format=None,
        mode=None,
        history=(),
    ) -> GeneratedAnswer:
        self.note_ids_seen.append([chunk.source.note_id for chunk in chunks])
        return GeneratedAnswer(content="An answer.", sources=(chunks[0].source,))


class FixedEmbedder(QuestionEmbeddingProvider):
    async def embed_question(self, question: str) -> tuple[float, ...]:
        return (0.25,) * 768


def chunk(note_id: int, text: str) -> GroundingChunk:
    return GroundingChunk(
        content=text,
        source=ChatSource(
            note_id=note_id,
            note_title="Note " + str(note_id),
            chunk_id=note_id * 10,
            page=1,
        ),
    )


def make_service(embedder=None):
    generator = CapturingGenerator()
    chunks = InMemoryReadyNoteChunkRepository()
    service = ChatService(
        repository=InMemoryChatRepository(),
        chunk_repository=chunks,
        answer_generator=generator,
        maximum_question_length=4000,
        question_embedding_provider=embedder,
        semantic_search_limit=5,
    )
    return service, chunks, generator


async def seed(chunks) -> None:
    await chunks.replace_user_chunks(
        user_id="u1",
        chunks=(
            chunk(1, "Transformers use attention."),
            chunk(2, "Inflation in Turkey rose."),
            chunk(2, "The exchange rate fell."),
        ),
    )
    await chunks.replace_user_chunks(
        user_id="u2",
        chunks=(chunk(3, "Another student's private note."),),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("use_search", [False, True])
async def test_no_note_chosen_searches_every_note(use_search: bool) -> None:
    embedder = FixedEmbedder() if use_search else None
    service, chunks, generator = make_service(embedder)
    await seed(chunks)
    chat = await service.create_chat(user_id="u1", title=None)

    await service.ask_question(
        chat_id=chat.chat_id, user_id="u1", question="What is in my notes?"
    )

    assert sorted(set(generator.note_ids_seen[0])) == [1, 2]


@pytest.mark.asyncio
@pytest.mark.parametrize("use_search", [False, True])
async def test_chosen_note_limits_the_search_to_that_note(use_search: bool) -> None:
    embedder = FixedEmbedder() if use_search else None
    service, chunks, generator = make_service(embedder)
    await seed(chunks)
    chat = await service.create_chat(user_id="u1", title=None)

    await service.ask_question(
        chat_id=chat.chat_id,
        user_id="u1",
        question="What is in this note?",
        note_id=2,
    )

    assert generator.note_ids_seen[0] == [2, 2]


@pytest.mark.asyncio
async def test_choice_is_sent_every_time_and_can_be_changed() -> None:
    service, chunks, generator = make_service()
    await seed(chunks)
    chat = await service.create_chat(user_id="u1", title=None)

    await service.ask_question(
        chat_id=chat.chat_id, user_id="u1", question="First", note_id=1
    )
    await service.ask_question(
        chat_id=chat.chat_id, user_id="u1", question="Second", note_id=2
    )

    assert generator.note_ids_seen[0] == [1]
    assert generator.note_ids_seen[1] == [2, 2]


@pytest.mark.asyncio
@pytest.mark.parametrize("missing_note_id", [99, 3])
async def test_missing_or_foreign_note_is_unavailable(missing_note_id: int) -> None:
    """Note 99 does not exist. Note 3 belongs to another student."""

    service, chunks, generator = make_service()
    await seed(chunks)
    chat = await service.create_chat(user_id="u1", title=None)

    with pytest.raises(SelectedNoteUnavailableError):
        await service.ask_question(
            chat_id=chat.chat_id,
            user_id="u1",
            question="What is in this note?",
            note_id=missing_note_id,
        )

    assert generator.note_ids_seen == []
    messages, total = await service.list_messages(
        chat_id=chat.chat_id, user_id="u1", page=1, page_size=50
    )
    assert total == 0


@pytest.mark.asyncio
async def test_student_with_no_notes_still_gets_the_original_error() -> None:
    service, _chunks, _generator = make_service()
    chat = await service.create_chat(user_id="u1", title=None)

    with pytest.raises(NoProcessedNotesError):
        await service.ask_question(
            chat_id=chat.chat_id, user_id="u1", question="Anything?"
        )


def test_request_accepts_a_note_id_or_none() -> None:
    assert AskQuestionRequest(content="Hi").note_id is None
    assert AskQuestionRequest(content="Hi", note_id=7).note_id == 7
    assert AskQuestionRequest(content="Hi", note_id="7").note_id == 7


@pytest.mark.parametrize("bad_value", [0, -1, "abc", 1.5])
def test_request_rejects_a_bad_note_id(bad_value) -> None:
    with pytest.raises(ValidationError):
        AskQuestionRequest(content="Hi", note_id=bad_value)


def test_unavailable_note_has_its_own_error_code() -> None:
    with pytest.raises(ApiError) as caught:
        _raise_chat_api_error(SelectedNoteUnavailableError("gone"))
    assert caught.value.code == "SELECTED_NOTE_UNAVAILABLE"
    assert caught.value.status_code == 409
