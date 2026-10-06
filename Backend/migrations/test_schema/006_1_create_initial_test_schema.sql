/*
Version: 6.1

Existing tables:	users, groups, memberships, channels, messages, message_mentions, attachments, chunks,
                	knowledge_graphs, knowledge_nodes, knowledge_edges,
(15 in total)   	ai_responses, ai_response_sources, ai_response_feedbacks,
                	user_activity_logs

Updated tables: groups, memberships, message_mentions, attachments, knowledge_graphs, knowledge_nodes, knowledge_edges

Changes:    Renamed attribute "current_admin" to "current_owner" and a new constraint to ensure the owner is a current member of the group.
            Added new attribtue "active_owner_role", new enum value "owner" for member_roles enum and an index in Memberships table. 
            Added not null constraints to the composite keys of Message_Mentions table.
            Added "show_in_library" attribute in Attachments table.
            Restructured Knowledge_Graphs, Knowledge_Nodes and Knowledge_Edges tables: attributes, relationships, constraints and their indexes.

Notes:	Deletion rules may be implemented as required in future updates.
		Besides, future updates should focus more on constraints and indexes of the tables related to knowledge graph, AI responses and activity logs.
*/

create extension if not exists vector;
create type activity_status as enum ('active', 'deactivated');
create type user_roles as enum ('student','admin');
create type member_roles as enum ('owner', 'admin', 'member');
create type group_types as enum ('personal', 'private', 'public');
create type attachment_status as enum('queued', 'processing', 'ready', 'failed');
create type ai_modes as enum ('quiz', 'summarizer','facilitator','default');
create type ratings as enum ('good', 'bad');
create type actions as enum ('login', 'logout', 'create', 'update', 'delete', 'upload', 'download', 'send', 'edit', 'join', 'leave', 'ai_request', 'ai_feedback');

create table if not exists users (
    user_id uuid primary key,
    email text not null unique,
    fullname text not null,
    password_hash text not null,
    user_role user_roles not null,
    status activity_status default 'active' not null,
    created_at timestamptz not null,
    last_updated_at timestamptz,
	deleted_at timestamptz
);

create table if not exists groups (
    group_id uuid primary key,
    group_name text not null,
    group_type group_types not null,
    description text,
    created_by uuid not null,
    current_owner uuid not null,
    max_members int not null,
    created_at timestamptz not null,
    last_updated_at timestamptz,
	deleted_at timestamptz,

	constraint fk_group_created_by_for_groups foreign key (created_by)
	references users(user_id),

	constraint fk_current_owner_for_groups foreign key (current_owner)
	references users(user_id)
);

create table if not exists memberships (
    membership_id bigint generated always as identity primary key,
    user_id uuid not null,
    group_id uuid not null,
    member_role member_roles not null,
    joined_at timestamptz not null,

	constraint fk_user_id_for_memberships foreign key (user_id)
	references users(user_id),

	constraint fk_group_id_for_memberships foreign key (group_id)
	references groups(group_id),

	constraint uq_memberships_user_group unique (user_id, group_id),
    constraint uq_memberships_group_user_role unique (group_id, user_id, member_role)
);

create table if not exists channels (
    channel_id uuid primary key,
    channel_name text not null,
    group_id uuid not null,
    description text,
    created_by uuid not null,
    created_at timestamptz not null,
    last_updated_at timestamptz,
	deleted_at timestamptz,

	constraint fk_group_id_for_channels foreign key (group_id)
	references groups(group_id),

	constraint fk_created_by_for_channels foreign key (created_by)
	references users(user_id)
);

create table if not exists messages (
    message_id bigint generated always as identity primary key,
    user_id uuid not null,
    channel_id uuid not null,
    message_content text not null,
    ai_mode_used ai_modes,
    sent_at timestamptz not null,
    edited_at timestamptz,
    deleted_at timestamptz,

	constraint fk_user_id_for_messages foreign key (user_id)
	references users(user_id),

	constraint fk_channel_id_for_messages foreign key (channel_id)
	references channels(channel_id)
);

create table if not exists message_mentions (
    message_id bigint not null references messages(message_id) on delete cascade,
    user_id uuid not null references users(user_id) on delete cascade,
    primary key (message_id, user_id)
);

