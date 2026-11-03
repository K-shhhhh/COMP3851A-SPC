/*
Version: 9

Changes:    Aligned with test_schema/008_create_initial_test_schema.sql:
            - Added 5 report/governance enum types: report_target_type, report_status,
              report_category, report_outcomes, report_activity_actions.
            - Added 7 new tables for user profiles, notification preferences, user reports,
              evidence, report notes, report activity events, and audit events.
            - Added indexes for user_reports, evidence, report_notes, report_activity_events,
              audit_events, and user_activity_logs.

Notes:	This migration is additive and may be applied to an existing Version 8
        database without rebuilding its Docker volume.
*/

do $$
begin
    create type report_target_type as enum ('message', 'group', 'file');
exception
    when duplicate_object then null;
end
$$;

do $$
begin
    create type report_status as enum ('submitted', 'under_review', 'resolved', 'dismissed');
exception
    when duplicate_object then null;
end
$$;

do $$
begin
    create type report_category as enum (
        'harassment_bullying',
        'hate_discrimination',
        'spam_scam',
        'inappropriate_content',
        'academic_misconduct',
        'privacy_violation',
        'impersonation',
        'dangerous_content',
        'other'
    );
exception
    when duplicate_object then null;
end
$$;

do $$
begin
    create type report_outcomes as enum (
        'no_violation',
        'duplicate',
        'insufficient_evidence',
        'content_removed',
        'user_deactivated',
        'group_removed',
        'file_removed'
    );
exception
    when duplicate_object then null;
end
$$;

do $$
begin
    create type report_activity_actions as enum (
        'report_submitted',
        'review_started',
        'note_added',
        'evidence_viewed',
        'governance_action',
        'resolved',
        'dismissed'
    );
exception
    when duplicate_object then null;
end
$$;

create table if not exists user_profiles (
    user_id uuid primary key,
    bio varchar(500),
    programme varchar(120),
    year_of_study int,

    constraint fk_user_id_for_user_profiles foreign key (user_id)
    references users(user_id),

    constraint ck_year_of_study check (year_of_study is null or year_of_study between 1 and 10)
);

create table if not exists notification_preferences (
    user_id uuid primary key,
    new_group_messages boolean default true not null,
    group_mentions boolean default true not null,

    constraint fk_user_id_for_notification_preferences foreign key (user_id)
    references users(user_id)
);

create table if not exists user_reports (
    report_id uuid primary key,
    reporter_user_id uuid not null,
    target_type report_target_type not null,
    target_message_id bigint,
    target_group_id uuid,
    target_file_id bigint,
    description text not null,
    category report_category not null,
    status report_status default 'submitted' not null,
    target_snapshot jsonb not null,
    limited_context_snapshot jsonb,
    outcome report_outcomes,
    internal_resolution_reason text,
    public_summary text,
    created_at timestamptz not null,
    last_updated_at timestamptz,
    case_closed_at timestamptz,

    constraint fk_reporter_user_id_for_user_reports foreign key (reporter_user_id)
	references users(user_id),

    constraint fk_target_message_id_for_user_reports foreign key (target_message_id)
	references messages(message_id),

    constraint fk_target_group_id_for_user_reports foreign key (target_group_id)
	references groups(group_id),

    constraint fk_target_file_id_for_user_reports foreign key (target_file_id)
	references attachments(attachment_id),

    constraint chk_target_matches_type check (
        (target_type = 'message' and target_message_id is not null and target_group_id is null and target_file_id is null) or
        (target_type = 'group'   and target_group_id is not null and target_message_id is null and target_file_id is null) or
        (target_type = 'file'    and target_file_id is not null and target_message_id is null and target_group_id is null))
);

create table if not exists evidence (
    evidence_id uuid primary key,
    report_id uuid not null,
    private_storage_key text not null,
    file_name text not null,
    file_type text not null,
    file_size_bytes bigint not null,
    created_at timestamptz not null,

    constraint fk_report_id_for_evidence foreign key (report_id)
	references user_reports(report_id),

	constraint ck_evidence_file_size check (file_size_bytes > 0)
);

