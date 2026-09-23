/*
Version: 4

Existing tables:	users, groups, memberships, channels, messages, attachments, chunks,
                	knowledge_graphs, knowledge_nodes, knowledge_edges,
(14 in total)   	ai_responses, ai_response_sources, ai_response_feedbacks,
                	user_activity_logs
                
Updated tables: all tables

Changes: 	Removed "status" attribute from Groups table
			Added "check" Constraints to Attachments tables.
			Added indexes for Memberships, Messages, Attachments and Chunks tables for better query performance.
			In Chunks table, "source_page" attribute is nullable and "chunk_content" attribute is non-nullable now.
			Replaced/Added soft-deletion flags as "deleted_at" attribute in Users, Groups, Channels, Messages, Attachments and Chunks tables.
			Removed deletion rules on every table relationship since the applicaiton solely depends on soft-deletions.
					
Notes:	Memberships table allows hard-deletion when a memeber left a group. Other than that, any deletions shall be soft-deletion.
		Deletion rules will be implemented as required in future updates.
		Besides, future updates should focus more on constraints and indexes of the tables related to knowledge graph, AI responses and activity logs.
*/

create extension if not exists vector;
create type activity_status as enum ('active', 'deactivated');
create type user_roles as enum ('student','admin');
create type member_roles as enum ('admin', 'member');
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
    current_admin uuid not null,
    max_members int not null,
    created_at timestamptz not null,
    last_updated_at timestamptz,
	deleted_at timestamptz,

	constraint fk_group_created_by_for_groups foreign key (created_by)	
	references users(user_id),

	constraint fk_current_admin_for_groups foreign key (current_admin) 
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

	constraint uq_memberships_user_group	unique (user_id, group_id)
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
    ai_mode_used ai_modes default 'default' not null,
    sent_at timestamptz not null,
    edited_at timestamptz,
    deleted_at timestamptz,

	constraint fk_user_id_for_messages foreign key (user_id)	
	references users(user_id),

	constraint fk_channel_id_for_messages foreign key (channel_id) 
	references channels(channel_id)
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
    object_path text,
    processing_status attachment_status default 'queued' not null,
	processing_progress int default 0 not null,
	processing_error text,
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
	
	constraint ck_attachments_file_size check (file_size_bytes >= 0),
	
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

	constraint uq_chunks_attachment_order    unique (attachment_id, chunk_order)
);

create table if not exists knowledge_graphs (
    graph_id bigint generated always as identity primary key,
    user_id uuid not null,
    graph_name text not null,
    description text,
    created_at timestamptz not null,
    last_updated_at timestamptz,
    deleted_at timestamptz,

	constraint fk_user_id_for_knowledge_graphs foreign key (user_id) 
	references users(user_id)
);

create table if not exists knowledge_nodes (
    node_id bigint generated always as identity primary key,
    graph_id bigint not null,
    node_label text not null,
    node_properties jsonb,
    position_x double precision,
    position_y double precision,
    created_at timestamptz not null,
    last_updated_at timestamptz,

	constraint fk_graph_id_for_knowledge_nodes foreign key (graph_id) 
	references knowledge_graphs(graph_id)
);

create table if not exists knowledge_edges (
    edge_id bigint generated always as identity primary key,
    graph_id bigint not null,
    source_node_id bigint not null,
    target_node_id bigint not null,
    edge_label text,
    edge_properties jsonb,
    created_at timestamptz not null,
    last_updated_at timestamptz,

	constraint fk_graph_id_for_knowledge_edges foreign key (graph_id) 
	references knowledge_graphs(graph_id),

	constraint fk_source_node_id_for_knowledge_edges foreign key (source_node_id) 
	references knowledge_nodes(node_id),

	constraint fk_target_node_id_for_knowledge_edges foreign key (target_node_id) 
	references knowledge_nodes(node_id)
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

-- Unique index for channel name consistency, allows duplication if an old one is deleted
create unique index uq_channels_group_name on channels (group_id, channel_name) where deleted_at is null;

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

