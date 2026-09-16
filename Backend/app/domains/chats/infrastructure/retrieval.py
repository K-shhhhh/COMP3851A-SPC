"""PostgreSQL/pgvector integration point for authorized ready-note chunks."""

from app.domains.chats.domain.retrieval import ReadyNoteChunkRepository


class PostgreSQLReadyNoteChunkRepository(ReadyNoteChunkRepository):
    """Declare the pending permission-scoped chunk retrieval adapter."""

