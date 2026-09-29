"""Unit tests for attachment-scoped knowledge-graph use cases."""

import pytest

from app.domains.knowledge_graph.application.services import (
    KnowledgeGraphService,
)
from app.domains.knowledge_graph.domain.exceptions import (
    KnowledgeGraphAttachmentNotFoundError,
    KnowledgeGraphNotReadyError,
)
from app.domains.knowledge_graph.domain.models import (
    KnowledgeEdge,
    KnowledgeNode,
)
from app.domains.knowledge_graph.infrastructure.memory_repository import (
    InMemoryKnowledgeGraphRepository,
)
from app.domains.notes.domain.models import NoteProcessingStatus
from app.domains.notes.infrastructure.memory_repository import (
    InMemoryAttachmentRepository,
)


pytestmark = pytest.mark.asyncio


async def create_note(
    repository: InMemoryAttachmentRepository,
    *,
    user_id: str = "user-1",
    ready: bool = True,
):
    """Create one My Notes attachment for a service test."""

    attachment = await repository.create_attachment(
        uploaded_by=user_id,
        title="Neural Networks",
        file_name="neural-networks.pdf",
        file_type="application/pdf",
        file_size_bytes=100,
        object_path="/private/neural-networks.pdf",
    )

    if ready:
        attachment = await repository.update_processing_status(
            attachment_id=attachment.attachment_id,
            processing_status=NoteProcessingStatus.READY,
            processing_progress=100,
        )

    assert attachment is not None
    return attachment


def create_service(
    attachments: InMemoryAttachmentRepository,
    graphs: InMemoryKnowledgeGraphRepository,
) -> KnowledgeGraphService:
    """Build a service from isolated in-memory adapters."""

    return KnowledgeGraphService(
        repository=graphs,
        attachment_repository=attachments,
    )


async def test_owned_ready_note_returns_its_graph() -> None:
    attachments = InMemoryAttachmentRepository()
    graphs = InMemoryKnowledgeGraphRepository()
    service = create_service(attachments, graphs)
    attachment = await create_note(attachments)

    nodes = [
        KnowledgeNode(
            id=1,
            attachment_id=attachment.attachment_id,
            title="Gradient Descent",
            topic="Optimisation",
            description="Updates model parameters using gradients.",
            source_chunk_id=10,
        )
    ]
    await service.replace_graph_for_attachment(
        attachment_id=attachment.attachment_id,
        nodes=nodes,
        edges=[],
    )

    stored_nodes, stored_edges = await service.get_graph_for_attachment(
        attachment_id=attachment.attachment_id,
        user_id="user-1",
    )

    assert stored_nodes == nodes
    assert stored_edges == []


async def test_graph_read_hides_another_users_attachment() -> None:
    attachments = InMemoryAttachmentRepository()
    graphs = InMemoryKnowledgeGraphRepository()
    service = create_service(attachments, graphs)
    attachment = await create_note(attachments, user_id="owner")

    with pytest.raises(KnowledgeGraphAttachmentNotFoundError):
        await service.get_graph_for_attachment(
            attachment_id=attachment.attachment_id,
            user_id="other-user",
        )


async def test_graph_read_rejects_unprocessed_note() -> None:
    attachments = InMemoryAttachmentRepository()
    graphs = InMemoryKnowledgeGraphRepository()
    service = create_service(attachments, graphs)
    attachment = await create_note(attachments, ready=False)

    with pytest.raises(KnowledgeGraphNotReadyError) as captured:
        await service.get_graph_for_attachment(
            attachment_id=attachment.attachment_id,
            user_id="user-1",
        )

    assert captured.value.processing_status == NoteProcessingStatus.QUEUED


async def test_graph_replacement_rejects_missing_edge_node() -> None:
    service = create_service(
        InMemoryAttachmentRepository(),
        InMemoryKnowledgeGraphRepository(),
    )
    nodes = [
        KnowledgeNode(
            id=1,
            attachment_id=1,
            title="Concept",
            topic="Topic",
            description="Description",
        )
    ]
    edges = [
        KnowledgeEdge(
            id=1,
            attachment_id=1,
            source_node_id=1,
            target_node_id=999,
            label="depends on",
        )
    ]

    with pytest.raises(ValueError, match="target node"):
        await service.replace_graph_for_attachment(
            attachment_id=1,
            nodes=nodes,
            edges=edges,
        )
