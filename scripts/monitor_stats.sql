-- Staging health snapshot for the team. Every statement is a select, so it is
-- safe to run at any time. Run it from the project folder on the server:
--
--   sh scripts/staging.sh exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < scripts/monitor_stats.sql
--
-- Days are cut at midnight Singapore time. Answer time is the gap between a
-- student's message and the saved AI reply. The ai_responses columns
-- execution_time_ms and token_count are always 0 today because the app does
-- not record them yet, so this file does not use them.


-- 1. Right now
select 'uploads waiting in the queue' as metric, count(*)::text as value
from attachments
where processing_status = 'queued' and deleted_at is null
union all
select 'uploads being processed', count(*)::text
from attachments
where processing_status = 'processing' and deleted_at is null
union all
select 'uploads waiting or processing for over 15 minutes (check the worker)', count(*)::text
from attachments
where processing_status in ('queued', 'processing')
  and deleted_at is null
  and uploaded_at < now() - interval '15 minutes'
union all
select 'failed uploads in the last 24 hours', count(*)::text
from attachments
where processing_status = 'failed'
  and deleted_at is null
  and last_updated_at > now() - interval '24 hours'
union all
select 'students active in the last 24 hours', count(distinct activity.user_id)::text
from (
    select user_id, sent_at as happened_at from messages where deleted_at is null
    union all
    select uploaded_by, uploaded_at from attachments where deleted_at is null
) as activity
where activity.happened_at > now() - interval '24 hours'
union all
select 'students active in the last 7 days', count(distinct activity.user_id)::text
from (
    select user_id, sent_at as happened_at from messages where deleted_at is null
    union all
    select uploaded_by, uploaded_at from attachments where deleted_at is null
) as activity
where activity.happened_at > now() - interval '7 days';


-- 2. Each day for the last 14 days
with days as (
    select series.day
    from generate_series(
        date_trunc('day', now() at time zone 'Asia/Singapore') - interval '13 days',
        date_trunc('day', now() at time zone 'Asia/Singapore'),
        interval '1 day'
    ) as series(day)
)
select to_char(days.day, 'YYYY-MM-DD Dy') as day_singapore,
       (select count(*) from users u
         where date_trunc('day', u.created_at at time zone 'Asia/Singapore') = days.day) as new_students,
       (select count(*) from attachments a
         where a.deleted_at is null
           and date_trunc('day', a.uploaded_at at time zone 'Asia/Singapore') = days.day) as uploads,
       (select count(*) from messages m
         where m.deleted_at is null
           and date_trunc('day', m.sent_at at time zone 'Asia/Singapore') = days.day) as messages,
       (select count(distinct m.user_id) from messages m
         where m.deleted_at is null
           and date_trunc('day', m.sent_at at time zone 'Asia/Singapore') = days.day) as students_who_wrote
from days
order by days.day desc;


-- 3. How far students got: signed up, uploaded, asked
with per_student as (
    select u.user_id,
           (select count(*) from attachments a
             where a.uploaded_by = u.user_id and a.deleted_at is null) as uploads,
           (select count(*) from messages m
             where m.user_id = u.user_id and m.deleted_at is null) as messages
    from users u
    where u.deleted_at is null
)
select count(*) as registered_students,
       count(*) filter (where uploads > 0) as uploaded_a_note,
       count(*) filter (where messages > 0) as sent_a_message,
       count(*) filter (where uploads > 0 and messages = 0) as uploaded_but_never_asked,
       count(*) filter (where uploads = 0) as never_uploaded
from per_student;


-- 4. PDF processing time over the last 14 days, split by file size.
--    Wait is time in the queue. Processing is time inside the worker.
select case
           when file_size_bytes < 1048576 then 'under 1 MB'
           when file_size_bytes < 5242880 then '1 to 5 MB'
           else 'over 5 MB'
       end as file_size,
       count(*) as ready_uploads,
       round(avg(extract(epoch from (processing_started_at - uploaded_at)))::numeric) as avg_wait_seconds,
       round((percentile_cont(0.5) within group (
           order by extract(epoch from (processing_completed_at - processing_started_at))::double precision
       ))::numeric) as median_processing_seconds,
       round((percentile_cont(0.9) within group (
           order by extract(epoch from (processing_completed_at - processing_started_at))::double precision
       ))::numeric) as p90_processing_seconds,
       round(max(extract(epoch from (processing_completed_at - processing_started_at)))::numeric) as slowest_processing_seconds
from attachments
where processing_status = 'ready'
  and processing_started_at is not null
  and processing_completed_at is not null
  and deleted_at is null
  and uploaded_at > now() - interval '14 days'
group by 1
order by min(file_size_bytes);


-- 5. The ten slowest uploads in the last 14 days (ids only, no file names)
select attachment_id,
       round(file_size_bytes / 1048576.0, 1) as size_mb,
       processing_status as status,
       round(extract(epoch from (processing_started_at - uploaded_at))::numeric) as wait_seconds,
       round(extract(epoch from (processing_completed_at - processing_started_at))::numeric) as processing_seconds
from attachments
where processing_started_at is not null
  and processing_completed_at is not null
  and deleted_at is null
  and uploaded_at > now() - interval '14 days'
order by processing_completed_at - processing_started_at desc
limit 10;


-- 6. Why uploads failed in the last 14 days, most common first
select left(processing_error, 120) as reason, count(*) as times
from attachments
where processing_status = 'failed'
  and deleted_at is null
  and uploaded_at > now() - interval '14 days'
group by 1
order by times desc;


-- 7. AI answers each day for the last 14 days.
--    A refusal is a reply saying the notes do not cover the question.
select to_char(date_trunc('day', m.sent_at at time zone 'Asia/Singapore'), 'YYYY-MM-DD') as day_singapore,
       count(*) as answers,
       count(*) filter (
           where r.response ->> 'content' ilike '%not available in the supplied study material%'
       ) as refusals,
       round(100.0 * count(*) filter (
           where r.response ->> 'content' ilike '%not available in the supplied study material%'
       ) / count(*), 1) as refusal_percent,
       round((percentile_cont(0.5) within group (
           order by extract(epoch from (r.generated_at - m.sent_at))::double precision
       ))::numeric, 1) as median_answer_seconds,
       round((percentile_cont(0.9) within group (
           order by extract(epoch from (r.generated_at - m.sent_at))::double precision
       ))::numeric, 1) as p90_answer_seconds
from messages m
join ai_responses r on r.message_id = m.message_id and r.is_selected
where m.deleted_at is null
  and m.sent_at > now() - interval '14 days'
group by 1
order by 1 desc;


-- 8. Which AI modes students use (last 14 days)
select r.ai_mode_used::text as ai_mode, count(*) as answers
from ai_responses r
where r.is_selected
  and r.generated_at > now() - interval '14 days'
group by 1
order by answers desc;


-- 9. Where the disk space is going inside the database
select pg_size_pretty(pg_database_size(current_database())) as whole_database;

select c.relname as table_name,
       pg_size_pretty(pg_total_relation_size(c.oid)) as total_size
from pg_class c
join pg_namespace n on n.oid = c.relnamespace
where n.nspname = 'public' and c.relkind = 'r'
order by pg_total_relation_size(c.oid) desc
limit 8;
