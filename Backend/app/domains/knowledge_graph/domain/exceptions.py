"""Expected knowledge-graph use-case failures."""

from app.domains.notes.domain.models import NoteProcessingStatus


class KnowledgeGraphError(Exception):
    """Base exception for expected knowledge-graph failures."""


class KnowledgeGraphAttachmentNotFoundError(KnowledgeGraphError):
    """Raised when the requested My Notes attachment is inaccessible."""


class KnowledgeGraphNotReadyError(KnowledgeGraphError):
    """Raised when document processing or graph generation is incomplete."""

    def __init__(
        self,
        processing_status: NoteProcessingStatus,
    ) -> None:
        self.processing_status = processing_status
        super().__init__("The knowledge graph is not ready yet.")
