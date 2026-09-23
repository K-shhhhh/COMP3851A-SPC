from __future__ import annotations
import enum
import ipaddress
import uuid
from datetime import datetime
from typing import Any
from pgvector.sqlalchemy import VECTOR
from sqlalchemy import (BigInteger, Boolean, CheckConstraint, DateTime, Float, ForeignKey, Identity, Index, Integer, Text, UniqueConstraint, text)
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# -----------------------------------------------------------------------------
# Base Model
# -----------------------------------------------------------------------------
class Base(DeclarativeBase):
    pass



# -----------------------------------------------------------------------------
# ENUMs

# Python enums mapped to the PostgreSQL enum types created by the SQL schema.
# create_type=False means SQLAlchemy will use the existing PostgreSQL enum types
# rather than trying to CREATE TYPE / DROP TYPE itself.
# -----------------------------------------------------------------------------


class ActivityStatus(str, enum.Enum):
    ACTIVE = "active"
    DEACTIVATED = "deactivated"


class UserRole(str, enum.Enum):
    STUDENT = "student"
    ADMIN = "admin"


class MemberRole(str, enum.Enum):
    ADMIN = "admin"
    MEMBER = "member"


class GroupType(str, enum.Enum):
    PERSONAL = "personal"
    PRIVATE = "private"
    PUBLIC = "public"


class AttachmentStatus(str, enum.Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class AIMode(str, enum.Enum):
    QUIZ = "quiz"
    SUMMARIZER = "summarizer"
    FACILITATOR = "facilitator"
    DEFAULT = "default"


class Rating(str, enum.Enum):
    GOOD = "good"
    BAD = "bad"


class Action(str, enum.Enum):
    LOGIN = "login"
    LOGOUT = "logout"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    UPLOAD = "upload"
    DOWNLOAD = "download"
    SEND = "send"
    EDIT = "edit"
    JOIN = "join"
    LEAVE = "leave"
    AI_REQUEST = "ai_request"
    AI_FEEDBACK = "ai_feedback"


def pg_enum(enum_class: type[enum.Enum], name: str) -> PGEnum:
    """Mapping a Python Enum to an already-existing PostgreSQL ENUM type."""
    return PGEnum(
        enum_class,
        name=name,
        values_callable=lambda cls: [member.value for member in cls],
        create_type=False,
    )


# -----------------------------------------------------------------------------
# ORM models
# -----------------------------------------------------------------------------


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    fullname: Mapped[str] = mapped_column(Text, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    user_role: Mapped[UserRole] = mapped_column(
        pg_enum(UserRole, "user_roles"), nullable=False
    )
    status: Mapped[ActivityStatus] = mapped_column(
        pg_enum(ActivityStatus, "activity_status"),
        nullable=False,
        server_default=text("'active'"),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    groups_created: Mapped[list[Group]] = relationship(
        back_populates="creator",
        foreign_keys="Group.created_by",
    )
    groups_administered: Mapped[list[Group]] = relationship(
        back_populates="current_admin_user",
        foreign_keys="Group.current_admin",
    )
    memberships: Mapped[list[Membership]] = relationship(back_populates="user")
    channels_created: Mapped[list[Channel]] = relationship(
        back_populates="creator",
        foreign_keys="Channel.created_by",
    )
    messages: Mapped[list[Message]] = relationship(back_populates="user")
    attachments_uploaded: Mapped[list[Attachment]] = relationship(
        back_populates="uploader",
        foreign_keys="Attachment.uploaded_by",
    )
    knowledge_graphs: Mapped[list[KnowledgeGraph]] = relationship(back_populates="user")
    ai_response_feedbacks: Mapped[list[AIResponseFeedback]] = relationship(
        back_populates="user"
    )


class Group(Base):
    __tablename__ = "groups"

    group_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    group_name: Mapped[str] = mapped_column(Text, nullable=False)
    group_type: Mapped[GroupType] = mapped_column(
        pg_enum(GroupType, "group_types"), nullable=False
    )
    description: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.user_id", name="fk_group_created_by_for_groups"),
    )
    current_admin: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.user_id", name="fk_current_admin_for_groups"),
        nullable=False,
    )
    max_members: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    creator: Mapped[User] = relationship(
        back_populates="groups_created",
        foreign_keys=[created_by],
    )
    current_admin_user: Mapped[User] = relationship(
        back_populates="groups_administered",
        foreign_keys=[current_admin],
    )
    memberships: Mapped[list[Membership]] = relationship(back_populates="group")
    channels: Mapped[list[Channel]] = relationship(back_populates="group")
    attachments: Mapped[list[Attachment]] = relationship(back_populates="group")


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "group_id",
            name="uq_memberships_user_group",
        ),
    )

    membership_id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(always=True),
        primary_key=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.user_id", name="fk_user_id_for_memberships"),
        nullable=False,
    )
    group_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("groups.group_id", name="fk_group_id_for_memberships"),
        nullable=False,
    )
    member_role: Mapped[MemberRole] = mapped_column(
        pg_enum(MemberRole, "member_roles"), nullable=False
    )
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user: Mapped[User] = relationship(back_populates="memberships")
    group: Mapped[Group] = relationship(back_populates="memberships")