create table if not exists report_notes (
    note_id uuid primary key,
    report_id uuid not null,
    admin_id uuid not null,
    note text not null,
    created_at timestamptz not null,

    constraint fk_report_id_for_report_notes foreign key (report_id)
	references user_reports(report_id),

    constraint fk_admin_id_for_report_notes foreign key (admin_id)
	references users(user_id)
);

create table if not exists audit_events (
    audit_event_id uuid primary key,
    admin_id uuid not null,
    action text not null,
    target_type text not null,
    target_id text not null,
    reason text,
    event_timestamp timestamptz not null,

    constraint fk_admin_id_for_audit_events foreign key (admin_id)
	references users(user_id)
);

create table if not exists report_activity_events (
    activity_event_id uuid primary key,
    report_id uuid not null,
    actor_type user_roles not null,
    actor_id uuid not null,
    action report_activity_actions not null,
    evidence_id uuid,
    report_note_id uuid,
    summary text,
    audit_event_id uuid,
    event_timestamp timestamptz not null,

    constraint fk_report_id_for_report_activity_events foreign key (report_id)
	references user_reports(report_id),

    constraint fk_actor_id_for_report_activity_events foreign key (actor_id)
	references users(user_id),

    constraint fk_evidence_id_for_report_activity_events foreign key (evidence_id)
	references evidence(evidence_id),

    constraint fk_report_note_id_for_report_activity_events foreign key (report_note_id)
	references report_notes(note_id),

    constraint fk_audit_event_id_for_report_activity_events foreign key (audit_event_id)
	references audit_events(audit_event_id)
);

-- User Reports: reporter history, admin status filtering, and polymorphic targets
create index if not exists ix_user_reports_reporter_user_id on user_reports (reporter_user_id);
create index if not exists ix_user_reports_status_created on user_reports (status, created_at desc);
create index if not exists ix_user_reports_target_type on user_reports (target_type, created_at desc);
create index if not exists ix_user_reports_target_message_id on user_reports (target_message_id) where target_message_id is not null;
create index if not exists ix_user_reports_target_group_id on user_reports (target_group_id) where target_group_id is not null;
create index if not exists ix_user_reports_target_file_id on user_reports (target_file_id) where target_file_id is not null;

-- Evidence: lookup by report
create index if not exists ix_evidence_report_id on evidence (report_id);

-- Report Notes: chronological note history per report
create index if not exists ix_report_notes_report_id_created on report_notes (report_id, created_at);
create index if not exists ix_report_notes_admin_id on report_notes (admin_id);

-- Report Activity Events: chronological activity timeline per report
create index if not exists ix_report_activity_events_report_id_timestamp on report_activity_events (report_id, event_timestamp);
create index if not exists ix_report_activity_events_actor_id on report_activity_events (actor_id);
create index if not exists ix_report_activity_events_evidence_id on report_activity_events (evidence_id) where evidence_id is not null;
create index if not exists ix_report_activity_events_report_note_id on report_activity_events (report_note_id) where report_note_id is not null;
create index if not exists ix_report_activity_events_audit_event_id on report_activity_events (audit_event_id) where audit_event_id is not null;

-- Audit Events: admin governance action trails and target lookup
create index if not exists ix_audit_events_admin_timestamp on audit_events (admin_id, event_timestamp desc);
create index if not exists ix_audit_events_target on audit_events (target_type, target_id, event_timestamp desc);
create index if not exists ix_audit_events_event_timestamp on audit_events (event_timestamp desc);

-- User Activity Logs: user activity history and action auditing
create index if not exists ix_user_activity_logs_user_created on user_activity_logs (user_id, created_at desc);
create index if not exists ix_user_activity_logs_action_created on user_activity_logs (user_action, created_at desc);