create table if not exists attachments (
    attachment_id bigint generated always as identity primary key,
    uploaded_by uuid not null,
    channel_id uuid,
	group_id uuid,
    message_id bigint,
	title text not null,
    file_name text not null,
    file_type text not null,
    file_size_bytes bigint not null,
    object_path text not null,
    processing_status attachment_status default 'queued' not null,
	processing_progress int default 0 not null,
	processing_error text,
    show_in_library boolean default true not null,
    uploaded_at timestamptz not null,
    last_updated_at timestamptz,
	deleted_at timestamptz,

	constraint fk_uploaded_by_for_attachments foreign key (uploaded_by)
	references users(user_id),

	constraint fk_channel_id_for_attachments foreign key (channel_id)
	references channels(channel_id),

	constraint fk_group_id_for_attachments foreign key (group_id)
	references groups(group_id),

	constraint fk_message_id_for_attachments foreign key (message_id)
	references messages(message_id),

	constraint ck_attachments_file_size check (file_size_bytes > 0),

	constraint ck_attachments_processing_progress check (processing_progress between 0 and 100)
);

create table if not exists chunks (
    chunk_id bigint generated always as identity primary key,
    attachment_id bigint not null,
    chunk_order int not null,
	source_page int,
	source_type text not null,
    chunk_content text not null,
    embedding_model_version text not null,
    vector_embedding vector(768) not null,
    created_at timestamptz not null,
	deleted_at timestamptz,

	constraint fk_attachment_id_for_chunks foreign key (attachment_id)
	references attachments(attachment_id),

	constraint uq_chunks_attachment_order unique (attachment_id, chunk_order)
);

create table if not exists knowledge_graphs (
    graph_id bigint generated always as identity primary key,
    attachment_id bigint not null,
    graph_name text not null,
    description text,
    created_at timestamptz not null,
    last_updated_at timestamptz,
    deleted_at timestamptz,

	constraint fk_attachment_id_for_knowledge_graphs foreign key (attachment_id)
	references attachments(attachment_id)
);

create table if not exists knowledge_nodes (
    node_id bigint generated always as identity primary key,
    graph_id bigint not null,
    title text not null,
    topic text not null,
    description text not null,
    source_chunk_id bigint,
    created_at timestamptz not null,
    last_updated_at timestamptz,
    deleted_at timestamptz,

	constraint fk_graph_id_for_knowledge_nodes foreign key (graph_id)
	references knowledge_graphs(graph_id),

    constraint fk_source_chunk_id_for_knowledge_nodes foreign key (source_chunk_id)
	references chunks(chunk_id),

    constraint uq_knowledge_nodes_graph_node unique (graph_id, node_id)
);

create table if not exists knowledge_edges (
    edge_id bigint generated always as identity primary key,
    graph_id bigint not null,
    source_node_id bigint not null,
    target_node_id bigint not null,
    relationship_label text,
    created_at timestamptz not null,
    last_updated_at timestamptz,
    deleted_at timestamptz,

	constraint fk_graph_id_for_knowledge_edges foreign key (graph_id)
	references knowledge_graphs(graph_id),

	constraint fk_source_node_id_for_knowledge_edges foreign key (source_node_id)
	references knowledge_nodes(node_id),

	constraint fk_target_node_id_for_knowledge_edges foreign key (target_node_id)
	references knowledge_nodes(node_id),

    constraint fk_edge_source_same_graph foreign key (graph_id, source_node_id)
    references knowledge_nodes(graph_id, node_id),

    constraint fk_edge_target_same_graph foreign key (graph_id, target_node_id)
    references knowledge_nodes(graph_id, node_id)
);

create table if not exists ai_responses (
    response_id bigint generated always as identity primary key,
    message_id bigint not null,
    ai_mode_used ai_modes default 'default' not null,
    response jsonb not null,
    confidence_score double precision,
    attempt_number int not null,
    is_selected boolean not null,
    execution_time_ms int not null,
    token_count int not null,
    generated_at timestamptz not null,

	constraint fk_message_id_for_ai_responses foreign key (message_id)
	references messages(message_id)
);

create table if not exists ai_response_sources (
    retrieval_id bigint generated always as identity primary key,
    response_id bigint not null,
    chunk_id bigint,
    node_id bigint,
    edge_id bigint,
    similarity_score double precision not null,
    rerank_score double precision,
    is_used_in_prompt boolean not null,


	constraint fk_response_id_for_ai_response_sources foreign key (response_id)
	references ai_responses(response_id),

	constraint fk_chunk_id_for_ai_response_sources foreign key (chunk_id)
	references chunks(chunk_id),

	constraint fk_node_id_for_ai_response_sources foreign key (node_id)
	references knowledge_nodes(node_id),

	constraint fk_edge_id_for_ai_response_sources foreign key (edge_id)
	references knowledge_edges(edge_id)
);

create table if not exists ai_response_feedbacks (
    feedback_id bigint generated always as identity primary key,
    response_id bigint not null,
    user_id uuid not null,
    rating ratings not null,
    feedback_text text,
    created_at timestamptz not null,

	constraint fk_response_id_for_ai_response_feedbacks foreign key (response_id)
	references ai_responses(response_id),

	constraint fk_user_id_for_ai_response_feedbacks foreign key (user_id)
	references users(user_id)
);