class Channel(Base):
    __tablename__ = "channels"

    channel_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    channel_name: Mapped[str] = mapped_column(Text, nullable=False)
    group_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("groups.group_id", name="fk_group_id_for_channels"),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.user_id", name="fk_created_by_for_channels"),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    group: Mapped[Group] = relationship(back_populates="channels")
    creator: Mapped[User] = relationship(
        back_populates="channels_created",
        foreign_keys=[created_by],
    )
    messages: Mapped[list[Message]] = relationship(back_populates="channel")
    attachments: Mapped[list[Attachment]] = relationship(back_populates="channel")


class Message(Base):
    __tablename__ = "messages"

    message_id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(always=True),
        primary_key=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.user_id", name="fk_user_id_for_messages"),
        nullable=False,
    )
    channel_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("channels.channel_id", name="fk_channel_id_for_messages"),
        nullable=False,
    )
    message_content: Mapped[str] = mapped_column(Text, nullable=False)
    ai_mode_used: Mapped[AIMode] = mapped_column(
        pg_enum(AIMode, "ai_modes"),
        nullable=False,
        server_default=text("'default'"),
    )
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="messages")
    channel: Mapped[Channel] = relationship(back_populates="messages")
    attachments: Mapped[list[Attachment]] = relationship(back_populates="message")
    ai_responses: Mapped[list[AIResponse]] = relationship(back_populates="message")


class Attachment(Base):
    __tablename__ = "attachments"
    __table_args__ = (
        CheckConstraint(
            "file_size_bytes >= 0",
            name="ck_attachments_file_size",
        ),
        CheckConstraint(
            "processing_progress between 0 and 100",
            name="ck_attachments_processing_progress",
        ),
    )

    attachment_id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(always=True),
        primary_key=True,
    )
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.user_id", name="fk_uploaded_by_for_attachments"),
        nullable=False,
    )
    channel_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("channels.channel_id", name="fk_channel_id_for_attachments"),
    )
    group_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("groups.group_id", name="fk_group_id_for_attachments"),
    )
    message_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("messages.message_id", name="fk_message_id_for_attachments"),
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    file_name: Mapped[str] = mapped_column(Text, nullable=False)
    file_type: Mapped[str] = mapped_column(Text, nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    object_path: Mapped[str | None] = mapped_column(Text)
    processing_status: Mapped[AttachmentStatus] = mapped_column(
        pg_enum(AttachmentStatus, "attachment_status"),
        nullable=False,
        server_default=text("'queued'"),
    )
    processing_progress: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    processing_error: Mapped[str | None] = mapped_column(Text)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    uploader: Mapped[User] = relationship(
        back_populates="attachments_uploaded",
        foreign_keys=[uploaded_by],
    )
    channel: Mapped[Channel | None] = relationship(back_populates="attachments")
    group: Mapped[Group | None] = relationship(back_populates="attachments")
    message: Mapped[Message | None] = relationship(back_populates="attachments")
    chunks: Mapped[list[Chunk]] = relationship(back_populates="attachment")


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (
        UniqueConstraint(
            "attachment_id",
            "chunk_order",
            name="uq_chunks_attachment_order",
        ),
    )

    chunk_id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(always=True),
        primary_key=True,
    )
    attachment_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("attachments.attachment_id", name="fk_attachment_id_for_chunks"),
        nullable=False,
    )
    chunk_order: Mapped[int] = mapped_column(Integer, nullable=False)
    source_page: Mapped[int | None] = mapped_column(Integer)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_model_version: Mapped[str] = mapped_column(Text, nullable=False)
    vector_embedding: Mapped[list[float]] = mapped_column(VECTOR(768), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    attachment: Mapped[Attachment] = relationship(back_populates="chunks")
    ai_response_sources: Mapped[list[AIResponseSource]] = relationship(
        back_populates="chunk"
    )


class KnowledgeGraph(Base):
    __tablename__ = "knowledge_graphs"

    graph_id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(always=True),
        primary_key=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.user_id", name="fk_user_id_for_knowledge_graphs"),
        nullable=False,
    )
    graph_name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="knowledge_graphs")
    nodes: Mapped[list[KnowledgeNode]] = relationship(back_populates="graph")
    edges: Mapped[list[KnowledgeEdge]] = relationship(back_populates="graph")


