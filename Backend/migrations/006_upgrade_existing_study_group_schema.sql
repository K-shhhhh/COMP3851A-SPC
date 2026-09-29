/*
Upgrade an existing version-4 local database for Study Group persistence.

Fresh databases use 005_create_initial_test_schema.sql and already contain
these objects. This migration is for Docker volumes that were initialized
before the message-mentions and Study Group retrieval changes were added.
It is intentionally additive and safe to run more than once.
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

-- Channel names are unique within an active group without being
-- case-sensitive. Drop the older case-sensitive index before replacing it.
drop index if exists uq_channels_group_name;
create unique index if not exists uq_channels_group_name
    on channels (group_id, lower(channel_name))
    where deleted_at is null;

create index if not exists ix_users_active_email
    on users (lower(email))
    where deleted_at is null and status = 'active';
create index if not exists ix_groups_active_type_updated
    on groups (group_type, coalesce(last_updated_at, created_at) desc, group_id)
    where deleted_at is null;
create index if not exists ix_groups_active_owner_updated
    on groups (created_by, coalesce(last_updated_at, created_at) desc, group_id)
    where deleted_at is null;
create index if not exists ix_channels_group_id on channels (group_id);
create index if not exists ix_channels_active_group_created
    on channels (group_id, created_at, channel_id)
    where deleted_at is null;
create index if not exists ix_messages_active_channel_sent
    on messages (channel_id, sent_at, message_id)
    where deleted_at is null;
create index if not exists ix_message_mentions_user_id
    on message_mentions (user_id);
create index if not exists ix_attachments_ready_group_channel
    on attachments (group_id, channel_id, attachment_id)
    where deleted_at is null and processing_status = 'ready';
create index if not exists ix_chunks_active_attachment_order
    on chunks (attachment_id, chunk_order, chunk_id)
    where deleted_at is null;
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

commit;
