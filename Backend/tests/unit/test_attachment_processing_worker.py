"""Unit tests for knowledge-graph orchestration in the attachment worker."""

import asyncio

from app.domains.knowledge_graph.domain.models import KnowledgeNode
from app.workers.attachment import processing_worker


class RecordingGraphService:
    """Capture graph replacement without requiring PostgreSQL."""

    def __init__(self) -> None:
        self.replacement: dict | None = None

    async def replace_graph_for_attachment(
        self,
        *,
        attachment_id: int,
        nodes: list,
        edges: list,
    ) -> None:
        self.replacement = {
            "attachment_id": attachment_id,
            "nodes": nodes,
            "edges": edges,
        }


def test_worker_passes_raw_chunks_to_graph_generator(monkeypatch) -> None:
    """The graph generator receives the pre-embedding chunk contract."""

    attachment_id = 42
    chunks = [{"chunk_id": 0, "text": "Gradient descent updates weights."}]
    generated_nodes = [
        KnowledgeNode(
            id=0,
            attachment_id=attachment_id,
            title="Gradient Descent",
            topic="Optimisation",
            description="An iterative optimisation method.",
            source_chunk_id=0,
        )
    ]
    received: dict = {}

    def fake_generate(candidate_attachment_id: int, candidate_chunks: list[dict]):
        received["attachment_id"] = candidate_attachment_id
        received["chunks"] = candidate_chunks
        return generated_nodes, []

    monkeypatch.setattr(
        processing_worker,
        "_generate_graph_sync",
        fake_generate,
    )
    service = RecordingGraphService()

    asyncio.run(
        processing_worker._generate_and_store_graph(
            attachment_id=attachment_id,
            chunks=chunks,
            graph_service=service,
        )
    )

    assert received == {
        "attachment_id": attachment_id,
        "chunks": chunks,
    }
    assert service.replacement == {
        "attachment_id": attachment_id,
        "nodes": generated_nodes,
        "edges": [],
    }