class KnowledgeNode(Base):
    __tablename__ = "knowledge_nodes"

    node_id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(always=True),
        primary_key=True,
    )
    graph_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("knowledge_graphs.graph_id", name="fk_graph_id_for_knowledge_nodes"),
        nullable=False,
    )
    node_label: Mapped[str] = mapped_column(Text, nullable=False)
    node_properties: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    position_x: Mapped[float | None] = mapped_column(Float)
    position_y: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    graph: Mapped[KnowledgeGraph] = relationship(back_populates="nodes")
    source_edges: Mapped[list[KnowledgeEdge]] = relationship(
        back_populates="source_node",
        foreign_keys="KnowledgeEdge.source_node_id",
    )
    target_edges: Mapped[list[KnowledgeEdge]] = relationship(
        back_populates="target_node",
        foreign_keys="KnowledgeEdge.target_node_id",
    )
    ai_response_sources: Mapped[list[AIResponseSource]] = relationship(
        back_populates="node"
    )


class KnowledgeEdge(Base):
    __tablename__ = "knowledge_edges"

    edge_id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(always=True),
        primary_key=True,
    )
    graph_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("knowledge_graphs.graph_id", name="fk_graph_id_for_knowledge_edges"),
        nullable=False,
    )
    source_node_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "knowledge_nodes.node_id",
            name="fk_source_node_id_for_knowledge_edges",
        ),
        nullable=False,
    )
    target_node_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "knowledge_nodes.node_id",
            name="fk_target_node_id_for_knowledge_edges",
        ),
        nullable=False,
    )
    edge_label: Mapped[str | None] = mapped_column(Text)
    edge_properties: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    graph: Mapped[KnowledgeGraph] = relationship(back_populates="edges")
    source_node: Mapped[KnowledgeNode] = relationship(
        back_populates="source_edges",
        foreign_keys=[source_node_id],
    )
    target_node: Mapped[KnowledgeNode] = relationship(
        back_populates="target_edges",
        foreign_keys=[target_node_id],
    )
    ai_response_sources: Mapped[list[AIResponseSource]] = relationship(
        back_populates="edge"
    )


class AIResponse(Base):
    __tablename__ = "ai_responses"

    response_id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(always=True),
        primary_key=True,
    )
    message_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("messages.message_id", name="fk_message_id_for_ai_responses"),
        nullable=False,
    )
    ai_mode_used: Mapped[AIMode] = mapped_column(
        pg_enum(AIMode, "ai_modes"),
        nullable=False,
        server_default=text("'default'"),
    )
    response: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    confidence_score: Mapped[float | None] = mapped_column(Float)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    is_selected: Mapped[bool] = mapped_column(Boolean, nullable=False)
    execution_time_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    message: Mapped[Message] = relationship(back_populates="ai_responses")
    sources: Mapped[list[AIResponseSource]] = relationship(back_populates="response")
    feedbacks: Mapped[list[AIResponseFeedback]] = relationship(back_populates="response")


