"""Expected personal-chat failures without HTTP-specific behaviour."""


class ChatError(Exception):
    """Base exception for expected personal-chat failures."""


class ChatNotFoundError(ChatError):
    """Raised when a chat is missing or inaccessible to the current user."""


class InvalidChatTitleError(ChatError):
    """Raised when a normalized conversation title is invalid."""


class InvalidQuestionError(ChatError):
    """Raised when a normalized question is empty or too long."""


class NoProcessedNotesError(ChatError):
    """Raised when the student has no ready note chunks to search."""


class AnswerGenerationError(ChatError):
    """Raised when the configured synchronous answer adapter fails."""

