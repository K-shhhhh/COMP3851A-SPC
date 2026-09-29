"""Knowledge-graph application use cases."""

from app.domains.knowledge_graph.domain.exceptions import (
    KnowledgeGraphAttachmentNotFoundError,
    KnowledgeGraphNotReadyError,
)
from app.domains.knowledge_graph.domain.models import (
    KnowledgeEdge,
    KnowledgeNode,
)
from app.domains.knowledge_graph.domain.repository import (
    KnowledgeGraphRepository,
)
from app.domains.notes.domain.models import NoteProcessingStatus
from app.domains.notes.domain.repository import AttachmentRepository


class KnowledgeGraphService:
    """Authorize graph reads and coordinate graph replacement."""

    def __init__(
        self,
        *,
        repository: KnowledgeGraphRepository,
        attachment_repository: AttachmentRepository,
    ) -> None:
        self._repository = repository
        self._attachment_repository = attachment_repository

    async def get_graph_for_attachment(
        self,
        *,
        attachment_id: int,
        user_id: str,
    ) -> tuple[list[KnowledgeNode], list[KnowledgeEdge]]:
        """Return an owned, processed My Notes attachment's graph.

        Missing and unauthorized attachments return the same failure so one
        user cannot discover another user's attachment identifiers. Channel
        attachments are deliberately excluded from this first release.
        """

        attachment = await self._attachment_repository.get_owned_attachment(
            attachment_id=attachment_id,
            user_id=user_id,
        )

        if attachment is None or not attachment.appears_in_my_notes:
            raise KnowledgeGraphAttachmentNotFoundError(
                "The requested note was not found."
            )

        if attachment.processing_status != NoteProcessingStatus.READY:
            raise KnowledgeGraphNotReadyError(
                attachment.processing_status
            )

        nodes, edges = await self._repository.get_graph_for_attachment(
            attachment_id
        )

        # The agreed repository contract returns an empty tuple when no graph
        # has yet been persisted for a fully processed document.
        if not nodes and not edges:
            raise KnowledgeGraphNotReadyError(
                attachment.processing_status
            )

        return nodes, edges

    async def replace_graph_for_attachment(
        self,
        *,
        attachment_id: int,
        nodes: list[KnowledgeNode],
        edges: list[KnowledgeEdge],
    ) -> None:
        """Store a complete graph produced by the trusted AI pipeline."""

        self._validate_generated_graph(
            attachment_id=attachment_id,
            nodes=nodes,
            edges=edges,
        )
        await self._repository.replace_graph_for_attachment(
            attachment_id=attachment_id,
            nodes=nodes,
            edges=edges,
        )

    @staticmethod
    def _validate_generated_graph(
        *,
        attachment_id: int,
        nodes: list[KnowledgeNode],
        edges: list[KnowledgeEdge],
    ) -> None:
        """Reject inconsistent generator output before persistence."""

        if attachment_id <= 0:
            raise ValueError("attachment_id must be greater than zero")

        node_ids = {node.id for node in nodes}
        if len(node_ids) != len(nodes):
            raise ValueError("knowledge graph node identifiers must be unique")

        for node in nodes:
            if node.attachment_id != attachment_id:
                raise ValueError("every node must belong to the attachment")

        for edge in edges:
            if edge.attachment_id != attachment_id:
                raise ValueError("every edge must belong to the attachment")
            if edge.source_node_id not in node_ids:
                raise ValueError("edge source node does not exist")
            if edge.target_node_id not in node_ids:
                raise ValueError("edge target node does not exist")
