"""Application use cases for personal AI Assistant conversations."""

from datetime import datetime, timezone
from app.domains.chats.application.prompt_security import (
    validate_user_question,
)

from app.domains.chats.domain.answering import ChatAnswerGenerator
from app.domains.chats.domain.exceptions import (
    AnswerGenerationError,
    ChatNotFoundError,
    InvalidChatTitleError,
    InvalidQuestionError,
    NoProcessedNotesError,
)
from app.domains.chats.domain.models import (
    ChatExchange,
    ChatMessage,
    ChatMessageRole,
    PersonalChat,
)
from app.domains.chats.domain.repository import ChatRepository
from app.domains.chats.domain.retrieval import ReadyNoteChunkRepository


class ChatService:
    """Coordinate ownership, history, retrieval, and synchronous answering."""

    def __init__(
        self,
        *,
        repository: ChatRepository,
        chunk_repository: ReadyNoteChunkRepository,
        answer_generator: ChatAnswerGenerator,
        maximum_question_length: int,
    ) -> None:
        """Initialize the use cases with replaceable infrastructure adapters."""

        if maximum_question_length <= 0:
            raise ValueError("maximum_question_length must be positive")

        self._repository = repository
        self._chunk_repository = chunk_repository
        self._answer_generator = answer_generator
        self._maximum_question_length = maximum_question_length

    async def create_chat(
        self,
        *,
        user_id: str,
        title: str | None,
    ) -> PersonalChat:
        """Create one personal conversation owned by the current student."""

        normalized_title = self._normalize_title(title, allow_default=True)
        return await self._repository.create_chat(
            owner_id=user_id,
            title=normalized_title,
        )

    async def list_chats(
        self,
        *,
        user_id: str,
        page: int,
        page_size: int,
    ) -> tuple[list[PersonalChat], int]:
        """List only the current student's non-deleted conversations."""

        offset = (page - 1) * page_size
        return await self._repository.list_owned_chats(
            owner_id=user_id,
            offset=offset,
            limit=page_size,
        )

    async def get_chat(self, *, chat_id: str, user_id: str) -> PersonalChat:
        """Return a chat without revealing another student's identifiers."""

        chat = await self._repository.get_owned_chat(
            chat_id=chat_id,
            owner_id=user_id,
        )

        if chat is None:
            raise ChatNotFoundError("Chat not found.")

        return chat

    async def rename_chat(
        self,
        *,
        chat_id: str,
        user_id: str,
        title: str,
    ) -> PersonalChat:
        """Rename one owned personal conversation."""

        normalized_title = self._normalize_title(title, allow_default=False)
        chat = await self._repository.rename_owned_chat(
            chat_id=chat_id,
            owner_id=user_id,
            title=normalized_title,
        )

        if chat is None:
            raise ChatNotFoundError("Chat not found.")

        return chat

    async def delete_chat(self, *, chat_id: str, user_id: str) -> None:
        """Soft-delete one owned conversation and hide its message history."""

        deleted = await self._repository.soft_delete_owned_chat(
            chat_id=chat_id,
            owner_id=user_id,
            deleted_at=datetime.now(timezone.utc),
        )

        if not deleted:
            raise ChatNotFoundError("Chat not found.")

    async def list_messages(
        self,
        *,
        chat_id: str,
        user_id: str,
        page: int,
        page_size: int,
    ) -> tuple[list[ChatMessage], int]:
        """Return history only after verifying personal-chat ownership."""

        await self.get_chat(chat_id=chat_id, user_id=user_id)
        offset = (page - 1) * page_size
        return await self._repository.list_messages(
            chat_id=chat_id,
            offset=offset,
            limit=page_size,
        )

    async def ask_question(
        self,
        *,
        chat_id: str,
        user_id: str,
        question: str,
    ) -> ChatExchange:
        """Answer synchronously using only the student's ready note chunks.

        The API owns authentication, chat ownership, validation, and message
        persistence. Krish's adapter owns similarity search and answer
        generation across the already authorized chunks supplied here.
        """

        await self.get_chat(chat_id=chat_id, user_id=user_id)
        normalized_question = self._normalize_question(question)

        # The repository is the security boundary: it must exclude other
        # students' chunks, failed/deleted notes, and channel attachments.
        chunks = await self._chunk_repository.list_ready_chunks_for_user(
            user_id=user_id
        )

        if not chunks:
            raise NoProcessedNotesError(
                "Upload and process at least one note before asking a question."
            )

        user_message = await self._repository.create_message(
            chat_id=chat_id,
            role=ChatMessageRole.USER,
            content=normalized_question,
        )

        try:
            answer = await self._answer_generator.answer_question(
                question=normalized_question,
                chunks=chunks,
            )
            self._validate_sources(answer.sources, chunks)
        except Exception as exc:
            raise AnswerGenerationError(
                "The AI answer could not be generated."
            ) from exc

        assistant_message = await self._repository.create_message(
            chat_id=chat_id,
            role=ChatMessageRole.ASSISTANT,
            content=answer.content.strip(),
            sources=answer.sources,
        )

        return ChatExchange(
            user_message=user_message,
            assistant_message=assistant_message,
        )

    @staticmethod
    def _normalize_title(title: str | None, *, allow_default: bool) -> str:
        """Normalize a title while preserving the New chat default."""

        normalized = (title or "").strip()

        if not normalized and allow_default:
            return "New chat"
        if not normalized:
            raise InvalidChatTitleError("Chat title must not be empty.")
        if len(normalized) > 100:
            raise InvalidChatTitleError(
                "Chat title must not exceed 100 characters."
            )

        return normalized

    def _normalize_question(self, question: str) -> str:
        """Normalize and enforce the authoritative question limits."""

        normalized = question.strip()

        if not normalized:
            raise InvalidQuestionError("Question must not be empty.")
        if len(normalized) > self._maximum_question_length:
            raise InvalidQuestionError(
                "Question exceeds the configured length limit."
            )
        validate_user_question(normalized)
        return normalized

    @staticmethod
    def _validate_sources(sources, chunks) -> None:
        """Reject citations that were not present in authorized retrieval."""

        allowed = {
            (
                chunk.source.note_id,
                chunk.source.chunk_id,
            )
            for chunk in chunks
        }

        if any(
            (source.note_id, source.chunk_id) not in allowed
            for source in sources
        ):
            raise ValueError(
                "The answer adapter returned an unauthorized source."
            )