class AIResponseSource(Base):
    __tablename__ = "ai_response_sources"

    retrieval_id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(always=True),
        primary_key=True,
    )
    response_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("ai_responses.response_id", name="fk_response_id_for_ai_response_sources"),
        nullable=False,
    )
    chunk_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("chunks.chunk_id", name="fk_chunk_id_for_ai_response_sources"),
    )
    node_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("knowledge_nodes.node_id", name="fk_node_id_for_ai_response_sources"),
    )
    edge_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("knowledge_edges.edge_id", name="fk_edge_id_for_ai_response_sources"),
    )
    similarity_score: Mapped[float] = mapped_column(Float, nullable=False)
    rerank_score: Mapped[float | None] = mapped_column(Float)
    is_used_in_prompt: Mapped[bool] = mapped_column(Boolean, nullable=False)

    response: Mapped[AIResponse] = relationship(back_populates="sources")
    chunk: Mapped[Chunk | None] = relationship(back_populates="ai_response_sources")
    node: Mapped[KnowledgeNode | None] = relationship(back_populates="ai_response_sources")
    edge: Mapped[KnowledgeEdge | None] = relationship(back_populates="ai_response_sources")


class AIResponseFeedback(Base):
    __tablename__ = "ai_response_feedbacks"

    feedback_id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(always=True),
        primary_key=True,
    )
    response_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "ai_responses.response_id",
            name="fk_response_id_for_ai_response_feedbacks",
        ),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.user_id", name="fk_user_id_for_ai_response_feedbacks"),
        nullable=False,
    )
    rating: Mapped[Rating] = mapped_column(
        pg_enum(Rating, "ratings"), nullable=False
    )
    feedback_text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    response: Mapped[AIResponse] = relationship(back_populates="feedbacks")
    user: Mapped[User] = relationship(back_populates="ai_response_feedbacks")


class UserActivityLog(Base):
    __tablename__ = "user_activity_logs"

    activity_id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(always=True),
        primary_key=True,
    )
    # Intentionally no ForeignKey: the Version 4 SQL schema does not define one.
    user_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    user_action: Mapped[Action] = mapped_column(
        pg_enum(Action, "actions"), nullable=False
    )
    entity_type: Mapped[str | None] = mapped_column(Text)
    entity_id: Mapped[str | None] = mapped_column(Text)
    ip_address: Mapped[ipaddress.IPv4Address | ipaddress.IPv6Address | None] = mapped_column(
        INET
    )
    user_agent: Mapped[str | None] = mapped_column(Text)

    # "metadata" is reserved by SQLAlchemy Declarative, so the Python attribute is named metadata_ while the actual PostgreSQL column remains "metadata".
    metadata_: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


# -----------------------------------------------------------------------------
# Indexes 
# -----------------------------------------------------------------------------

# Allows the same channel name to be reused after the old channel is soft-deleted.
Index(
    "uq_channels_group_name",
    Channel.group_id,
    Channel.channel_name,
    unique=True,
    postgresql_where=Channel.deleted_at.is_(None),
)

Index("ix_memberships_group_id", Membership.group_id)

Index(
    "ix_messages_channel_sent_at",
    Message.channel_id,
    Message.sent_at.desc(),
)
Index("ix_messages_user_id", Message.user_id)

Index("ix_attachments_uploaded_by", Attachment.uploaded_by)
Index("ix_attachments_channel_id", Attachment.channel_id)
Index("ix_attachments_group_id", Attachment.group_id)
Index("ix_attachments_message_id", Attachment.message_id)

Index(
    "ix_chunks_vector_embedding_hnsw",
    Chunk.vector_embedding,
    postgresql_using="hnsw",
    postgresql_with={"m": 16, "ef_construction": 64},
    postgresql_ops={"vector_embedding": "vector_cosine_ops"},
)
