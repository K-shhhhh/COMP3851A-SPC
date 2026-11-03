/*
Version: 8.1

Changes:    Aligned with test_schema/008_1_create_initial_test_schema.sql:
            - Added partial unique indexes on USER_REPORTS table to prevent the same reporter from creating duplicate active ('submitted', 'under_review') reports for the same
              message, group, or file target.
            - Added composite keyset indexes on USER_REPORTS and AUDIT_EVENTS tables for stable opaque cursor pagination.
            - Aligned ix_report_activity_events_audit_event_id as a partial unique index to enforce the 0..1-to-0..1 link between REPORT_ACTIVITY_EVENTS and AUDIT_EVENTS tables.

*/

-- User Reports: composite keyset indexes for stable opaque cursor pagination
create index if not exists ix_user_reports_reporter_created_id
    on user_reports (reporter_user_id, created_at desc, report_id desc);

create index if not exists ix_user_reports_created_id
    on user_reports (created_at desc, report_id desc);

-- Partial uniqueness preventing duplicate active ('submitted', 'under_review') reports by the same reporter for the same target
create unique index if not exists uq_user_reports_active_reporter_message
    on user_reports (reporter_user_id, target_message_id)
    where status in ('submitted', 'under_review') and target_message_id is not null;

create unique index if not exists uq_user_reports_active_reporter_group
    on user_reports (reporter_user_id, target_group_id)
    where status in ('submitted', 'under_review') and target_group_id is not null;

create unique index if not exists uq_user_reports_active_reporter_file
    on user_reports (reporter_user_id, target_file_id)
    where status in ('submitted', 'under_review') and target_file_id is not null;

-- Report Activity Events: 0..1-to-0..1 partial unique index on audit_event_id
drop index if exists ix_report_activity_events_audit_event_id;
create unique index if not exists ix_report_activity_events_audit_event_id
    on report_activity_events (audit_event_id)
    where audit_event_id is not null;

-- Audit Events: composite keyset index for stable opaque cursor pagination
create index if not exists ix_audit_events_timestamp_id
    on audit_events (event_timestamp desc, audit_event_id desc);
