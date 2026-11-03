/*
Version: 7

Changes:    Aligned with test_schema/007_create_initial_test_schema.sql (including 6.1 ownership rules):
            - Added enum value 'owner' to member_roles.
            - Renamed "current_admin" to "current_owner", added stored generated column "active_owner_role",
              and added deferred composite FK "fk_groups_active_owner" on Groups table.
            - Added composite unique constraint "uq_memberships_group_user_role" and partial unique index
              "uq_memberships_group_owner" on Memberships table.
            - Added "processing_started_at" and "processing_completed_at" in Attachments table.
            - Added "show_online_status" in Users table.
*/

alter type member_roles add value if not exists 'owner' before 'admin';

do $$
begin
    if exists (
        select 1
        from information_schema.columns
        where table_schema = current_schema()
          and table_name = 'groups'
          and column_name = 'current_admin'
    ) then
        alter table groups rename column current_admin to current_owner;
    end if;
end
$$;

alter table groups drop constraint if exists fk_current_admin_for_groups;
alter table groups drop constraint if exists fk_current_owner_for_groups;
alter table groups add constraint fk_current_owner_for_groups
    foreign key (current_owner) references users(user_id);

alter table memberships drop constraint if exists uq_memberships_group_user_role;
alter table memberships add constraint uq_memberships_group_user_role
    unique (group_id, user_id, member_role);

-- Memberships have no deleted_at: leaving hard-deletes the membership.
create unique index if not exists uq_memberships_group_owner
    on memberships (group_id)
    where member_role = 'owner';

-- Every group, including personal and soft-deleted groups, retains an owner.
-- The generated constant cannot be overwritten or become NULL to bypass the FK.
alter table groups
    add column if not exists active_owner_role member_roles
    generated always as ('owner'::member_roles) stored not null;

alter table groups drop constraint if exists fk_groups_active_owner;
alter table groups add constraint fk_groups_active_owner
    foreign key (group_id, current_owner, active_owner_role)
    references memberships (group_id, user_id, member_role)
    deferrable initially deferred;

-- Add durable timing boundaries for the PDF upload-processing lifecycle.
-- Knowledge-graph generation intentionally runs outside this measured interval.
alter table attachments
    add column if not exists processing_started_at timestamptz,
    add column if not exists processing_completed_at timestamptz;

-- Add persistent privacy preference controlling whether an authenticated user
-- may appear in online-member lists.
alter table users
    add column if not exists show_online_status boolean default true not null;
