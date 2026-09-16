"""PostgreSQL integration point for personal-chat persistence.

The database developer implements ``ChatRepository`` here. Local development
continues to use ``InMemoryChatRepository`` until that adapter and its
integration tests are complete.
"""

from app.domains.chats.domain.repository import ChatRepository


class PostgreSQLChatRepository(ChatRepository):
    """Declare the pending PostgreSQL personal-chat adapter."""

