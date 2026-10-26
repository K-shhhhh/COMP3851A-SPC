/*
Version: 9

Purpose:
    Store private per-student quiz results used by the learning-progress
    dashboard.

Privacy:
    Rows are keyed to users.user_id. The public API never accepts a user ID;
    it derives the student from the authenticated access token.
*/

create table if not exists quiz_attempts (
    attempt_id bigint generated always as identity primary key,
    student_user_id uuid not null
        references users(user_id) on delete cascade,
    topic text not null,
    is_correct boolean not null,
    attempted_at timestamptz not null default now(),
    constraint ck_quiz_attempts_topic_length
        check (char_length(btrim(topic)) between 1 and 100)
);

create index if not exists ix_quiz_attempts_student_attempted
on quiz_attempts (student_user_id, attempted_at desc, attempt_id desc);
