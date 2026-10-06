from __future__ import annotations
import enum
import ipaddress
import uuid
from datetime import datetime
from typing import Any
from pgvector.sqlalchemy import VECTOR
from sqlalchemy import (BigInteger, Boolean, CheckConstraint, Computed, DateTime, Float, ForeignKey, ForeignKeyConstraint, Identity, Index, Integer, Text, UniqueConstraint, func, text)
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
    OWNER = "owner"
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
    groups_owned: Mapped[list[Group]] = relationship(
        back_populates="current_owner_user",
        foreign_keys="Group.current_owner",
    )
    memberships: Mapped[list[Membership]] = relationship(back_populates="user")
    channels_created: Mapped[list[Channel]] = relationship(
        back_populates="creator",
        foreign_keys="Channel.created_by",
    )
    messages: Mapped[list[Message]] = relationship(back_populates="user")
    message_mentions: Mapped[list[MessageMention]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    attachments_uploaded: Mapped[list[Attachment]] = relationship(
        back_populates="uploader",
        foreign_keys="Attachment.uploaded_by",
    )
    ai_response_feedbacks: Mapped[list[AIResponseFeedback]] = relationship(
        back_populates="user"
    )


class Group(Base):
    __tablename__ = "groups"
    __table_args__ = (
        ForeignKeyConstraint(
            ["group_id", "current_owner", "active_owner_role"],
            ["memberships.group_id", "memberships.user_id", "memberships.member_role"],
            name="fk_groups_active_owner", use_alter=True,
            deferrable=True, initially="DEFERRED",
        ),
    )

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
    current_owner: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.user_id", name="fk_current_owner_for_groups"),
        nullable=False,
    )
    max_members: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Always require an owner membership, including for soft-deleted groups.
    # This generated constant cannot be overwritten to bypass the deferred FK.
    active_owner_role: Mapped[MemberRole] = mapped_column(
        pg_enum(MemberRole, "member_roles"),
        Computed("'owner'::member_roles", persisted=True), nullable=False,
    )

    creator: Mapped[User] = relationship(
        back_populates="groups_created",
        foreign_keys=[created_by],
    )
    current_owner_user: Mapped[User] = relationship(
        back_populates="groups_owned",
        foreign_keys=[current_owner],
    )
    memberships: Mapped[list[Membership]] = relationship(
        back_populates="group", foreign_keys="Membership.group_id",
    )
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
        UniqueConstraint("group_id", "user_id", "member_role", name="uq_memberships_group_user_role"),
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
    group: Mapped[Group] = relationship(back_populates="memberships", foreign_keys=[group_id])


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
    ai_mode_used: Mapped[AIMode | None] = mapped_column(
        pg_enum(AIMode, "ai_modes"),
        nullable=True,
    )
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="messages")
    channel: Mapped[Channel] = relationship(back_populates="messages")
    attachments: Mapped[list[Attachment]] = relationship(back_populates="message")
    ai_responses: Mapped[list[AIResponse]] = relationship(back_populates="message")
    mentions: Mapped[list[MessageMention]] = relationship(
        back_populates="message",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class MessageMention(Base):
    __tablename__ = "message_mentions"

    message_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("messages.message_id", ondelete="CASCADE"),
        primary_key=True,
        autoincrement=False,
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )

    message: Mapped[Message] = relationship(back_populates="mentions")
    user: Mapped[User] = relationship(back_populates="message_mentions")


class Attachment(Base):
    __tablename__ = "attachments"
    __table_args__ = (
        CheckConstraint(
            "file_size_bytes > 0",
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
    object_path: Mapped[str] = mapped_column(Text, nullable=False)
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
    show_in_library: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true"),
    )
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    processing_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    processing_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
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

    # A graph may not exist yet while the attachment is awaiting processing.
    knowledge_graph: Mapped[KnowledgeGraph | None] = relationship(
        back_populates="attachment", uselist=False,
    )


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
    knowledge_nodes: Mapped[list[KnowledgeNode]] = relationship(back_populates="source_chunk")
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
    attachment_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("attachments.attachment_id", name="fk_attachment_id_for_knowledge_graphs"),
        nullable=False,
    )
    graph_name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    attachment: Mapped[Attachment] = relationship(back_populates="knowledge_graph")
    nodes: Mapped[list[KnowledgeNode]] = relationship(back_populates="graph")
    edges: Mapped[list[KnowledgeEdge]] = relationship(back_populates="graph")


