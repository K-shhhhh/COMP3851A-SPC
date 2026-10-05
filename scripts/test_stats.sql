-- Objective numbers for the user testing report. Run with:
--   sh scripts/staging.sh exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < scripts/test_stats.sql

select 'registered students' as metric, count(*)::text as value from users
union all
select 'uploads (My Notes)', count(*)::text from attachments where show_in_library
union all
select 'uploads (study group channels)', count(*)::text from attachments where channel_id is not null
union all
select 'chat and group messages', count(*)::text from messages;

-- How uploads ended up
select processing_status, count(*) as uploads
from attachments
group by processing_status
order by uploads desc;

-- How long processing took for uploads that reached ready
select count(*) as ready_uploads,
       round(avg(extract(epoch from (last_updated_at - uploaded_at)))) as avg_seconds,
       round(max(extract(epoch from (last_updated_at - uploaded_at)))) as slowest_seconds
from attachments
where processing_status = 'ready' and last_updated_at is not null;

-- Why uploads failed (most common first)
select left(processing_error, 120) as reason, count(*) as times
from attachments
where processing_status = 'failed'
group by reason
order by times desc;
