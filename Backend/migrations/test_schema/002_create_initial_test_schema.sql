/*
Version: 2

Existing tables:	users, groups, memberships, channels, messages, attachments, chunks,
(15 in total)   	ai_responses, ai_response_sources, ai_response_feedbacks, 
                	knowledge_graphs, knowledge_nodes, knowledge_edges, 
                	sessions, user_activity_logs
                
Updated tables: users, groups, memberships, channels, messages, chunks

Changes: 	Set the vector embedding count in Chunks to 768.
			Added table constraints for Users, Groups, Memberships, Channels, Messages.
			Changed Users's attributes.

Notes: 	Constraints for other tables are yet to be implemented. 
*/

create extension if not exists vector;
create type status as enum ('active', 'deactivated', 'deleted');
create type user_roles as enum ('student','admin');
create type member_roles as enum ('admin', 'member');
create type group_types as enum ('personal', 'private', 'public');
create type ai_modes as enum ('quiz', 'summarizer','facilitator','default');
create type ratings as enum ('good', 'bad');
create type actions as enum ('login', 'logout', 'create', 'update', 'delete',
'upload', 'download', 'send', 'edit', 'join', 'leave', 'ai_request', 'ai_feedback');

create table if not exists users (
    user_id uuid primary key,
    email text not null unique,
    fullname text not null,
    password_hash text not null,
    user_role user_roles not null,
    user_status status default 'active' not null,
    created_at timestamptz not null,
    last_updated_at timestamptz
);

create table if not exists groups (
    group_id uuid primary key,
    group_name text not null unique,
    group_type group_types not null,
    description text,
    created_by uuid not null,
    current_admin uuid not null,
    max_members int not null,
    group_status status default 'active' not null,
    created_at timestamptz not null,
    last_updated_at timestamptz,

	constraint fk_group_created_by_for_groups foreign key (created_by)	
	references users(user_id)	on delete restrict,

	constraint fk_current_admin_for_groups foreign key (current_admin) 
	references users(user_id)	on delete restrict
);

create table if not exists memberships (
    membership_id bigint generated always as identity primary key,
    user_id uuid not null,
    group_id uuid not null,
    member_role member_roles not null,
    joined_at timestamptz not null,

	constraint fk_user_id_for_memberships foreign key (user_id)	
	references users(user_id)	on delete restrict,

	constraint fk_group_id_for_memberships foreign key (group_id) 
	references groups(group_id)	on delete restrict,

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

	constraint fk_group_id_for_channels foreign key (group_id) 
	references groups(group_id)	on delete restrict,

	constraint fk_created_by_for_channels foreign key (created_by)
	references users(user_id) on delete restrict,

	constraint uq_channels_group_name    unique (group_id, channel_name)
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
	references users(user_id)	on delete restrict,

	constraint fk_channel_id_for_messages foreign key (channel_id) 
	references channels(channel_id)	on delete restrict
);

create table if not exists attachments (
    attachment_id bigint generated always as identity primary key,
    uploaded_by uuid,
    channel_id uuid,
    message_id bigint,
    file_name text,
    file_type text,
    file_size_bytes bigint,
    object_path text,
    processing_status text, -- to be defined as enum later
    uploaded_at timestamptz,
    deleted_at timestamptz
);

create table if not exists chunks (
    chunk_id bigint generated always as identity primary key,
    attachment_id bigint,
    chunk_order int,
    chunk_content text,
    embedding_model_version text,
    vector_embedding vector(768),
    created_at timestamptz
);

create table if not exists ai_responses (
    response_id bigint generated always as identity primary key,
    message_id bigint,
    ai_mode_used ai_modes default 'default',
    response jsonb,
    confidence_score double precision,
    attempt_number int,
    is_selected boolean,
    execution_time_ms int,
    token_count int,
    generated_at timestamptz
);

create table if not exists ai_response_sources (
    retrieval_id bigint generated always as identity primary key,
    response_id bigint,
    chunk_id bigint,
    node_id bigint,
    edge_id bigint,
    similarity_score double precision,
    rerank_score double precision,
    is_used_in_prompt boolean
);

create table if not exists ai_response_feedbacks (
    feedback_id bigint generated always as identity primary key,
    response_id bigint,
    user_id uuid,
    rating ratings,
    feedback_text text,
    created_at timestamptz
);

create table if not exists knowledge_graphs (
    graph_id bigint generated always as identity primary key,
    user_id uuid,
    graph_name text,
    description text,
    created_at timestamptz,
    last_updated_at timestamptz,
    deleted_at timestamptz
);

create table if not exists knowledge_nodes (
    node_id bigint generated always as identity primary key,
    graph_id bigint,
    node_label text,
    node_properties jsonb,
    position_x double precision,
    position_y double precision,
    created_at timestamptz,
    last_updated_at timestamptz
);

create table if not exists knowledge_edges (
    edge_id bigint generated always as identity primary key,
    graph_id bigint,
    source_node_id bigint,
    target_node_id bigint,
    edge_label text,
    edge_properties jsonb,
    created_at timestamptz,
    last_updated_at timestamptz
);

create table if not exists sessions (
    session_id bigint generated always as identity primary key,
    user_id uuid,
    hash_session_token text,
    ip_address inet,
    started_at timestamptz,
    expired_at timestamptz
);

create table if not exists user_activity_logs (
    activity_id bigint generated always as identity primary key,
    user_id uuid,
    user_action actions,
    entity_type text,
    entity_id text,
    ip_address inet,
    user_agent text,
    metadata jsonb,
    created_at timestamptz
);