class KnowledgeNode(Base):
    __tablename__ = "knowledge_nodes"
    __table_args__ = (
        UniqueConstraint("graph_id", "node_id", name="uq_knowledge_nodes_graph_node"),
    )

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
    title: Mapped[str] = mapped_column(Text, nullable=False)
    topic: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    source_chunk_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("chunks.chunk_id", name="fk_source_chunk_id_for_knowledge_nodes"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    graph: Mapped[KnowledgeGraph] = relationship(back_populates="nodes")
    source_chunk: Mapped[Chunk | None] = relationship(back_populates="knowledge_nodes")
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
    __table_args__ = (
        ForeignKeyConstraint(
            ["graph_id", "source_node_id"],
            ["knowledge_nodes.graph_id", "knowledge_nodes.node_id"],
            name="fk_edge_source_same_graph",
        ),
        ForeignKeyConstraint(
            ["graph_id", "target_node_id"],
            ["knowledge_nodes.graph_id", "knowledge_nodes.node_id"],
            name="fk_edge_target_same_graph",
        ),
    )

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
    relationship_label: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

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
    # Intentionally no ForeignKey: the SQL schema does not define one.
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
    func.lower(Channel.channel_name),
    unique=True,
    postgresql_where=Channel.deleted_at.is_(None),
)

Index("ix_memberships_group_id", Membership.group_id)
Index(
    "uq_memberships_group_owner", Membership.group_id, unique=True,
    postgresql_where=Membership.member_role == MemberRole.OWNER,
)

Index(
    "uq_knowledge_graphs_attachment",
    KnowledgeGraph.attachment_id,
    unique=True,
)

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
    "ix_users_active_email", func.lower(User.email),
    postgresql_where=User.deleted_at.is_(None) & (User.status == ActivityStatus.ACTIVE),
)
Index(
    "ix_groups_active_type_updated", Group.group_type,
    func.coalesce(Group.last_updated_at, Group.created_at).desc(), Group.group_id,
    postgresql_where=Group.deleted_at.is_(None),
)
Index(
    "ix_groups_active_owner_updated", Group.created_by,
    func.coalesce(Group.last_updated_at, Group.created_at).desc(), Group.group_id,
    postgresql_where=Group.deleted_at.is_(None),
)
Index("ix_channels_group_id", Channel.group_id)
Index(
    "ix_channels_active_group_created", Channel.group_id, Channel.created_at, Channel.channel_id,
    postgresql_where=Channel.deleted_at.is_(None),
)
Index(
    "ix_messages_active_channel_sent", Message.channel_id, Message.sent_at, Message.message_id,
    postgresql_where=Message.deleted_at.is_(None),
)
Index("ix_message_mentions_user_id", MessageMention.user_id)
Index(
    "ix_attachments_ready_group_channel", Attachment.group_id, Attachment.channel_id, Attachment.attachment_id,
    postgresql_where=Attachment.deleted_at.is_(None) & (Attachment.processing_status == AttachmentStatus.READY),
)
Index(
    "ix_chunks_active_attachment_order", Chunk.attachment_id, Chunk.chunk_order, Chunk.chunk_id,
    postgresql_where=Chunk.deleted_at.is_(None),
)
Index(
    "ix_ai_responses_message_attempt", AIResponse.message_id,
    AIResponse.attempt_number.desc(), AIResponse.response_id.desc(),
)
Index("ix_ai_response_sources_response", AIResponseSource.response_id, AIResponseSource.retrieval_id)
Index("ix_ai_response_sources_chunk", AIResponseSource.chunk_id)
Index("ix_ai_response_sources_node", AIResponseSource.node_id)
Index("ix_ai_response_sources_edge", AIResponseSource.edge_id)

Index(
    "ix_knowledge_nodes_active_graph", KnowledgeNode.graph_id, KnowledgeNode.node_id,
    postgresql_where=KnowledgeNode.deleted_at.is_(None),
)
Index(
    "ix_knowledge_edges_active_graph", KnowledgeEdge.graph_id, KnowledgeEdge.edge_id,
    postgresql_where=KnowledgeEdge.deleted_at.is_(None),
)
Index(
    "ix_attachments_active_library_owner_uploaded",
    Attachment.uploaded_by, Attachment.uploaded_at.desc(),
    postgresql_where=Attachment.deleted_at.is_(None) & Attachment.show_in_library.is_(True),
)

Index(
    "ix_chunks_vector_embedding_hnsw",
    Chunk.vector_embedding,
    postgresql_using="hnsw",
    postgresql_with={"m": 16, "ef_construction": 64},
    postgresql_ops={"vector_embedding": "vector_cosine_ops"},
)
