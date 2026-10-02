"""Relationship and constraint regression tests for attachment knowledge graphs."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import Column, Integer, MetaData, Table, create_engine
from sqlalchemy.dialects.postgresql import dialect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import configure_mappers
from sqlalchemy.schema import CreateIndex, CreateTable

from app.models.orm_models import Attachment, Chunk, KnowledgeEdge, KnowledgeGraph, KnowledgeNode


def test_relationship_cardinalities_and_postgresql_ddl():
    configure_mappers()
    assert not Attachment.knowledge_graph.property.uselist
    assert Attachment.chunks.property.uselist
    assert KnowledgeGraph.nodes.property.uselist
    assert KnowledgeGraph.edges.property.uselist
    assert not KnowledgeNode.source_chunk.property.uselist
    assert KnowledgeNode.__table__.c.source_chunk_id.nullable
    assert Chunk.knowledge_nodes.property.uselist
    for model in (KnowledgeGraph, KnowledgeNode, KnowledgeEdge):
        assert str(CreateTable(model.__table__).compile(dialect=dialect()))
    index, = KnowledgeGraph.__table__.indexes
    sql = str(CreateIndex(index).compile(dialect=dialect()))
    assert "UNIQUE INDEX" in sql and "WHERE" not in sql


@pytest.fixture
def graph_db():
    # SQLite checks relational behavior; PostgreSQL DDL is compiled above.
    metadata = MetaData()
    Table("attachments", metadata, Column("attachment_id", Integer, primary_key=True))
    for model in (Chunk, KnowledgeGraph, KnowledgeNode, KnowledgeEdge):
        table = model.__table__.to_metadata(metadata)
        for column in table.primary_key:
            column.type = Integer()
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        metadata.create_all(connection)
        connection.execute(metadata.tables["attachments"].insert(), [
            {"attachment_id": 1}, {"attachment_id": 2},
        ])
        now = datetime.now(timezone.utc)
        connection.execute(metadata.tables["knowledge_graphs"].insert(), [
            dict(graph_id=1, attachment_id=1, graph_name="One", created_at=now),
            dict(graph_id=2, attachment_id=2, graph_name="Two", created_at=now),
        ])
        connection.execute(metadata.tables["chunks"].insert(), [
            dict(chunk_id=i + 1, attachment_id=1, chunk_order=i, source_type="text",
                 chunk_content="Supporting text", embedding_model_version="test",
                 vector_embedding=[0.0] * 768, created_at=now)
            for i in range(2)
        ])
        connection.execute(metadata.tables["knowledge_nodes"].insert(), [
            dict(node_id=i, graph_id=2 if i == 4 else 1, title=f"Concept {i}",
                 topic="Topic", description="Concept description",
                 source_chunk_id=1 if i in (1, 2) else None, created_at=now)
            for i in range(1, 5)
        ])
        yield connection, metadata.tables, now
    engine.dispose()


@pytest.mark.parametrize("soft_deleted", [False, True])
def test_attachment_cannot_have_a_second_graph(graph_db, soft_deleted):
    connection, tables, now = graph_db
    graphs = tables["knowledge_graphs"]
    if soft_deleted:
        connection.execute(graphs.update().where(graphs.c.graph_id == 1).values(deleted_at=now))
    with pytest.raises(IntegrityError):
        connection.execute(graphs.insert().values(
            attachment_id=1, graph_name="Duplicate", created_at=now,
        ))


def test_multiple_concepts_can_share_a_chunk_or_have_no_source(graph_db):
    connection, tables, now = graph_db
    nodes = connection.execute(tables["knowledge_nodes"].select()).mappings().all()
    assert [node["source_chunk_id"] for node in nodes] == [1, 1, None, None]
    # Multiple edges within a graph are valid, including nodes without a source chunk.
    connection.execute(tables["knowledge_edges"].insert(), [
        dict(graph_id=1, source_node_id=1, target_node_id=2, created_at=now),
        dict(graph_id=1, source_node_id=2, target_node_id=3, created_at=now),
    ])
    with pytest.raises(IntegrityError):
        connection.execute(tables["knowledge_nodes"].update().where(
            tables["knowledge_nodes"].c.node_id == 3,
        ).values(source_chunk_id=999))


@pytest.mark.parametrize("source,target", [(4, 1), (1, 4)])
def test_edges_cannot_connect_nodes_from_another_graph(graph_db, source, target):
    connection, tables, now = graph_db
    with pytest.raises(IntegrityError):
        connection.execute(tables["knowledge_edges"].insert().values(
            graph_id=1, source_node_id=source, target_node_id=target, created_at=now,
        ))
