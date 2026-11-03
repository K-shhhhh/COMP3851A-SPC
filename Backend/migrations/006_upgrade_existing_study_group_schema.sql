/*
Version 6

Changes:    Aligned with test_schema/006_create_initial_test_schema.sql:
            - Removed default value and not null constraint from "ai_mode_used" attribute in Messages table.
            - Created Message_Mentions table with NOT NULL composite keys and user lookup index.
            - Added "show_in_library" attribute, NOT NULL on "object_path", and check constraint (file_size_bytes > 0) in Attachments table.
            - Restructured Knowledge_Graphs, Knowledge_Nodes, and Knowledge_Edges tables: attributes, relationships, constraints, and indexes.
            - Added/Updated indexes across Study Group, Attachments, Chunks, Knowledge Graph, and AI Response tables.

Notes:	Idempotent incremental migration bringing an existing v4/v5 schema to Version 6.
*/

begin;

-- Ordinary human messages do not invoke an AI mode. AI-invoking messages
-- continue to store the selected mode explicitly.
alter table messages alter column ai_mode_used drop default;
alter table messages alter column ai_mode_used drop not null;

-- A message may mention multiple users, and a user may be mentioned by many
-- messages. The composite primary key also prevents duplicate mentions.
create table if not exists message_mentions (
    message_id bigint not null references messages(message_id) on delete cascade,
    user_id uuid not null references users(user_id) on delete cascade,
    primary key (message_id, user_id)
);

alter table message_mentions
    alter column message_id set not null,
    alter column user_id set not null;

-- Attachments: enforce non-null object_path, positive file size, and library visibility flag.
alter table attachments
    alter column object_path set not null,
    add column if not exists show_in_library boolean default true not null;

alter table attachments drop constraint if exists ck_attachments_file_size;
alter table attachments add constraint ck_attachments_file_size
    check (file_size_bytes > 0);

-- Knowledge Graphs: scope one graph per attachment rather than user_id.
alter table knowledge_edges drop constraint if exists fk_edge_source_same_graph;
alter table knowledge_edges drop constraint if exists fk_edge_target_same_graph;
alter table knowledge_nodes drop constraint if exists uq_knowledge_nodes_graph_node;
alter table knowledge_nodes drop constraint if exists fk_source_chunk_id_for_knowledge_nodes;
alter table knowledge_graphs drop constraint if exists fk_user_id_for_knowledge_graphs;
alter table knowledge_graphs drop constraint if exists fk_attachment_id_for_knowledge_graphs;

alter table knowledge_graphs
    drop column if exists user_id,
    add column if not exists attachment_id bigint not null;

alter table knowledge_graphs add constraint fk_attachment_id_for_knowledge_graphs
    foreign key (attachment_id) references attachments(attachment_id);

-- Knowledge Nodes: restructure attributes, chunk linkage, soft deletion, and composite uniqueness.
alter table knowledge_nodes
    drop column if exists node_label,
    drop column if exists node_properties,
    drop column if exists position_x,
    drop column if exists position_y,
    add column if not exists title text not null,
    add column if not exists topic text not null,
    add column if not exists description text not null,
    add column if not exists source_chunk_id bigint,
    add column if not exists deleted_at timestamptz;

alter table knowledge_nodes add constraint fk_source_chunk_id_for_knowledge_nodes
    foreign key (source_chunk_id) references chunks(chunk_id);

alter table knowledge_nodes add constraint uq_knowledge_nodes_graph_node
    unique (graph_id, node_id);

-- Knowledge Edges: restructure attributes, soft deletion, and same-graph composite FKs.
alter table knowledge_edges
    drop column if exists edge_label,
    drop column if exists edge_properties,
    add column if not exists relationship_label text,
    add column if not exists deleted_at timestamptz;

alter table knowledge_edges add constraint fk_edge_source_same_graph
    foreign key (graph_id, source_node_id) references knowledge_nodes(graph_id, node_id);

alter table knowledge_edges add constraint fk_edge_target_same_graph
    foreign key (graph_id, target_node_id) references knowledge_nodes(graph_id, node_id);

-- Unique index for channel name consistency, allows duplication if an old one is deleted.
drop index if exists uq_channels_group_name;
create unique index if not exists uq_channels_group_name
    on channels (group_id, lower(channel_name))
    where deleted_at is null;

-- One graph record per attachment, including soft-deleted records.
create unique index if not exists uq_knowledge_graphs_attachment
    on knowledge_graphs (attachment_id);

-- Active account lookup used when adding a group member by email.
create index if not exists ix_users_active_email
    on users (lower(email))
    where deleted_at is null and status = 'active';

-- Discovery and owned-group listings, excluding soft-deleted records.
create index if not exists ix_groups_active_type_updated
    on groups (group_type, coalesce(last_updated_at, created_at) desc, group_id)
    where deleted_at is null;
create index if not exists ix_groups_active_owner_updated
    on groups (created_by, coalesce(last_updated_at, created_at) desc, group_id)
    where deleted_at is null;

-- Keep a full FK lookup index as well as an active ordered channel listing.
create index if not exists ix_channels_group_id on channels (group_id);
create index if not exists ix_channels_active_group_created
    on channels (group_id, created_at, channel_id)
    where deleted_at is null;
create index if not exists ix_messages_active_channel_sent
    on messages (channel_id, sent_at, message_id)
    where deleted_at is null;

-- The mention PK supports message lookup, this index supports user lookup/cascade.
create index if not exists ix_message_mentions_user_id
    on message_mentions (user_id);

-- Exact group/channel grounding with ready, non-deleted content.
create index if not exists ix_attachments_ready_group_channel
    on attachments (group_id, channel_id, attachment_id)
    where deleted_at is null and processing_status = 'ready';
create index if not exists ix_chunks_active_attachment_order
    on chunks (attachment_id, chunk_order, chunk_id)
    where deleted_at is null;

-- Response history, selected response lookup, and citation FK traversal.
create index if not exists ix_ai_responses_message_attempt
    on ai_responses (message_id, attempt_number desc, response_id desc);
create index if not exists ix_ai_response_sources_response
    on ai_response_sources (response_id, retrieval_id);
create index if not exists ix_ai_response_sources_chunk
    on ai_response_sources (chunk_id);
create index if not exists ix_ai_response_sources_node
    on ai_response_sources (node_id);
create index if not exists ix_ai_response_sources_edge
    on ai_response_sources (edge_id);

-- Active graph nodes: graph loading and replacement.
create index if not exists ix_knowledge_nodes_active_graph
    on knowledge_nodes (graph_id, node_id)
    where deleted_at is null;

-- Active graph edges: graph loading and replacement.
create index if not exists ix_knowledge_edges_active_graph
    on knowledge_edges (graph_id, edge_id)
    where deleted_at is null;

-- My Notes: owner filtering and newest-first pagination.
create index if not exists ix_attachments_active_library_owner_uploaded
    on attachments (uploaded_by, uploaded_at desc)
    where deleted_at is null and show_in_library is true;

commit;