create table if not exists user_activity_logs (
    activity_id bigint generated always as identity primary key,
    user_id uuid,
    user_action actions not null,
    entity_type text,
    entity_id text,
    ip_address inet,
    user_agent text,
    metadata jsonb,
    created_at timestamptz not null
);


-- Memberships have no deleted_at: leaving hard-deletes the membership.
create unique index uq_memberships_group_owner on memberships (group_id) where member_role = 'owner';

-- Every group, including personal and soft-deleted groups, retains an owner. The generated constant cannot be overwritten or become NULL to bypass the FK.
alter table groups add column active_owner_role member_roles generated always as
    ('owner'::member_roles) stored not null;

alter table groups add constraint fk_groups_active_owner
    foreign key (group_id, current_owner, active_owner_role)
    references memberships (group_id, user_id, member_role)
    deferrable initially deferred;

-- Unique index for channel name consistency, allows duplication if an old one is deleted
create unique index uq_channels_group_name on channels (group_id, lower(channel_name)) where deleted_at is null;

-- One graph record per attachment, including soft-deleted records. Regeneration should update/reuse the existing graph rather than inserting another.
create unique index uq_knowledge_graphs_attachment on knowledge_graphs (attachment_id);

-- Membership lookups from group
create index if not exists ix_memberships_group_id on memberships (group_id);

-- Messages inside a channel, newest first
create index if not exists ix_messages_channel_sent_at on messages (channel_id, sent_at desc);

create index if not exists ix_messages_user_id on messages (user_id);

-- Attachments
create index if not exists ix_attachments_uploaded_by on attachments (uploaded_by);

create index if not exists ix_attachments_channel_id on attachments (channel_id);

create index if not exists ix_attachments_group_id on attachments (group_id);

create index if not exists ix_attachments_message_id on attachments (message_id);

-- Vector embedding similarity search
create index if not exists ix_chunks_vector_embedding_hnsw on chunks using hnsw (vector_embedding vector_cosine_ops) with (m = 16, ef_construction = 64);

-- Active account lookup used when adding a group member by email.
create index if not exists ix_users_active_email on users (lower(email)) where deleted_at is null and status = 'active';

-- Discovery and owned-group listings, excluding soft-deleted records.
create index if not exists ix_groups_active_type_updated on groups (group_type, coalesce(last_updated_at, created_at) desc, group_id) where deleted_at is null;
create index if not exists ix_groups_active_owner_updated on groups (created_by, coalesce(last_updated_at, created_at) desc, group_id) where deleted_at is null;

-- Keep a full FK lookup index as well as an active ordered channel listing.
create index if not exists ix_channels_group_id on channels (group_id);
create index if not exists ix_channels_active_group_created on channels (group_id, created_at, channel_id) where deleted_at is null;
create index if not exists ix_messages_active_channel_sent on messages (channel_id, sent_at, message_id) where deleted_at is null;

-- The mention PK supports message lookup, this index supports user lookup/cascade.
create index if not exists ix_message_mentions_user_id on message_mentions (user_id);

-- Exact group/channel grounding with ready, non-deleted content.
create index if not exists ix_attachments_ready_group_channel on attachments (group_id, channel_id, attachment_id) where deleted_at is null and processing_status = 'ready';
create index if not exists ix_chunks_active_attachment_order on chunks (attachment_id, chunk_order, chunk_id) where deleted_at is null;

-- Response history, selected response lookup, and citation FK traversal.
create index if not exists ix_ai_responses_message_attempt on ai_responses (message_id, attempt_number desc, response_id desc);
create index if not exists ix_ai_response_sources_response on ai_response_sources (response_id, retrieval_id);
create index if not exists ix_ai_response_sources_chunk on ai_response_sources (chunk_id);
create index if not exists ix_ai_response_sources_node on ai_response_sources (node_id);
create index if not exists ix_ai_response_sources_edge on ai_response_sources (edge_id);

-- Active graph nodes: graph loading and replacement.
create index if not exists ix_knowledge_nodes_active_graph on knowledge_nodes (graph_id, node_id) where deleted_at is null;

-- Active graph edges: graph loading and replacement.
create index if not exists ix_knowledge_edges_active_graph on knowledge_edges (graph_id, edge_id) where deleted_at is null;

-- My Notes: owner filtering and newest-first pagination.
create index if not exists ix_attachments_active_library_owner_uploaded on attachments (uploaded_by, uploaded_at desc) where deleted_at is null and show_in_library is true;