-- Add durable timing boundaries for the PDF upload-processing lifecycle.
-- Knowledge-graph generation intentionally runs outside this measured interval.

alter table attachments
    add column if not exists processing_started_at timestamptz,
    add column if not exists processing_completed_at timestamptz;
