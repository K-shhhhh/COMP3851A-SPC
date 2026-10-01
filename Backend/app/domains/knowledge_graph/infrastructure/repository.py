"""Transactional persistence for attachment-scoped knowledge graphs."""

from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.knowledge_graph.domain.models import (
    KnowledgeEdge,
    KnowledgeNode,
)
from app.domains.knowledge_graph.domain.repository import (
    KnowledgeGraphRepository,
)
from app.models.orm_models import (
    Attachment,
    Chunk,
    KnowledgeEdge as ORMEdge,
    KnowledgeGraph as ORMGraph,
    KnowledgeNode as ORMNode,
)


class PostgreSQLKnowledgeGraphRepository(
    KnowledgeGraphRepository
):
    """Read active graphs and commit complete replacements in one transaction.

    As with the other PostgreSQL adapters, writes own the session transaction:
    callers should not mix unrelated pending writes into this session.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Bind graph operations to the worker's database session."""

        self._session = session

    async def get_graph_for_attachment(
        self,
        attachment_id: int,
    ) -> tuple[list[KnowledgeNode], list[KnowledgeEdge]]:
        # Keep a shared graph lock until the caller's transaction ends so a
        # replacement cannot occur between the node and edge queries.
        graph_id = await self._session.scalar(
            select(ORMGraph.graph_id)
            .join(Attachment, Attachment.attachment_id == ORMGraph.attachment_id)
            .where(
                ORMGraph.attachment_id == attachment_id,
                ORMGraph.deleted_at.is_(None),
                Attachment.deleted_at.is_(None),
            )
            .with_for_update(read=True, of=ORMGraph)
        )
        if graph_id is None:
            return [], []

        stored_nodes = (await self._session.scalars(
            select(ORMNode).where(
                ORMNode.graph_id == graph_id,
                ORMNode.deleted_at.is_(None),
            ).order_by(ORMNode.node_id).execution_options(populate_existing=True)
        )).all()
        stored_edges = (await self._session.scalars(
            select(ORMEdge).where(
                ORMEdge.graph_id == graph_id,
                ORMEdge.deleted_at.is_(None),
            ).order_by(ORMEdge.edge_id).execution_options(populate_existing=True)
        )).all()
        return (
            [KnowledgeNode(
                id=node.node_id, attachment_id=attachment_id,
                title=node.title, topic=node.topic, description=node.description,
                source_chunk_id=node.source_chunk_id,
            ) for node in stored_nodes],
            [KnowledgeEdge(
                id=edge.edge_id, attachment_id=attachment_id,
                source_node_id=edge.source_node_id, target_node_id=edge.target_node_id,
                label=edge.relationship_label,
            ) for edge in stored_edges],
        )

    async def replace_graph_for_attachment(
        self,
        *,
        attachment_id: int,
        nodes: list[KnowledgeNode],
        edges: list[KnowledgeEdge],
    ) -> None:
        """Resolve generator references and atomically replace active contents.

        Old rows are soft-deleted to preserve existing AI-response citations.
        The graph row itself is reused, including when it was soft-deleted.
        """
        try:
            if attachment_id <= 0:
                raise ValueError("attachment_id must be greater than zero")
            temporary_ids = {node.id for node in nodes}
            if len(temporary_ids) != len(nodes):
                raise ValueError("knowledge graph node identifiers must be unique")
            if any(item.attachment_id != attachment_id for item in [*nodes, *edges]):
                raise ValueError("every node and edge must belong to the attachment")
            if any(edge.source_node_id not in temporary_ids or
                   edge.target_node_id not in temporary_ids for edge in edges):
                raise ValueError("edge endpoints must reference generated nodes")

            # Lock the parent even when no graph exists yet. Concurrent first
            # replacements for this attachment then serialize before insertion.
            attachment = (await self._session.execute(
                select(Attachment.attachment_id, Attachment.title).where(
                    Attachment.attachment_id == attachment_id,
                    Attachment.deleted_at.is_(None),
                ).with_for_update()
            )).first()
            if attachment is None:
                raise LookupError("active attachment not found")

            graph = await self._session.scalar(
                select(ORMGraph).where(ORMGraph.attachment_id == attachment_id)
                .with_for_update().execution_options(populate_existing=True)
            )
            orders = {node.source_chunk_id for node in nodes if node.source_chunk_id is not None}
            chunk_ids = {}
            if orders:
                chunk_ids = dict((await self._session.execute(
                    select(Chunk.chunk_order, Chunk.chunk_id).where(
                        Chunk.attachment_id == attachment_id,
                        Chunk.chunk_order.in_(orders),
                        Chunk.deleted_at.is_(None),
                    )
                )).all())
                if orders - chunk_ids.keys():
                    raise ValueError("source chunk order does not exist for this attachment")

            now = datetime.now(timezone.utc)
            if graph is None:
                graph = ORMGraph(
                    attachment_id=attachment_id, graph_name=attachment.title,
                    created_at=now, last_updated_at=now,
                )
                self._session.add(graph)
                await self._session.flush()
            else:
                graph.deleted_at = None
                graph.last_updated_at = now
                for model in (ORMEdge, ORMNode):
                    await self._session.execute(
                        update(model).where(
                            model.graph_id == graph.graph_id,
                            model.deleted_at.is_(None),
                        ).values(deleted_at=now, last_updated_at=now)
                    )

            inserted_nodes = [ORMNode(
                graph_id=graph.graph_id, title=node.title, topic=node.topic,
                description=node.description,
                source_chunk_id=(chunk_ids[node.source_chunk_id]
                                 if node.source_chunk_id is not None else None),
                created_at=now,
            ) for node in nodes]
            self._session.add_all(inserted_nodes)
            await self._session.flush()
            node_ids = {node.id: stored.node_id for node, stored in zip(nodes, inserted_nodes)}

            self._session.add_all([ORMEdge(
                graph_id=graph.graph_id,
                source_node_id=node_ids[edge.source_node_id],
                target_node_id=node_ids[edge.target_node_id],
                relationship_label=edge.label, created_at=now,
            ) for edge in edges])
            await self._session.commit()
        except BaseException:
            await self._session.rollback()
            raise
