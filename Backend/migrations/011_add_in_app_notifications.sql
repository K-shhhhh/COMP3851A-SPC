/*
Version: 11

Adds persistent in-app notifications for Study Group messages and mentions.
Notification preferences remain in notification_preferences.
*/

do $$
begin
    create type notification_types as enum (
        'new_group_message',
        'group_mention'
    );
exception
    when duplicate_object then null;
end $$;

create table if not exists notifications (
    notification_id bigint generated always as identity primary key,
    recipient_user_id uuid not null,
    notification_type notification_types not null,
    actor_user_id uuid not null,
    group_id uuid not null,
    channel_id uuid not null,
    message_id bigint not null,
    created_at timestamptz default now() not null,
    read_at timestamptz,

    constraint fk_notifications_recipient_user foreign key (recipient_user_id)
        references users(user_id),
    constraint fk_notifications_actor_user foreign key (actor_user_id)
        references users(user_id),
    constraint fk_notifications_group foreign key (group_id)
        references groups(group_id),
    constraint fk_notifications_channel foreign key (channel_id)
        references channels(channel_id),
    constraint fk_notifications_message foreign key (message_id)
        references messages(message_id),
    constraint uq_notifications_recipient_message_type unique (
        recipient_user_id,
        message_id,
        notification_type
    )
);

create index if not exists ix_notifications_recipient_created
    on notifications (recipient_user_id, created_at desc, notification_id desc);

create index if not exists ix_notifications_recipient_unread
    on notifications (recipient_user_id, created_at desc, notification_id desc)
    where read_at is null;
